"""Animated central processing indicator and unobtrusive pending-tool status."""

from contextlib import contextmanager
from time import monotonic

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from gerber_editor.ui.input_guard import processing_guard


class Hourglass(QWidget):
    """Draw the indicator without depending on an installed symbol font."""

    def __init__(self, parent=None, size=20):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0.0
        self._opaque = size > 20
        if self._opaque:
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._opaque:
            painter.fillRect(self.rect(), QColor("#183345"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        scale = self.width() / 26
        painter.scale(scale, scale)
        painter.translate(-9, -10)
        painter.setPen(QPen(QColor("#3d5363"), 1.4))
        painter.setBrush(QColor("#e8f5ff"))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(x, y)
                    for x, y in (
                        (4, 3),
                        (14, 3),
                        (13, 6),
                        (10, 10),
                        (13, 14),
                        (14, 17),
                        (4, 17),
                        (5, 14),
                        (8, 10),
                        (5, 6),
                    )
                ]
            )
        )
        painter.setPen(QPen(QColor("#c88a20"), 1))
        painter.setBrush(QColor("#e8ad43"))
        for points in (((6, 5), (12, 5), (9, 9)), ((5, 16), (13, 16), (9, 12))):
            painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
        painter.setPen(QPen(QColor("#3d5363"), 2))
        painter.drawLine(3, 2, 15, 2)
        painter.drawLine(3, 18, 15, 18)


class ProcessingOverlay(QFrame):
    """Small non-modal card, centered above the window's drawing area."""

    def __init__(self, window):
        super().__init__(window)
        self.host_window = window
        self.setObjectName("processingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            "QFrame#processingOverlay { background: #183345; border: 1px solid #6a9bbb;"
            " border-radius: 14px; }"
            "QFrame#processingOverlay QLabel { color: #ffffff; background: transparent;"
            " border: none; font-size: 14px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 18)
        self.hourglass = Hourglass(self, 72)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.hourglass, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self.setFixedWidth(300)
        self._watched_area = None
        self.hide()
        window.installEventFilter(self)

    def reposition(self):
        area = self.host_window.centralWidget()
        if area is None:
            return
        if area is not self._watched_area:
            self._watched_area = area
            area.installEventFilter(self)
        self.adjustSize()
        center = area.mapTo(self.host_window, area.rect().center())
        self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
        self.raise_()

    def eventFilter(self, watched, event):
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Show,
        ):
            self.reposition()
        return super().eventFilter(watched, event)


class BusyIndicator(QWidget):
    def __init__(self, locale, parent=None):
        super().__init__(parent)
        self.locale = locale
        self.operations = {}
        self.sequence = 0
        self.tool = ""
        self.input_guard = processing_guard()
        self.overlay = ProcessingOverlay(parent) if parent is not None else None
        self._started = monotonic()
        self._last_pulse = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.pulse)
        self.setObjectName("busyIndicator")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedSize(55, 10)
        self.label = QLabel()
        layout.addWidget(Hourglass(self))
        layout.addWidget(self.progress)
        layout.addWidget(self.label)
        self.hide()

    @property
    def active(self):
        return bool(self.operations or self.tool)

    def begin(self, label):
        self.sequence += 1
        self.operations[self.sequence] = label
        self.refresh()
        return self.sequence

    def end(self, token):
        self.operations.pop(token, None)
        self.refresh()

    def pending(self, active, label=""):
        self.tool = label if active else ""
        self.refresh()

    def refresh(self):
        text = next(reversed(self.operations.values()), self.tool) if self.operations else self.tool
        self.label.setText(self.locale(text) if text else "")
        self.setVisible(self.active)
        self.progress.setVisible(bool(self.operations))
        if self.operations:
            self.input_guard.acquire(self)
        else:
            self.input_guard.release(self)
        if self.overlay:
            self.overlay.label.setText(self.locale(text) if text else "")
            self.overlay.setVisible(bool(self.operations))
            if self.operations:
                self.overlay.reposition()
                if not self.timer.isActive():
                    self._started = monotonic()
                    self.timer.start()
                self.pulse()
            else:
                self.timer.stop()

    def pulse(self):
        """Also repaint between batches of GUI-only geometry work, without reentry."""
        now = monotonic()
        if self.overlay and self.operations and now - self._last_pulse >= 0.025:
            self._last_pulse = now
            self.overlay.hourglass.angle = ((now - self._started) * 160) % 360
            self.overlay.hourglass.repaint()

    @contextmanager
    def operation(self, label):
        token = self.begin(label)
        if self.overlay:
            self.overlay.repaint()
        try:
            yield
        finally:
            self.end(token)
