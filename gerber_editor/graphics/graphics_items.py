"""Per-object hit paths indexed by QGraphicsScene's BSP tree."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem


class ObjectItem(QGraphicsPathItem):
    def __init__(self, obj, layer, path):
        super().__init__(path)
        self.obj, self.layer = obj, layer
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            pen = QPen(QColor("#59e1ff"), 1.7)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QColor(65, 210, 255, 70))
            painter.drawPath(self.path())
