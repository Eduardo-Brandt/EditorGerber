"""A left tool palette that wraps into columns instead of hiding actions."""

import math

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QGridLayout, QLayout, QSizePolicy, QToolButton, QWidget


class ToolPalette(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setObjectName("expandedToolPalette")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.layout_grid = QGridLayout(self)
        self.layout_grid.setContentsMargins(3, 3, 3, 3)
        self.layout_grid.setSpacing(2)
        self.layout_grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.buttons = []
        self._rows = None
        for action in actions:
            if action.isSeparator():
                continue
            button = QToolButton(self)
            button.setDefaultAction(action)
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(32, 32)
            button.setAutoRaise(True)
            self.buttons.append(button)
        self.setMinimumHeight(40)
        self._arrange()

    def _arrange(self):
        rows = max(1, (self.height() - 6) // 34)
        if rows == self._rows:
            return
        old_rows = self._rows or 0
        self._rows = rows
        for row in range(max(old_rows, rows) + 1):
            self.layout_grid.setRowStretch(row, 0)
        while self.layout_grid.count():
            self.layout_grid.takeAt(0)
        for index, button in enumerate(self.buttons):
            self.layout_grid.addWidget(button, index % rows, index // rows)
        self.layout_grid.setRowStretch(rows, 1)
        self.setFixedWidth(math.ceil(len(self.buttons) / rows) * 34 + 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def minimumSizeHint(self):
        return QSize(self.width(), 40)

    def sizeHint(self):
        return self.minimumSizeHint()
