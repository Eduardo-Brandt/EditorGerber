"""Creation helpers shared by UI and tests."""

from decimal import Decimal

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Line, Point


def circular_aperture(layer: GerberLayer, width: Decimal) -> Aperture:
    if not width.is_finite() or width <= 0:
        raise ValueError("Espessura deve ser positiva.")
    all_apertures = dict(layer.apertures)
    all_apertures.update({o.aperture.code: o.aperture for o in layer.objects if o.aperture})
    for ap in all_apertures.values():
        if ap.shape == "C" and ap.parameters == (width,) and not ap.attributes:
            return ap
    return Aperture(max([9, *all_apertures]) + 1, "C", (width,))


def create_line(
    layer: GerberLayer, start: Point, end: Point, width: Decimal, polarity: Polarity = Polarity.DARK
) -> GerberObject:
    if start == end:
        raise ValueError("A linha deve ter comprimento maior que zero.")
    return GerberObject(Line(start, end), circular_aperture(layer, width), polarity)
