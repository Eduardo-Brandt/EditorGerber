"""Branded startup artwork with native, always-current identity text."""

from pathlib import Path
from time import monotonic

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import QSplashScreen

from gerber_editor.app.metadata import (
    CREATED,
    CREATOR,
    LOCATION,
    SUPPORT_MESSAGE,
    VERSION,
    WEBSITE,
    WEBSITE_URL,
)


class SplashScreen(QSplashScreen):
    supportRequested = Signal()
    MINIMUM_SECONDS = 8.0

    def __init__(self, locale, dismiss_on_click=False):
        artwork = Path(__file__).resolve().parents[1] / "assets" / "splash.png"
        pixmap = QPixmap(str(artwork)).scaledToWidth(
            900, Qt.TransformationMode.SmoothTransformation
        )
        if pixmap.isNull():
            raise RuntimeError("Splash artwork is missing from the application package.")
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self.locale = locale
        self.dismiss_on_click = dismiss_on_click
        self._shown_at = None
        self._support_pending = False
        self.link_rect = QRectF(
            pixmap.width() * 0.56, pixmap.height() * 0.83, pixmap.width() * 0.4, 28
        )
        self.setObjectName("startupSplash")
        self.support_rect = QRectF(26, pixmap.height() - 52, pixmap.width() - 52, 26)

    def showEvent(self, event):
        self._shown_at = monotonic()
        super().showEvent(event)

    def remaining_ms(self):
        if self.dismiss_on_click or self._shown_at is None:
            return 0
        return max(0, int((self.MINIMUM_SECONDS - (monotonic() - self._shown_at)) * 1000) + 1)

    def finish(self, window):
        delay = self.remaining_ms()
        if delay:
            QTimer.singleShot(delay, lambda: self.finish(window))
        else:
            super().finish(window)

    def _open_support(self):
        if delay := self.remaining_ms():
            QTimer.singleShot(delay, self._open_support)
            return
        self.hide()
        self.supportRequested.emit()

    def drawContents(self, painter):
        painter.setPen(QColor("#daeaf5"))
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        height = self.pixmap().height()
        top = height * 0.73
        painter.drawText(
            26, int(top), f"{self.locale('Versão')} {VERSION} · {self.locale('Criação')}: {CREATED}"
        )
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(26, int(top + 27), CREATOR)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(26, int(top + 50), LOCATION)
        painter.setPen(QColor("#46d5f5"))
        painter.drawText(26, int(top + 75), self.locale("SOFTWARE LIVRE") + " · GPLv3")
        painter.setPen(QColor("#46d5f5"))
        painter.drawText(self.link_rect, Qt.AlignmentFlag.AlignCenter, WEBSITE)
        font.setPointSize(9)
        font.setUnderline(True)
        painter.setFont(font)
        painter.drawText(
            self.support_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.locale(SUPPORT_MESSAGE),
        )
        font.setUnderline(False)
        painter.setFont(font)
        painter.setPen(QColor("#a2bace"))
        painter.drawText(26, int(height - 18), self.locale("Inicializando…"))

    def mousePressEvent(self, event):
        if self.link_rect.contains(event.position()):
            QDesktopServices.openUrl(QUrl(WEBSITE_URL))
        elif self.support_rect.contains(event.position()):
            if not self._support_pending:
                self._support_pending = True
                QTimer.singleShot(self.remaining_ms(), self._open_support)
        else:
            if self.dismiss_on_click:
                self.close()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if not self.remaining_ms():
                self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.remaining_ms():
            event.ignore()
        else:
            super().closeEvent(event)
