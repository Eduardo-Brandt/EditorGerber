"""Exact translations of logical primitives, without polygon conversion."""

from decimal import Decimal

from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region


def translate_geometry(geometry, dx: Decimal, dy: Decimal):
    def point(value: Point) -> Point:
        return Point(value.x + dx, value.y + dy)

    if not dx.is_finite() or not dy.is_finite():
        raise ValueError("Deslocamento deve ser finito.")
    if isinstance(geometry, Flash):
        return Flash(point(geometry.position))
    if isinstance(geometry, Line):
        return Line(point(geometry.start), point(geometry.end))
    if isinstance(geometry, Arc):
        return Arc(
            point(geometry.start), point(geometry.end), point(geometry.center), geometry.clockwise
        )
    if isinstance(geometry, Region):
        return Region(
            tuple(
                tuple(translate_geometry(curve, dx, dy) for curve in contour)
                for contour in geometry.contours
            )
        )
    raise TypeError(f"Geometria não suportada: {type(geometry).__name__}")
