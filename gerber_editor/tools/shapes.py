"""Exact logical drawing helpers. New geometry is rounded to the layer's grid."""

from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from gerber_editor.core.objects import GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Line, Point, Region
from gerber_editor.tools.drawing import circular_aperture

D = Decimal


def layer_quantum(layer) -> Decimal:
    if layer.source:
        return layer.source.unit_scale * D(1).scaleb(-layer.source.coordinate_format.decimal)
    return D("0.000001")


def rounded(value: Decimal, quantum: Decimal) -> Decimal:
    return (value / quantum).to_integral_value(rounding=ROUND_HALF_UP) * quantum


def point_on_grid(x, y, quantum):
    return Point(rounded(D(str(x)), quantum), rounded(D(str(y)), quantum))


def rectangle_region(start: Point, end: Point) -> Region:
    if start.x == end.x or start.y == end.y:
        raise ValueError("Rectangle must have positive width and height.")
    points = (start, Point(end.x, start.y), end, Point(start.x, end.y), start)
    return Region((tuple(Line(a, b) for a, b in zip(points, points[1:], strict=False)),))


def create_shape(
    layer,
    kind: str,
    points: list[Point],
    width: Decimal,
    polarity=Polarity.DARK,
    clockwise=False,
    filled=False,
) -> list[GerberObject]:
    quantum = layer_quantum(layer)
    points = [point_on_grid(p.x, p.y, quantum) for p in points]
    aperture = circular_aperture(layer, width)
    start, end = points[:2]
    if kind in ("rectangle", "square"):
        if kind == "square":
            size = max(abs(end.x - start.x), abs(end.y - start.y))
            end = Point(
                start.x + (size if end.x >= start.x else -size),
                start.y + (size if end.y >= start.y else -size),
            )
        region = rectangle_region(start, end)
        if filled:
            return [GerberObject(region, None, polarity)]
        group = uuid4().hex
        return [
            GerberObject(curve, aperture, polarity, group_id=group) for curve in region.contours[0]
        ]
    radius = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2).sqrt()
    radius = rounded(radius, quantum)
    if radius <= 0:
        raise ValueError("Radius must be positive.")
    if kind == "circle":
        point = Point(start.x + radius, start.y)
        arc = Arc(point, point, start, False)
        return [
            GerberObject(
                Region(((arc,),)) if filled else arc, None if filled else aperture, polarity
            )
        ]
    if kind == "arc":
        target = points[2]
        dx, dy = target.x - start.x, target.y - start.y
        distance = (dx**2 + dy**2).sqrt()
        if distance == 0:
            raise ValueError("Arc endpoint cannot be its center.")
        # Preserve the chosen start point exactly. Project only the newly
        # created endpoint onto the radius and then onto the output grid.
        radius = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2).sqrt()
        target = point_on_grid(
            start.x + dx * radius / distance, start.y + dy * radius / distance, quantum
        )
        if target == end:
            raise ValueError(
                "Arc needs distinct start and end points; use Circle for a full circle."
            )
        arc = Arc(end, target, start, clockwise)
        geometry = Region(((arc, Line(target, start), Line(start, end)),)) if filled else arc
        return [GerberObject(geometry, None if filled else aperture, polarity)]
    raise ValueError(f"Unknown drawing shape: {kind}")
