"""Recognize canonical shapes from fabrication geometry, including reopened files."""

import math
from dataclasses import dataclass, replace
from decimal import Decimal as D
from uuid import uuid4

from gerber_editor.core.primitives import Arc, Line, Point, Region
from gerber_editor.tools.drawing import circular_aperture
from gerber_editor.tools.object_properties import edit_object
from gerber_editor.tools.shapes import layer_quantum, point_on_grid


@dataclass
class EditableShape:
    layer: object
    objects: list
    kind: str
    values: dict


def arc_geometry(g):
    if isinstance(g, Arc):
        return g, False
    if isinstance(g, Region) and len(g.contours) == 1:
        contour = g.contours[0]
        if len(contour) == 1 and isinstance(contour[0], Arc) and contour[0].start == contour[0].end:
            return contour[0], True
        if len(contour) == 3:
            for index, curve in enumerate(contour):
                if isinstance(curve, Arc):
                    following, last = contour[(index + 1) % 3], contour[(index + 2) % 3]
                    if (
                        isinstance(following, Line)
                        and isinstance(last, Line)
                        and following.start == curve.end
                        and following.end == curve.center
                        and last.start == curve.center
                        and last.end == curve.start
                    ):
                        return curve, True
    return None


def recognize(layer, objects):
    first = objects[0]
    if any(
        o.polarity != first.polarity or o.attributes != first.attributes or o.text_entity
        for o in objects
    ):
        return None
    if len(objects) == 1 and (arc := arc_geometry(first.geometry)):
        if first.aperture and (first.aperture.shape != "C" or len(first.aperture.parameters) != 1):
            return None
        g, filled = arc
        angle, sweep = g.angles()
        return EditableShape(
            layer,
            objects,
            "circle" if g.start == g.end else "arc",
            dict(
                cx=g.center.x,
                cy=g.center.y,
                radius=g.radius,
                start_angle=D(str(math.degrees(angle))),
                sweep=D(str(abs(math.degrees(sweep)))),
                clockwise=g.clockwise,
                filled=filled,
                width=first.aperture.width if first.aperture else D("0.2"),
            ),
        )
    if (
        len(objects) == 1
        and isinstance(first.geometry, Region)
        and len(first.geometry.contours) == 1
    ):
        edges = list(first.geometry.contours[0])
        filled = True
    elif len(objects) == 4 and all(isinstance(o.geometry, Line) for o in objects):
        edges, filled = [o.geometry for o in objects], False
        if (
            not first.aperture
            or first.aperture.shape != "C"
            or len(first.aperture.parameters) != 1
            or any(o.aperture != first.aperture for o in objects)
        ):
            return None
    else:
        return None
    if len(edges) != 4 or not all(isinstance(e, Line) for e in edges):
        return None
    if any(a.end != b.start for a, b in zip(edges, edges[1:] + edges[:1], strict=True)):
        return None
    a, b, c, d = [edge.start for edge in edges]
    u, v = Point(b.x - a.x, b.y - a.y), Point(d.x - a.x, d.y - a.y)
    width, height = (u.x * u.x + u.y * u.y).sqrt(), (v.x * v.x + v.y * v.y).sqrt()
    tolerance = layer_quantum(layer) * max(width, height, D(1)) * 4
    if (
        width == 0
        or height == 0
        or abs(u.x * v.x + u.y * v.y) > tolerance
        or c != Point(b.x + d.x - a.x, b.y + d.y - a.y)
    ):
        return None
    return EditableShape(
        layer,
        objects,
        "rectangle",
        dict(
            cx=(a.x + c.x) / 2,
            cy=(a.y + c.y) / 2,
            size_x=width,
            size_y=height,
            rotation=D(str(math.degrees(math.atan2(float(u.y), float(u.x))))),
            filled=filled,
            width=first.aperture.width if first.aperture else D("0.2"),
        ),
    )


def shape_selection(items):
    """Partition selected objects into independent shapes, without merging groups."""
    by_layer = {}
    for item in items:
        by_layer.setdefault(item.layer.id, (item.layer, []))[1].append(item.obj)
    result = []
    for layer, ordered in by_layer.values():
        outgoing = {}
        for obj in ordered:
            if isinstance(obj.geometry, Line):
                outgoing.setdefault(obj.geometry.start, []).append(obj)
        used = set()
        for obj in ordered:
            if obj.id in used:
                continue
            shape = recognize(layer, [obj])
            if shape is None and isinstance(obj.geometry, Line):
                edges = [obj]
                while len(edges) < 4:
                    candidates = [
                        o
                        for o in outgoing.get(edges[-1].geometry.end, [])
                        if o.id not in used and o not in edges
                    ]
                    if len(candidates) != 1:
                        break
                    edges.append(candidates[0])
                shape = recognize(layer, edges)
            if shape is None:
                return None
            result.append(shape)
            used.update(o.id for o in shape.objects)
    return result if result and len({s.kind for s in result}) == 1 else None


def edit_shape(shape, changes):
    values = {**shape.values, **changes}
    first, layer = shape.objects[0], shape.layer
    q = layer_quantum(layer)
    aperture = (
        replace(first.aperture, parameters=(values["width"],))
        if first.aperture
        else circular_aperture(layer, values["width"])
    )
    if shape.kind in ("arc", "circle"):
        g, _ = arc_geometry(first.geometry)
        surrogate = replace(
            first, geometry=g, aperture=first.aperture or circular_aperture(layer, values["width"])
        )
        geometry_changes = set(changes) - {"filled", "width"}
        if geometry_changes:
            g = edit_object(layer, surrogate, {**values, "_changed": geometry_changes}).geometry
        if values["filled"]:
            geometry = (
                Region(((g,),))
                if g.start == g.end
                else Region(((g, Line(g.end, g.center), Line(g.center, g.start)),))
            )
            objects = [replace(first, geometry=geometry, aperture=None)]
        else:
            objects = [replace(first, geometry=g, aperture=aperture)]
    else:
        if values["size_x"] <= 0 or values["size_y"] <= 0:
            raise ValueError("As dimensões devem ser positivas.")
        angle = math.radians(values["rotation"])
        c, s = D(str(math.cos(angle))), D(str(math.sin(angle)))
        points = [
            point_on_grid(values["cx"] + x * c - y * s, values["cy"] + x * s + y * c, q)
            for x, y in [
                (-values["size_x"] / 2, -values["size_y"] / 2),
                (values["size_x"] / 2, -values["size_y"] / 2),
                (values["size_x"] / 2, values["size_y"] / 2),
                (-values["size_x"] / 2, values["size_y"] / 2),
            ]
        ]
        curves = tuple(Line(a, b) for a, b in zip(points, points[1:] + points[:1], strict=True))
        if not (set(changes) - {"filled", "width"}):
            curves = (
                shape.objects[0].geometry.contours[0]
                if isinstance(shape.objects[0].geometry, Region)
                else tuple(o.geometry for o in shape.objects)
            )
        if values["filled"]:
            objects = [replace(first, geometry=Region((curves,)), aperture=None)]
        else:
            group = first.group_id or uuid4().hex
            objects = [
                replace(
                    first,
                    geometry=curve,
                    aperture=aperture,
                    id=shape.objects[i].id if i < len(shape.objects) else uuid4().hex,
                    group_id=group,
                )
                for i, curve in enumerate(curves)
            ]
    if any(o.aperture and o.aperture.width <= 0 for o in objects):
        raise ValueError("A espessura deve ser positiva.")
    return objects
