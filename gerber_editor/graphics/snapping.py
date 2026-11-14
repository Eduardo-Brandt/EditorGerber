"""Screen-space point magnets and exact 45/90-degree construction constraints."""

import math
from decimal import Decimal as D

from PySide6.QtCore import QPointF, QRectF

from gerber_editor.core.primitives import Arc, Flash, Point, Region
from gerber_editor.graphics.graphics_items import ObjectItem
from gerber_editor.tools.shapes import point_on_grid


def object_points(obj):
    g = obj.geometry
    if isinstance(g, Flash):
        return (g.position,)
    if isinstance(g, Region):
        return tuple(c.start for contour in g.contours for c in contour)
    if isinstance(g, Arc):
        start, sweep = g.angles()
        points = [g.start, g.end, g.center]
        half = (D(1) / 2).sqrt()
        directions = (
            (D(1), D(0)),
            (half, half),
            (D(0), D(1)),
            (-half, half),
            (D(-1), D(0)),
            (-half, -half),
            (D(0), D(-1)),
            (half, -half),
        )
        for i, (c, s) in enumerate(directions):
            angle = i * math.pi / 4
            distance = ((angle - start) if sweep > 0 else (start - angle)) % math.tau
            if distance <= abs(sweep) + 1e-10:
                points.append(Point(g.center.x + g.radius * c, g.center.y + g.radius * s))
        return tuple(points)
    return (g.start, g.end, Point((g.start.x + g.end.x) / 2, (g.start.y + g.end.y) / 2))


def constrain(point, anchor, angle):
    dx, dy = point.x - anchor.x, point.y - anchor.y
    direction = int(math.floor(math.degrees(math.atan2(float(dy), float(dx))) / angle + 0.5))
    index = direction % (360 // angle)
    if angle == 90:
        return Point(point.x, anchor.y) if index % 2 == 0 else Point(anchor.x, point.y)
    if index % 2 == 0:
        return Point(point.x, anchor.y) if index % 4 == 0 else Point(anchor.x, point.y)
    sx, sy = (1 if index in (1, 7) else -1), (1 if index in (1, 3) else -1)
    length = (dx * sx + dy * sy) / 2
    return Point(anchor.x + length * sx, anchor.y + length * sy)


def resolve(canvas, position, reference=None):
    point = Point(D(str(position.x())), D(str(position.y())))
    anchor = reference or canvas.constraint_anchor()
    ortho = canvas._shift_held and canvas.mode != "select"
    if ortho:
        point = constrain(point, anchor, canvas.ortho_angle)
    target = None
    radius = 12 / max(abs(canvas.transform().m11()), 0.0001)
    if canvas.snap_points and canvas._pan is None:
        center = QPointF(float(point.x), float(point.y))
        nearest = radius * radius
        for item in canvas.scene().items(
            QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        ):
            if (
                not isinstance(item, ObjectItem)
                or not item.isVisible()
                or item.obj.id in canvas.snap_excluded
            ):
                continue
            for candidate in object_points(item.obj):
                dx, dy = float(candidate.x - point.x), float(candidate.y - point.y)
                distance = dx * dx + dy * dy
                if distance <= nearest:
                    if ortho:
                        projected = constrain(candidate, anchor, canvas.ortho_angle)
                        if (
                            math.hypot(
                                float(projected.x - candidate.x), float(projected.y - candidate.y)
                            )
                            > float(canvas.quantum_mm) * 1.5
                        ):
                            continue
                    nearest, target = distance, candidate
    canvas.snap_target = target
    if target:
        return point_on_grid(target.x, target.y, canvas.quantum_mm)
    if canvas.snap_grid:
        point = point_on_grid(point.x, point.y, canvas.grid_mm)
        if ortho:
            point = constrain(point, anchor, canvas.ortho_angle)
    return point_on_grid(point.x, point.y, canvas.quantum_mm)
