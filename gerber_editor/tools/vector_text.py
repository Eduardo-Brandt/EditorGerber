"""Installed fonts become isolated Gerber aperture images with transparent holes."""

from dataclasses import replace
from decimal import Decimal
from math import cos, radians, sin

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QPainterPath, QTransform

from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Flash, Line, Point
from gerber_editor.tools.shapes import layer_quantum, point_on_grid
from gerber_editor.tools.stroke_font import create_text

STROKE_FONT = "Stroke PCB"
TEXT_TOLERANCE_MM = 0.00025


def ensure_offscreen_font():
    """The Windows offscreen Qt plugin requires explicitly loading a local font."""
    if QFontDatabase.families():
        return
    import os
    from pathlib import Path

    roots = [
        Path(p)
        for p in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.FontsLocation)
    ]
    if os.environ.get("SystemRoot"):
        roots.append(Path(os.environ["SystemRoot"]) / "Fonts")
    for root in roots:
        for name in ("segoeui.ttf", "arial.ttf"):
            path = root / name
            if path.is_file() and QFontDatabase.addApplicationFont(str(path)) >= 0:
                return


def vector_text(
    layer,
    text: str,
    position: Point,
    height: Decimal,
    stroke: Decimal,
    family: str = STROKE_FONT,
    *,
    rotation=0.0,
    bold=False,
    italic=False,
    centered=False,
    mirror_y=False,
    polarity=Polarity.DARK,
    reserved_apertures=(),
) -> list[GerberObject]:
    if not text.strip() or not height.is_finite() or height <= 0:
        raise ValueError("Text and positive height are required.")
    quantum = layer_quantum(layer)
    angle = radians(rotation)
    c, s = Decimal(str(cos(angle))), Decimal(str(sin(angle)))

    def transform(p, offset=Decimal(0)):
        x, y = p.x - offset, -p.y if mirror_y else p.y
        return point_on_grid(position.x + x * c - y * s, position.y + x * s + y * c, quantum)

    if family == STROKE_FONT:
        objects = create_text(layer, text, Point.of(0, 0), height, stroke, polarity)
        bounds = objects[0].bounds
        for obj in objects[1:]:
            bounds = bounds.union(obj.bounds)
        offset = Decimal(str((bounds.left + bounds.right) / 2)) if centered else Decimal(0)
        return [
            replace(
                obj,
                geometry=Line(
                    transform(obj.geometry.start, offset), transform(obj.geometry.end, offset)
                ),
            )
            for obj in objects
        ]
    ensure_offscreen_font()
    if not QFontDatabase.families():
        raise ValueError("No installed font is available for vector conversion.")
    font = QFont(family)
    font.setPixelSize(1000)
    font.setBold(bold)
    font.setItalic(italic)
    metrics = QFontMetricsF(font)
    cap_height = metrics.capHeight()
    if cap_height <= 0:
        raise ValueError("Invalid font metrics.")
    path = QPainterPath()
    path.addText(0, 0, font, text)
    scale = float(height) / cap_height
    path = QTransform.fromScale(scale, -scale).map(path)
    center = Decimal(str(path.boundingRect().center().x())) if centered else Decimal(0)
    flatten = 1.0 / max(TEXT_TOLERANCE_MM, float(quantum) / 2)
    contours = []
    # Resolve overlaps at high resolution before flattening into output-grid
    # points. Simplifying directly in mm would introduce a coarse tolerance.
    outline = QTransform.fromScale(flatten, flatten).map(path).simplified()
    for polygon in outline.toSubpathPolygons():
        points = []
        for value in polygon:
            p = transform(
                Point(Decimal(str(value.x() / flatten)), Decimal(str(value.y() / flatten))), center
            )
            if not points or p != points[-1]:
                points.append(p)
        if len(points) > 2 and points[0] != points[-1]:
            points.append(points[0])
        if len(points) >= 4:
            contours.append(points)
    if not contours:
        raise ValueError("The chosen font produced no outline at this size.")
    from shapely.geometry import Polygon

    polygons = [Polygon([(float(p.x), float(p.y)) for p in contour]) for contour in contours]
    if any(not polygon.is_valid or polygon.area == 0 for polygon in polygons):
        raise ValueError(
            "Font outline cannot be represented at this layer resolution. Increase the text height."
        )
    depths = [
        sum(other.covers(polygon) for j, other in enumerate(polygons) if i != j)
        for i, polygon in enumerate(polygons)
    ]
    flash = point_on_grid(position.x, position.y, quantum)
    primitives = []
    for index in sorted(range(len(contours)), key=lambda i: depths[i]):
        points = contours[index]
        values = [Decimal(1 if depths[index] % 2 == 0 else 0), Decimal(len(points) - 1)]
        for p in points:
            values += [p.x - flash.x, p.y - flash.y]
        values.append(Decimal(0))
        primitives.append(MacroPrimitive(4, tuple(values)))
    codes = [
        9,
        *layer.apertures,
        *(obj.aperture.code for obj in layer.objects if obj.aperture),
        *(aperture.code for aperture in reserved_apertures),
    ]
    aperture = Aperture(max(codes) + 1, "MACRO", (), macro=tuple(primitives))
    return [GerberObject(Flash(flash), aperture, polarity)]
