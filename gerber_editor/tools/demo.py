"""Synthetic industrial silkscreen, deliberately separated from user files."""

from decimal import Decimal as D

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject
from gerber_editor.core.primitives import Flash, Line, Point, Region
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.tools.drawing import circular_aperture, create_line
from gerber_editor.tools.stroke_font import create_text


def demo_layer() -> GerberLayer:
    layer = GerberLayer("demo_F_Silkscreen.gbr", function="F.Silk")
    layer.attributes = ((".FileFunction", ("Legend", "Top")),)
    corners = [Point.of(0, 0), Point.of(80, 0), Point.of(80, 50), Point.of(0, 50), Point.of(0, 0)]
    for a, b in zip(corners, corners[1:], strict=False):
        layer.objects.append(create_line(layer, a, b, D("0.2")))
    for text, x, y, height in [
        ("INDUSTRIAL I/O", 5, 43, "3"),
        ("CONTROL BOARD REV 1.0", 5, 38, "1.7"),
        ("J1", 6, 6, "2"),
        ("J2", 6, 26, "2"),
        ("U1", 30, 28, "2"),
        ("24V  GND  IN  OUT", 5, 3, "1.3"),
        ("MANUFACTURER", 51, 6, "1.7"),
        ("LOGO", 57, 10, "2"),
    ]:
        layer.objects.extend(create_text(layer, text, Point.of(x, y), D(height), D("0.16")))
    for x, y, w, h in [(5, 9, 20, 12), (5, 29, 20, 6), (30, 14, 15, 12)]:
        points = [
            Point.of(x, y),
            Point.of(x + w, y),
            Point.of(x + w, y + h),
            Point.of(x, y + h),
            Point.of(x, y),
        ]
        for a, b in zip(points, points[1:], strict=False):
            layer.objects.append(create_line(layer, a, b, D("0.2")))
    ap = circular_aperture(layer, D("1.1"))
    for i in range(8):
        layer.objects.append(GerberObject(Flash(Point(D(7) + D(i) * D("2.2"), D(11))), ap))
    # Diamond emblem beside manufacturer wordmark; window [50,5]-[78,18] removes both.
    points = [
        Point.of(53, 14),
        Point.of(57, 18),
        Point.of(61, 14),
        Point.of(57, 10),
        Point.of(53, 14),
    ]
    region = Region((tuple(Line(a, b) for a, b in zip(points, points[1:], strict=False)),))
    layer.objects.append(GerberObject(region, None))
    return GerberParser().parse(GerberWriter().serialize(layer, SaveMode.NORMALIZED), layer.name)
