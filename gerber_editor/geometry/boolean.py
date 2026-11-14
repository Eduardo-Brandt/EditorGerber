"""Lazy display geometry. Polygon approximation is never used for Gerber export."""

from __future__ import annotations

import math
from functools import lru_cache

from shapely import affinity
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import unary_union

from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line, Region
from gerber_editor.geometry.regions import cutin_polygon
from gerber_editor.gerber.errors import GerberError

DISPLAY_TOLERANCE_MM = 0.001


def quad_segments(radius: float) -> int:
    """Keep chord error below the display tolerance without oversized pad meshes."""
    angle = math.acos(max(-1.0, 1 - min(DISPLAY_TOLERANCE_MM / radius, 1.0)))
    return max(4, min(256, math.ceil(math.pi / (4 * angle))))


def curve_points(curve: Line | Arc) -> list[tuple[float, float]]:
    if isinstance(curve, Line):
        return [
            (float(curve.start.x), float(curve.start.y)),
            (float(curve.end.x), float(curve.end.y)),
        ]
    angle, sweep = curve.angles()
    radius = float(curve.radius)
    step = 2 * math.acos(max(-1.0, 1 - min(DISPLAY_TOLERANCE_MM / radius, 1.0)))
    count = max(4, min(16384, math.ceil(abs(sweep) / max(step, 1e-6))))
    points = [
        (
            float(curve.center.x) + radius * math.cos(angle + sweep * i / count),
            float(curve.center.y) + radius * math.sin(angle + sweep * i / count),
        )
        for i in range(count + 1)
    ]
    points[0] = (float(curve.start.x), float(curve.start.y))
    points[-1] = (float(curve.end.x), float(curve.end.y))
    return points


@lru_cache(maxsize=4096)
def aperture_shape(ap: Aperture):
    if ap.macro:
        return macro_shape(ap.macro)
    p = [float(v) for v in ap.parameters]
    if ap.shape == "C" and p[0] == 0:
        return GeometryCollection()
    if ap.shape == "C":
        shape = Point(0, 0).buffer(p[0] / 2, quad_segs=quad_segments(p[0] / 2))
    elif ap.shape == "R":
        shape = box(-p[0] / 2, -p[1] / 2, p[0] / 2, p[1] / 2)
    elif ap.shape == "O":
        radius = min(p[0], p[1]) / 2
        dx, dy = max(0, p[0] / 2 - radius), max(0, p[1] / 2 - radius)
        shape = LineString([(-dx, -dy), (dx, dy)]).buffer(radius, quad_segs=quad_segments(radius))
    else:
        count = int(p[1])
        rotation = math.radians(p[2] if len(p) > 2 else 0)
        shape = Polygon(
            [
                (
                    p[0] / 2 * math.cos(rotation + i * math.tau / count),
                    p[0] / 2 * math.sin(rotation + i * math.tau / count),
                )
                for i in range(count)
            ]
        )
    hole_index = {"C": 1, "R": 2, "O": 2, "P": 3}[ap.shape]
    if len(p) > hole_index and p[hole_index] > 0:
        shape = shape.difference(
            Point(0, 0).buffer(p[hole_index] / 2, quad_segs=quad_segments(p[hole_index] / 2))
        )
    return shape


def macro_shape(primitives):
    result = GeometryCollection()
    for primitive in primitives:
        p = [float(v) for v in primitive.values]
        if primitive.code == 1:
            shape = Point(p[2], p[3]).buffer(p[1] / 2, quad_segs=quad_segments(p[1] / 2))
        elif primitive.code == 4:
            shape = Polygon(list(zip(p[2:-1:2], p[3:-1:2], strict=True)))
            if not shape.is_valid or shape.area == 0:
                raise GerberError("Outline de macro inválido; nenhum reparo aplicado.")
        elif primitive.code == 5:
            count = int(p[1])
            shape = Polygon(
                [
                    (
                        p[2] + p[4] / 2 * math.cos(i * math.tau / count),
                        p[3] + p[4] / 2 * math.sin(i * math.tau / count),
                    )
                    for i in range(count)
                ]
            )
        elif primitive.code == 20:
            shape = LineString([(p[2], p[3]), (p[4], p[5])]).buffer(p[1] / 2, cap_style=2)
        else:
            cx, cy = p[3], p[4]
            if primitive.code == 22:
                cx, cy = cx + p[1] / 2, cy + p[2] / 2
            shape = box(cx - p[1] / 2, cy - p[2] / 2, cx + p[1] / 2, cy + p[2] / 2)
        shape = affinity.rotate(shape, p[-1], origin=(0, 0))
        result = result.union(shape) if p[0] == 1 else result.difference(shape)
    return result


def object_geometry(obj: GerberObject):
    geometry = obj.geometry
    if isinstance(geometry, Region):
        result = GeometryCollection()
        for contour in geometry.contours:
            points = []
            for curve in contour:
                part = curve_points(curve)
                points.extend(part if not points else part[1:])
            polygon = Polygon(points)
            if not polygon.is_valid:
                polygon = cutin_polygon(contour, curve_points)
            if polygon.is_empty or polygon.area == 0:
                raise GerberError("Região inválida/auto-intersectante; nenhum reparo aplicado.")
            # Ucamco 4.10.1: G36/G37 fills each contour independently, then
            # unions the filled regions. A nested contour is not a hole.
            result = result.union(polygon)
        return result
    ap = obj.aperture
    # A zero-diameter circular aperture has no image effect (Ucamco 4.3.3).
    if ap.shape == "C" and ap.width == 0:
        return GeometryCollection()
    if isinstance(geometry, Flash):
        return affinity.translate(
            aperture_shape(ap), float(geometry.position.x), float(geometry.position.y)
        )
    points = curve_points(geometry)
    if ap.shape == "C":
        if all(point == points[0] for point in points):
            return Point(points[0]).buffer(
                float(ap.width) / 2, quad_segs=quad_segments(float(ap.width) / 2)
            )
        return LineString(points).buffer(
            float(ap.width) / 2, quad_segs=quad_segments(float(ap.width) / 2)
        )
    base = aperture_shape(ap)
    # Convex fixed-orientation aperture swept over each sampled segment.
    shapes = []
    for start, end in zip(points, points[1:], strict=False):
        a = affinity.translate(base, *start)
        b = affinity.translate(base, *end)
        shapes.append(unary_union([a, b]).convex_hull)
    return unary_union(shapes)


def compose_layer(objects: list, geometries: dict):
    result = GeometryCollection()
    pending = []
    polarity = None
    for obj in objects:
        if not obj.visible:
            continue
        if polarity is not None and polarity != obj.polarity:
            group = unary_union(pending)
            result = result.union(group) if polarity == Polarity.DARK else result.difference(group)
            pending = []
        polarity = obj.polarity
        pending.append(geometries[obj.id])
    if pending:
        group = unary_union(pending)
        result = result.union(group) if polarity == Polarity.DARK else result.difference(group)
    return result
