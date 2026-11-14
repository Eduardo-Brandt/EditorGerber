"""Viewport overlays: contrast-inverted measurement and live unit-aware labels."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from gerber_editor.core.primitives import Arc, Point
from gerber_editor.core.units import length_text, vector_text
from gerber_editor.geometry.boolean import curve_points


def _point(p):
    return QPointF(float(p.x), float(p.y))


def draw_overlays(canvas, painter, rect):
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#59e1ff"), 0, Qt.PenStyle.DashLine))
    if canvas._line_start and canvas.mode == "line":
        painter.drawLine(_point(canvas._line_start), _point(canvas.snap(canvas._cursor)))
    points = canvas._shape_points
    current = canvas.snap(canvas._cursor)
    if points:
        start = points[0]
        end = current
        if canvas.mode in ("rectangle", "square"):
            x, y = float(end.x), float(end.y)
            if canvas.mode == "square":
                side = max(abs(float(end.x - start.x)), abs(float(end.y - start.y)))
                x = float(start.x) + (side if end.x >= start.x else -side)
                y = float(start.y) + (side if end.y >= start.y else -side)
            painter.drawRect(QRectF(_point(start), QPointF(x, y)).normalized())
        elif canvas.mode == "circle":
            radius = math.hypot(float(end.x - start.x), float(end.y - start.y))
            painter.drawEllipse(_point(start), radius, radius)
        elif canvas.mode == "arc":
            painter.drawLine(_point(start), _point(end))
            if len(points) == 2:
                radius = math.hypot(float(points[1].x - start.x), float(points[1].y - start.y))
                distance = math.hypot(float(end.x - start.x), float(end.y - start.y))
                if radius and distance:
                    from decimal import Decimal

                    target = Point(
                        start.x + (end.x - start.x) * Decimal(str(radius / distance)),
                        start.y + (end.y - start.y) * Decimal(str(radius / distance)),
                    )
                    arc = Arc(points[1], target, start, canvas.arc_clockwise)
                    painter.drawPolyline(QPolygonF([QPointF(x, y) for x, y in curve_points(arc)]))
        elif canvas.mode == "dimension":
            painter.drawLine(_point(start), _point(points[1] if len(points) > 1 else current))
            if len(points) > 1:
                painter.drawLine(_point(points[1]), _point(current))
    if canvas._placement_anchor:
        delta_x = float(current.x - canvas._placement_anchor.x)
        delta_y = float(current.y - canvas._placement_anchor.y)
        painter.save()
        painter.translate(delta_x, delta_y)
        painter.setBrush(QColor(75, 210, 255, 75))
        for path in canvas.placement_paths:
            painter.drawPath(path)
        painter.restore()
    if canvas.snap_target:
        target = _point(canvas.snap_target)
        size = 5 / abs(canvas.transform().m11())
        painter.setPen(QPen(QColor("#38ffd0"), 0))
        painter.drawRect(QRectF(target.x() - size, target.y() - size, size * 2, size * 2))
    selected = canvas.selected_objects()
    if selected:
        bounds = QRectF()
        for item in selected:
            bounds = bounds.united(item.sceneBoundingRect())
        painter.drawRect(bounds)
    if canvas._press is not None and canvas._rubber is not None:
        crossing = canvas._rubber.x() < canvas._press.x()
        selection = QRectF(
            canvas.mapToScene(canvas._press), canvas.mapToScene(canvas._rubber)
        ).normalized()
        color = QColor("#60dc9d" if crossing else "#63b6ff")
        painter.setPen(QPen(color, 0, Qt.PenStyle.DashLine))
        color.setAlpha(35)
        painter.setBrush(color)
        painter.drawRect(selection)
    painter.restore()

    measurement = None
    if canvas.mode == "measure":
        if canvas._line_start:
            measurement = (canvas._line_start, current)
        elif canvas._measurement:
            measurement = canvas._measurement
    painter.save()
    painter.resetTransform()
    cursor = QPointF(canvas.mapFromScene(canvas._cursor))
    if measurement:
        start, end = measurement
        a, b = (
            QPointF(canvas.mapFromScene(_point(start))),
            QPointF(canvas.mapFromScene(_point(end))),
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
        painter.setPen(QPen(QColor("white"), 1, Qt.PenStyle.DotLine))
        painter.drawLine(a, b)
        for point in (a, b):
            painter.drawLine(point + QPointF(-5, 0), point + QPointF(5, 0))
            painter.drawLine(point + QPointF(0, -5), point + QPointF(0, 5))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        dx, dy = float(end.x - start.x), float(end.y - start.y)
        text = vector_text(dx, dy, canvas.units, canvas.polar)
        metrics = painter.fontMetrics()
        box = metrics.boundingRect(
            QRectF(0, 0, 800, 150).toRect(), Qt.AlignmentFlag.AlignLeft, text
        )
        width, height = box.width() + 16, box.height() + 10
        x = min(max(2, cursor.x() + 16), canvas.viewport().width() - width - 2)
        y = min(max(2, cursor.y() + 18), canvas.viewport().height() - height - 2)
        label = QRectF(x, y, width, height)
        painter.setBrush(QColor(20, 24, 31, 235))
        painter.setPen(QPen(QColor("#c7d4e6"), 1))
        painter.drawRoundedRect(label, 3, 3)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(label.adjusted(8, 5, -5, -5), Qt.AlignmentFlag.AlignLeft, text)
    elif points and canvas.mode in ("circle", "arc"):
        radius = math.hypot(float(current.x - points[0].x), float(current.y - points[0].y))
        painter.setPen(QColor("#d4f7ff"))
        painter.drawText(cursor + QPointF(14, -12), "R " + length_text(radius, canvas.units))
    painter.setPen(QPen(QColor("#a0b0c7"), 1))
    if canvas.full_cursor:
        painter.drawLine(QPointF(0, cursor.y()), QPointF(canvas.viewport().width(), cursor.y()))
        painter.drawLine(QPointF(cursor.x(), 0), QPointF(cursor.x(), canvas.viewport().height()))
    else:
        painter.drawLine(cursor + QPointF(-7, 0), cursor + QPointF(7, 0))
        painter.drawLine(cursor + QPointF(0, -7), cursor + QPointF(0, 7))
    painter.restore()
