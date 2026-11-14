"""Original compact monoline font. Glyph paths become ordinary Gerber lines.

Glyph coordinates use a 6 x 10 grid. Lowercase is rendered as uppercase,
explicitly advertised by the text dialog. Unsupported characters are refused.
"""

from decimal import Decimal

from gerber_editor.core.objects import GerberObject, Polarity
from gerber_editor.core.primitives import Line, Point
from gerber_editor.tools.drawing import circular_aperture

GLYPHS = {
    "A": "0,0 0,7 3,10 6,7 6,0|0,4 6,4",
    "B": "0,0 0,10 4,10 6,8 6,7 4,5 0,5|4,5 6,3 6,2 4,0 0,0",
    "C": "6,9 4,10 2,10 0,8 0,2 2,0 4,0 6,1",
    "D": "0,0 0,10 3,10 6,7 6,3 3,0 0,0",
    "E": "6,10 0,10 0,0 6,0|0,5 5,5",
    "F": "0,0 0,10 6,10|0,5 5,5",
    "G": "6,9 4,10 2,10 0,8 0,2 2,0 6,0 6,5 3,5",
    "H": "0,0 0,10|6,0 6,10|0,5 6,5",
    "I": "0,10 6,10|3,10 3,0|0,0 6,0",
    "J": "0,2 2,0 4,0 6,2 6,10",
    "K": "0,0 0,10|6,10 0,5 6,0",
    "L": "0,10 0,0 6,0",
    "M": "0,0 0,10 3,5 6,10 6,0",
    "N": "0,0 0,10 6,0 6,10",
    "O": "2,0 0,2 0,8 2,10 4,10 6,8 6,2 4,0 2,0",
    "P": "0,0 0,10 4,10 6,8 6,7 4,5 0,5",
    "Q": "2,0 0,2 0,8 2,10 4,10 6,8 6,2 4,0 2,0|3,3 6,0",
    "R": "0,0 0,10 4,10 6,8 6,7 4,5 0,5|3,5 6,0",
    "S": "6,9 4,10 2,10 0,8 0,7 2,5 4,5 6,3 6,2 4,0 2,0 0,1",
    "T": "0,10 6,10|3,10 3,0",
    "U": "0,10 0,2 2,0 4,0 6,2 6,10",
    "V": "0,10 3,0 6,10",
    "W": "0,10 1,0 3,5 5,0 6,10",
    "X": "0,0 6,10|0,10 6,0",
    "Y": "0,10 3,5 6,10|3,5 3,0",
    "Z": "0,10 6,10 0,0 6,0",
    "0": "2,0 0,2 0,8 2,10 4,10 6,8 6,2 4,0 2,0|0,2 6,8",
    "1": "1,8 3,10 3,0|0,0 6,0",
    "2": "0,8 2,10 4,10 6,8 6,6 0,0 6,0",
    "3": "0,10 4,10 6,8 6,7 4,5 2,5|4,5 6,3 6,2 4,0 0,0",
    "4": "5,0 5,10 0,3 6,3",
    "5": "6,10 0,10 0,5 4,5 6,3 6,2 4,0 0,0",
    "6": "6,9 4,10 2,10 0,7 0,2 2,0 4,0 6,2 6,4 4,6 0,6",
    "7": "0,10 6,10 2,0",
    "8": "2,5 0,7 0,8 2,10 4,10 6,8 6,7 4,5 2,5 0,3 0,2 2,0 4,0 6,2 6,3 4,5",
    "9": "6,4 2,4 0,6 0,8 2,10 4,10 6,8 6,2 4,0 1,0",
    "-": "0,5 6,5",
    "_": "0,0 6,0",
    ".": "3,0 3,1",
    ":": "3,2 3,3|3,7 3,8",
    "/": "0,0 6,10",
    "+": "0,5 6,5|3,2 3,8",
    "=": "0,3 6,3|0,7 6,7",
    "(": "4,10 2,8 2,2 4,0",
    ")": "2,10 4,8 4,2 2,0",
    "[": "4,10 2,10 2,0 4,0",
    "]": "2,10 4,10 4,0 2,0",
    " ": "",
    "°": "2,8 2,10 4,10 4,8 2,8",
}


def create_text(
    layer,
    text: str,
    position: Point,
    height: Decimal,
    stroke: Decimal,
    polarity: Polarity = Polarity.DARK,
) -> list[GerberObject]:
    if not text.strip() or not height.is_finite() or height <= 0:
        raise ValueError("Informe texto e altura positiva.")
    text = text.upper()
    unsupported = sorted(set(text) - GLYPHS.keys())
    if unsupported:
        raise ValueError(f"Caracteres não suportados pela fonte stroke: {''.join(unsupported)}")
    ap = circular_aperture(layer, stroke)
    unit = height / 10
    result = []
    for index, char in enumerate(text):
        for polyline in filter(None, GLYPHS[char].split("|")):
            points = []
            for coordinate in polyline.split():
                x, y = (Decimal(n) for n in coordinate.split(","))
                points.append(Point(position.x + (x + 8 * index) * unit, position.y + y * unit))
            result.extend(
                GerberObject(Line(a, b), ap, polarity)
                for a, b in zip(points, points[1:], strict=False)
            )
    return result
