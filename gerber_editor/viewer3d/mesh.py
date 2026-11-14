"""Build a substrate and functional layer surfaces without changing source data."""

import re
from dataclasses import dataclass, field

import numpy as np
from shapely import (
    constrained_delaunay_triangles,
    get_coordinates,
    get_rings,
    make_valid,
    orient_polygons,
)
from shapely.geometry import GeometryCollection, LineString, Polygon, box
from shapely.ops import polygonize, unary_union

from gerber_editor.core.layer import canonical_function
from gerber_editor.core.primitives import Arc, Line, Region
from gerber_editor.geometry.boolean import compose_layer, curve_points, object_geometry
from gerber_editor.tools.drilling import DRILL_ROLES, drill_geometry
from gerber_editor.tools.routing import routing_geometry
from gerber_editor.viewer3d.cache import GeometryMemo


@dataclass
class MeshPart:
    key: str
    name: str
    vertices: np.ndarray
    color: tuple
    geometry: object = None
    z_min: float = 0
    z_max: float = 0
    material: str = "fr4"


@dataclass
class BoardMesh:
    parts: list[MeshPart]
    center: tuple[float, float]
    size: tuple[float, float, float]
    estimated_outline: bool
    triangles: int
    outline: object = None
    _cache: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class LayerGeometry:
    key: str
    name: str
    role: str
    geometry: object


@dataclass(frozen=True)
class BoardGeometry:
    """Detail-independent composition, reusable across preview settings."""

    outline: object
    routes: object
    drills: object
    layers: tuple[LayerGeometry, ...]
    estimated_outline: bool
    _cache: dict = field(default_factory=dict, repr=False)


