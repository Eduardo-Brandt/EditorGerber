"""Small native vector icons for CAD actions; no downloaded bitmap assets."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def icon(name: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(
            QColor("#50555b"),
            1.6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    if name == "select":
        path = QPainterPath(QPointF(6, 3))
        for x, y in [(18, 13), (12, 14), (9, 20), (6, 3)]:
            path.lineTo(x, y)
        painter.fillPath(path, QColor("#50555b"))
    elif name in ("line", "measure"):
        painter.drawLine(4, 20, 20, 4)
        if name == "measure":
            painter.drawLine(5, 14, 9, 18)
            painter.drawLine(9, 10, 13, 14)
            painter.drawLine(13, 6, 17, 10)
        else:
            painter.drawEllipse(QRectF(2, 18, 4, 4))
            painter.drawEllipse(QRectF(18, 2, 4, 4))
    elif name == "fiducial":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.setBrush(QColor("#3183ae"))
        painter.drawEllipse(QRectF(8, 8, 8, 8))
        painter.drawLine(0, 12, 5, 12)
        painter.drawLine(19, 12, 24, 12)
    elif name == "cutout":
        painter.drawRect(2, 3, 20, 18)
        painter.drawRoundedRect(QRectF(6, 9, 12, 6), 3, 3)
    elif name == "text":
        painter.drawLine(4, 5, 20, 5)
        painter.drawLine(12, 5, 12, 20)
        painter.drawLine(8, 20, 16, 20)
    elif name == "open":
        painter.setBrush(QColor("#e0b866"))
        painter.drawRoundedRect(QRectF(2, 6, 20, 15), 1, 1)
        painter.drawLine(3, 10, 21, 10)
        painter.drawLine(3, 6, 10, 6)
        painter.drawLine(10, 6, 12, 3)
    elif name in ("save", "save_as", "save_all"):
        if name == "save_all":
            painter.setBrush(QColor("#b4c6d5"))
            painter.drawRect(7, 2, 15, 17)
            painter.translate(-2, 2)
        painter.setBrush(QColor("#7198b9"))
        painter.drawRect(4, 3, 16, 18)
        painter.setBrush(QColor("#f8f8f8"))
        painter.drawRect(7, 3, 9, 6)
        painter.drawRect(7, 14, 10, 7)
        if name == "save_as":
            painter.setPen(QPen(QColor("#178bca"), 2))
            painter.drawLine(14, 20, 22, 12)
    elif name == "close_all":
        painter.setBrush(QColor("#e4ebf0"))
        painter.drawRect(7, 2, 15, 17)
        painter.setBrush(QColor("#f8f8f8"))
        painter.drawRect(3, 6, 15, 16)
        painter.setPen(QPen(QColor("#c34848"), 2.2))
        painter.drawLine(7, 10, 14, 18)
        painter.drawLine(7, 18, 14, 10)
    elif name in ("circle", "arc"):
        if name == "circle":
            painter.drawEllipse(QRectF(3, 3, 18, 18))
        else:
            painter.drawArc(QRectF(3, 3, 18, 18), 0, 120 * 16)
            painter.drawLine(12, 12, 21, 12)
            painter.drawLine(12, 12, 7, 4)
    elif name in ("rectangle", "square", "image"):
        painter.drawRect(3, 5 if name != "square" else 3, 18, 14 if name != "square" else 18)
        if name == "image":
            painter.drawLine(4, 17, 10, 10)
            painter.drawLine(10, 10, 16, 17)
            painter.drawEllipse(QRectF(15, 7, 3, 3))
    elif name == "dimension":
        painter.drawLine(3, 4, 3, 20)
        painter.drawLine(21, 4, 21, 20)
        painter.drawLine(3, 10, 21, 10)
        painter.drawLine(3, 10, 7, 7)
        painter.drawLine(3, 10, 7, 13)
        painter.drawLine(21, 10, 17, 7)
        painter.drawLine(21, 10, 17, 13)
    elif name in ("crosshair", "polar", "negative"):
        if name == "crosshair":
            painter.drawLine(1, 12, 23, 12)
            painter.drawLine(12, 1, 12, 23)
        elif name == "polar":
            painter.drawArc(QRectF(3, 3, 18, 18), 0, 100 * 16)
            painter.drawLine(3, 21, 22, 21)
            painter.drawLine(3, 21, 16, 4)
        else:
            painter.setBrush(QColor("#999999"))
            painter.drawEllipse(QRectF(3, 3, 18, 18))
            painter.setPen(QPen(QColor("#eeeeee"), 2))
            painter.drawLine(7, 12, 17, 12)
    elif name == "move":
        painter.setPen(QPen(QColor("#3183ae"), 1.8))
        painter.drawLine(3, 12, 21, 12)
        painter.drawLine(12, 3, 12, 21)
        for a, b, c in [
            ((6, 9), (3, 12), (6, 15)),
            ((18, 9), (21, 12), (18, 15)),
            ((9, 6), (12, 3), (15, 6)),
            ((9, 18), (12, 21), (15, 18)),
        ]:
            painter.drawLine(*a, *b)
            painter.drawLine(*b, *c)
    elif name in ("copy", "duplicate"):
        painter.setBrush(QColor("#dce7ef"))
        painter.drawRect(8, 3, 12, 14)
        painter.setBrush(QColor("#f8f8f8"))
        painter.drawRect(3, 8, 12, 14)
        if name == "duplicate":
            painter.setPen(QPen(QColor("#178bca"), 2))
            painter.drawLine(16, 17, 22, 17)
            painter.drawLine(19, 14, 19, 20)
        else:
            painter.drawLine(6, 12, 12, 12)
            painter.drawLine(6, 16, 12, 16)
    elif name == "cut":
        painter.drawEllipse(QRectF(3, 15, 6, 6))
        painter.drawEllipse(QRectF(15, 15, 6, 6))
        painter.drawLine(8, 16, 19, 3)
        painter.drawLine(16, 16, 5, 3)
        painter.setBrush(QColor("#3183ae"))
        painter.drawEllipse(QRectF(10.5, 10.5, 3, 3))
    elif name == "paste":
        painter.setBrush(QColor("#d7b877"))
        painter.drawRoundedRect(QRectF(4, 5, 16, 17), 1, 1)
        painter.setBrush(QColor("#f8f8f8"))
        painter.drawRect(7, 9, 10, 10)
        painter.setBrush(QColor("#7198b9"))
        painter.drawRoundedRect(QRectF(8, 2, 8, 6), 1, 1)
    elif name == "mirror":
        painter.setPen(QPen(QColor("#84919d"), 1.3, Qt.PenStyle.DashLine))
        painter.drawLine(12, 2, 12, 22)
        painter.setPen(QPen(QColor("#3183ae"), 1.5))
        for sign, color in ((-1, "#a9c8dd"), (1, "#e0b866")):
            path = QPainterPath(QPointF(12 + sign * 3, 5))
            path.lineTo(12 + sign * 9, 18)
            path.lineTo(12 + sign * 3, 18)
            path.closeSubpath()
            painter.fillPath(path, QColor(color))
            painter.drawPath(path)
    elif name in ("group", "ungroup"):
        painter.setBrush(QColor("#a9c8dd"))
        painter.drawRect(5, 6, 7, 7)
        painter.setBrush(QColor("#e0b866"))
        painter.drawRect(12, 12, 7, 7)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if name == "group":
            painter.setPen(QPen(QColor("#3183ae"), 1.4, Qt.PenStyle.DashLine))
            painter.drawRect(2, 2, 20, 20)
        else:
            painter.drawLine(2, 7, 2, 2)
            painter.drawLine(2, 2, 7, 2)
            painter.drawLine(17, 22, 22, 22)
            painter.drawLine(22, 22, 22, 17)
    elif name == "offset":
        painter.setPen(QPen(QColor("#9aa4ad"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(4, 19, 20, 19)
        painter.drawLine(20, 19, 20, 4)
        painter.setPen(QPen(QColor("#3183ae"), 1.8))
        painter.drawEllipse(QRectF(2, 17, 4, 4))
        painter.drawLine(6, 17, 20, 4)
        painter.drawLine(14, 4, 20, 4)
        painter.drawLine(20, 4, 20, 10)
    elif name in ("select_all", "clear_selection"):
        painter.setPen(QPen(QColor("#6b7e8e"), 1.3, Qt.PenStyle.DashLine))
        painter.drawRect(3, 3, 18, 18)
        painter.setPen(QPen(QColor("#3183ae"), 1.5))
        if name == "select_all":
            painter.setBrush(QColor("#a9c8dd"))
            painter.drawRect(7, 7, 5, 5)
            painter.drawRect(13, 13, 5, 5)
        else:
            painter.setPen(QPen(QColor("#c34848"), 2))
            painter.drawLine(8, 8, 16, 16)
            painter.drawLine(8, 16, 16, 8)
    elif name == "delete":
        painter.drawRect(6, 7, 12, 14)
        painter.drawLine(4, 6, 20, 6)
        painter.drawLine(9, 3, 15, 3)
        painter.drawLine(10, 10, 10, 18)
        painter.drawLine(14, 10, 14, 18)
    elif name in ("undo", "redo"):
        if name == "redo":
            painter.translate(24, 0)
            painter.scale(-1, 1)
        painter.drawArc(QRectF(6, 5, 15, 15), 0, 240 * 16)
        painter.drawLine(6, 6, 6, 13)
        painter.drawLine(6, 13, 13, 13)
    elif name in ("fit", "zoom_in", "zoom_out"):
        painter.drawEllipse(QRectF(3, 3, 13, 13))
        painter.drawLine(15, 15, 21, 21)
        painter.drawLine(6, 9, 13, 9)
        if name != "zoom_out":
            painter.drawLine(9, 6, 9, 13)
        if name == "fit":
            painter.drawRect(1, 1, 18, 18)
    elif name == "grid":
        painter.setBrush(QColor("#555b63"))
        for x in (5, 12, 19):
            for y in (5, 12, 19):
                painter.drawEllipse(QRectF(x - 1, y - 1, 2, 2))
    elif name == "array":
        painter.setBrush(QColor("#7198b9"))
        for x in (3, 11, 19):
            for y in (4, 12, 20):
                painter.drawRect(x - 2, y - 2, 4, 4)
    elif name == "3d":
        painter.setBrush(QColor("#6fae8e"))
        polygon = QPainterPath(QPointF(3, 8))
        for x, y in ((15, 3), (22, 8), (22, 17), (10, 22), (3, 17), (3, 8), (10, 13), (22, 8)):
            polygon.lineTo(x, y)
        painter.drawPath(polygon)
        painter.drawLine(10, 13, 10, 22)
    elif name in ("axes", "snap", "snap_points"):
        painter.setPen(QPen(QColor("#3183ae"), 1.5))
        painter.drawLine(2, 12, 22, 12)
        painter.drawLine(12, 2, 12, 22)
        if name in ("snap", "snap_points"):
            painter.drawRect(8, 8, 8, 8)
        if name == "snap_points":
            painter.drawEllipse(QRectF(2, 2, 5, 5))
            painter.drawEllipse(QRectF(17, 17, 5, 5))
    elif name in ("mm", "in", "mil"):
        painter.drawText(QRectF(0, 0, 24, 19), Qt.AlignmentFlag.AlignCenter, name)
        painter.drawLine(3, 21, 21, 21)
    painter.end()
    return QIcon(pixmap)
