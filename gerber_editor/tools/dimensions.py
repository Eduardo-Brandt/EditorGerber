"""Aligned dimensions are exported as ordinary lines, arrows and vector text."""

import math
from decimal import Decimal

from gerber_editor.core.objects import GerberObject, Polarity
from gerber_editor.core.primitives import Line, Region
from gerber_editor.core.units import Unit
from gerber_editor.tools.drawing import circular_aperture
from gerber_editor.tools.shapes import layer_quantum, point_on_grid
from gerber_editor.tools.vector_text import vector_text


def create_dimension(
    layer,
    start,
    end,
    location,
    *,
    arrow_mm: Decimal,
    text_mm: Decimal,
    width_mm: Decimal,
    family="Segoe UI",
    unit="mm",
    decimals=3,
    polar=False,
    polarity=Polarity.DARK,
):
    dx, dy = float(end.x - start.x), float(end.y - start.y)
    distance = math.hypot(dx, dy)
    if distance == 0 or min(arrow_mm, text_mm, width_mm) <= 0:
        raise ValueError("Dimension needs distinct points and positive sizes.")
    ux, uy = dx / distance, dy / distance
    nx, ny = -uy, ux
    offset = float(location.x - start.x) * nx + float(location.y - start.y) * ny
    if abs(offset) < float(text_mm):
        offset = float(text_mm) * 2 * (1 if offset >= 0 else -1)
    q = layer_quantum(layer)

    def p(x, y):
        return point_on_grid(x, y, q)

    a = p(float(start.x) + nx * offset, float(start.y) + ny * offset)
    b = p(float(end.x) + nx * offset, float(end.y) + ny * offset)
    extension = float(text_mm) * 0.3 * (1 if offset >= 0 else -1)
    ap = circular_aperture(layer, width_mm)
    curves = [
        Line(start, p(float(a.x) + nx * extension, float(a.y) + ny * extension)),
        Line(end, p(float(b.x) + nx * extension, float(b.y) + ny * extension)),
        Line(a, b),
    ]
    result = [GerberObject(curve, ap, polarity) for curve in curves]
    arrow = float(arrow_mm)
    for tip, direction in [(a, 1), (b, -1)]:
        x, y = float(tip.x) + ux * arrow * direction, float(tip.y) + uy * arrow * direction
        left, right = (
            p(x + nx * arrow * 0.3, y + ny * arrow * 0.3),
            p(x - nx * arrow * 0.3, y - ny * arrow * 0.3),
        )
        if tip != left and left != right and right != tip:
            result.append(
                GerberObject(
                    Region(((Line(tip, left), Line(left, right), Line(right, tip)),)),
                    None,
                    polarity,
                )
            )
    exact_distance = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2).sqrt()
    label = f"{Unit(unit).from_mm(exact_distance):.{decimals}f} {unit}"
    angle = math.degrees(math.atan2(dy, dx))
    if polar:
        label += f" / {angle:.2f}°"
    rotation = angle if -90 <= angle <= 90 else angle + 180
    label_position = p(
        (float(a.x + b.x) / 2) + nx * float(text_mm) * 0.35,
        (float(a.y + b.y) / 2) + ny * float(text_mm) * 0.35,
    )
    result += vector_text(
        layer,
        label,
        label_position,
        text_mm,
        width_mm,
        family,
        rotation=rotation,
        centered=True,
        polarity=polarity,
        reserved_apertures=(ap,),
    )
    return result