def polygons(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def outline_geometry(layers):
    rings, filled = [], []
    for layer in layers:
        if canonical_function(layer.function) != "Edge.Cuts":
            continue
        regions = []
        for obj in layer.objects:
            g = obj.geometry
            if isinstance(g, Region):
                regions.append(obj)
            elif isinstance(g, (Line, Arc)):
                coords = curve_points(g)
                rings.append(LineString([(round(x, 6), round(y, 6)) for x, y in coords]))
        if regions:
            filled.append(compose_layer(regions, {obj.id: object_geometry(obj) for obj in regions}))
    faces = list(polygonize(unary_union(rings))) if rings else []
    exteriors = [Polygon(face.exterior) for face in faces]
    result = GeometryCollection()
    for polygon in sorted(exteriors, key=lambda p: -p.area):
        depth = sum(other.area > polygon.area and other.covers(polygon) for other in exteriors)
        result = result.difference(polygon) if depth % 2 else result.union(polygon)
    if filled:
        result = result.union(unary_union(filled))
    return result


def surface(geometry, z, normal, center):
    if geometry.is_empty:
        return np.empty((0, 6), dtype=np.float32)
    coordinates = get_coordinates(constrained_delaunay_triangles(geometry))
    if not len(coordinates):
        return np.empty((0, 6), dtype=np.float32)
    # CDT emits closed triangle rings (four coordinates). Extract all vertices
    # in GEOS/NumPy rather than creating a Python object for every triangle.
    xy = coordinates.reshape(-1, 4, 2)[:, :3].astype(np.float32).reshape(-1, 2)
    result = np.zeros((len(xy), 6), dtype=np.float32)
    result[:, :2] = xy - np.asarray(center)
    result[:, 2] = z
    result[:, 5] = normal
    return result


def substrate(geometry, thickness, center):
    top = surface(geometry, thickness / 2, 1, center)
    bottom = top.copy()
    bottom[:, 2] *= -1
    bottom[:, 5] = -1
    rings = get_rings(orient_polygons(np.asarray(list(polygons(geometry)), dtype=object)))
    coordinates, indices = get_coordinates(rings, return_index=True)
    # Adjacent points from different rings must never form a wall segment.
    same_ring = indices[:-1] == indices[1:]
    a, b = coordinates[:-1][same_ring], coordinates[1:][same_ring]
    delta = b - a
    lengths = np.hypot(delta[:, 0], delta[:, 1])
    nonzero = lengths > 0
    a, b, delta, lengths = a[nonzero], b[nonzero], delta[nonzero], lengths[nonzero]
    sides = np.zeros((len(a), 6, 6), dtype=np.float32)
    sides[:, :, :2] = np.stack((a, b, b, a, b, a), axis=1) - np.asarray(center)
    sides[:, :, 2] = np.asarray((-1, -1, 1, -1, 1, 1)) * (thickness / 2)
    sides[:, :, 3] = (delta[:, 1] / lengths)[:, None]
    sides[:, :, 4] = (-delta[:, 0] / lengths)[:, None]
    return np.concatenate((top, bottom, sides.reshape(-1, 6)))


def layer_part(memo, cache_key, layer, shape, z, sign, center, color, height, material):
    return memo.get(
        cache_key,
        (layer.name, layer.role, z, sign, center, color, height, material),
        (shape,),
        lambda: MeshPart(
            layer.key,
            layer.name + " · " + layer.role,
            surface(shape, z, sign, center),
            color,
            shape,
            min(z, z - sign * height),
            max(z, z - sign * height),
            material,
        ),
    )


def prepare_board(layers, cache=None, previous=None, compositions=None, progress=None):
    """Compose the Gerbers once, retaining full geometry for every detail level."""
    layers = [layer for layer in layers if layer.objects]
    if not layers:
        raise ValueError("Abra as camadas da PCB para visualizar em 3D.")
    memo = GeometryMemo(previous)
    notify = progress or (lambda *_: None)
    notify(1, "Preparando camadas 3D…")
    cache, compositions = cache or {}, compositions or {}
    outline_layers = [
        layer for layer in layers if canonical_function(layer.function) == "Edge.Cuts"
    ]
    board = memo.get(
        "outline",
        tuple((layer.id, layer.signature()) for layer in outline_layers),
        (),
        lambda: outline_geometry(outline_layers),
    )
    routes, drills = [], []
    notify(5, "Preparando contorno…")
    for index, layer in enumerate(layers):
        role = canonical_function(layer.function)
        if role == "Route.Cuts":
            routes.append(
                memo.get(
                    ("route", layer.id),
                    layer.signature(),
                    (),
                    lambda layer=layer: routing_geometry(layer.objects),
                )
            )
        elif role in DRILL_ROLES:
            drills.append(
                memo.get(
                    ("drill", layer.id),
                    (role, layer.attributes, layer.signature()),
                    (),
                    lambda layer=layer: drill_geometry([layer], cache),
                )
            )
        notify(5 + int(15 * (index + 1) / len(layers)), "Preparando furação e recortes…")
    layers = [layer for layer in layers if layer.visible]
    estimated = board.is_empty
    if estimated:
        bounds = [
            bound
            for layer in layers
            if (
                bound := memo.get(
                    ("bounds", layer.id), layer.signature(), (), lambda layer=layer: layer.bounds
                )
            )
            is not None
        ]
        if not bounds:
            raise ValueError("Abra as camadas da PCB para visualizar em 3D.")
        extents = (
            min(b.left for b in bounds) - 1,
            min(b.bottom for b in bounds) - 1,
            max(b.right for b in bounds) + 1,
            max(b.top for b in bounds) + 1,
        )
        board = memo.get("estimated_outline", extents, (), lambda: box(*extents))
    images = []
    for index, layer in enumerate(layers):
        notify(20 + int(35 * index / max(1, len(layers))), "Compondo camadas 3D…")
        role = canonical_function(layer.function)
        if role in DRILL_ROLES or role in (
            "Edge.Cuts",
            "Route.Cuts",
            "Mechanical",
            "Drill drawing",
        ):
            continue

        def compose(layer=layer):
            snapshot = compositions.get(layer.id)
            if snapshot is not None and snapshot[0] == layer.signature():
                # Spatial cells already respect dark/clear order. Their clipped
                # GEOS images can be joined without replaying all Gerber objects.
                geometry = (
                    unary_union(snapshot[1]) if isinstance(snapshot[1], tuple) else snapshot[1]
                )
            else:
                geometries = {
                    obj.id: cache[obj.id][1]
                    if obj.id in cache and cache[obj.id][0] == obj
                    else object_geometry(obj)
                    for obj in layer.objects
                }
                geometry = compose_layer(layer.objects, geometries)
            return make_valid(geometry)

        images.append(
            LayerGeometry(
                layer.id,
                layer.name,
                role,
                memo.get(("image", layer.id), layer.signature(), (), compose),
            )
        )
    notify(58, "Finalizando geometria 3D…")
    return BoardGeometry(
        memo.get("valid_outline", None, (board,), lambda: make_valid(board)),
        memo.get("routes", None, tuple(routes), lambda: unary_union(routes)),
        memo.get("drills", None, tuple(drills), lambda: unary_union(drills)),
        tuple(images),
        estimated,
        memo.current,
    )


def build_board(layers, thickness=1.6, cache=None, tolerance=0.025, previous=None, progress=None):
    """Generate a mesh from source layers or a previously prepared PCB."""
    prepared = (
        layers
        if isinstance(layers, BoardGeometry)
        else prepare_board(layers, cache, progress=progress)
    )
    notify = progress or (lambda *_: None)
    layers = prepared.layers
    memo = GeometryMemo(previous)

    def cut_board():
        board = prepared.outline.simplify(tolerance, preserve_topology=True)
        if not prepared.routes.is_empty:
            board = make_valid(board.difference(prepared.routes)).simplify(
                tolerance, preserve_topology=True
            )
        if not prepared.drills.is_empty:
            # Drill after display simplification: the coarse preview must keep
            # small holes and their actual diameter.
            board = make_valid(board.difference(prepared.drills))
        return board

    notify(60, "Recortando substrato…")
    board = memo.get(
        "board", tolerance, (prepared.outline, prepared.routes, prepared.drills), cut_board
    )
    if board.is_empty or board.area == 0:
        raise ValueError("Os recortes removem toda a PCB.")
    left, bottom, right, top = board.bounds
    center = ((left + right) / 2, (bottom + top) / 2)
    notify(68, "Gerando malha do substrato…")
    parts = [
        memo.get(
            "substrate",
            (thickness, center),
            (board,),
            lambda: MeshPart(
                "substrate",
                "Substrato FR4",
                substrate(board, thickness, center),
                (0.48, 0.42, 0.20),
                board,
                -thickness / 2,
                thickness / 2,
                "fr4",
            ),
        )
    ]
    inner = sorted(
        {layer.role for layer in layers if re.match(r"In\d+\.Cu", layer.role)},
        key=lambda value: int(re.search(r"\d+", value)[0]),
    )
    images = {}
    for index, layer in enumerate(layers):
        notify(78 + int(7 * index / max(1, len(layers))), "Preparando superfícies 3D…")
        images[layer.key] = memo.get(
            ("image", layer.key),
            tolerance,
            (layer.geometry, board),
            lambda layer=layer: make_valid(
                layer.geometry.simplify(tolerance, preserve_topology=True).intersection(board)
            ),
        )
    mask_sides = {
        "B" if layer.role.startswith("B.") else "F"
        for layer in layers
        if layer.role.endswith(".Mask")
    }
    copper_by_side = {
        side: memo.get(
            ("copper", side),
            None,
            tuple(images[layer.key] for layer in layers if layer.role == side + ".Cu"),
            lambda side=side: unary_union(
                [images[layer.key] for layer in layers if layer.role == side + ".Cu"]
            ),
        )
        for side in mask_sides
    }
    for index, layer in enumerate(layers):
        notify(85 + int(14 * index / max(1, len(layers))), "Gerando malhas das camadas…")
        role = layer.role
        shape = images[layer.key]
        sign = -1 if role.startswith("B.") else 1
        z, color, material = sign * (thickness / 2 + 0.035), (0.72, 0.52, 0.20), "copper"
        height = 0.035
        if role.endswith(".Mask"):
            copper = copper_by_side["B" if sign < 0 else "F"]

            def mask_shapes(shape=shape, copper=copper):
                covered = board.difference(shape)
                return make_valid(covered.intersection(copper)), make_valid(
                    covered.difference(copper)
                )

            coated, shape = memo.get(("mask", layer.key), None, (board, shape, copper), mask_shapes)
            if not coated.is_empty and coated.area > 0:
                coated_z = sign * (thickness / 2 + 0.055)
                parts.append(
                    layer_part(
                        memo,
                        ("coated", layer.key),
                        layer,
                        coated,
                        coated_z,
                        sign,
                        center,
                        (0.035, 0.40, 0.155),
                        0.020,
                        "mask",
                    )
                )
            z, color, material, height = (
                sign * (thickness / 2 + 0.020),
                (0.025, 0.30, 0.105),
                "mask",
                0.020,
            )
        elif role.endswith(".Silk"):
            z, color, material, height = (
                sign * (thickness / 2 + 0.070),
                (0.95, 0.96, 0.91),
                "silk",
                0.015,
            )
        elif role.endswith(".Paste"):
            z, color, material, height = (
                sign * (thickness / 2 + 0.090),
                (0.64, 0.68, 0.70),
                "paste",
                0.025,
            )
        elif role in inner:
            z = thickness / 2 - thickness * (inner.index(role) + 1) / (len(inner) + 1)
        part = layer_part(
            memo,
            ("part", layer.key),
            layer,
            shape,
            z,
            sign,
            center,
            color,
            height,
            material,
        )
        if len(part.vertices):
            parts.append(part)
        if sum(len(part.vertices) for part in parts) > 3600000:
            raise ValueError("Modelo 3D muito grande. Oculte camadas ou aumente a tolerância 3D.")
    notify(99, "Concluindo PCB 3D…")
    return BoardMesh(
        parts,
        center,
        (right - left, top - bottom, thickness),
        prepared.estimated_outline,
        sum(len(part.vertices) // 3 for part in parts),
        board,
        memo.current,
    )
