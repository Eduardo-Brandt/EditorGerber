"""Determinate status-bar progress, counted once per completed file."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QProgressBar


class FileProgress(QProgressBar):
    def __init__(self, locale, title, parent):
        super().__init__(parent)
        self.locale, self.title = locale, title
        self.active = False
        self.setMinimumWidth(205)
        self.setMaximumWidth(280)
        self.setTextVisible(True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def add_files(self, count):
        if count <= 0:
            return
        self.timer.stop()
        if self.active:
            self.setMaximum(self.maximum() + count)
        else:
            self.setRange(0, count)
            self.setValue(0)
        self.active = True
        self.setFormat(self.locale(self.title) + " %v/%m")
        self.show()

    def advance(self, name):
        if self.active:
            self.setToolTip(name)
            self.setValue(min(self.maximum(), self.value() + 1))

    def finish(self):
        if self.active:
            self.active = False
            self.timer.start(1800)

    def cancel(self):
        self.active = False
        self.timer.stop()
        self.hide()
