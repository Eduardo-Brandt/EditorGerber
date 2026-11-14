"""Discard user input during processing; allow operation-owned modal dialogs."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget


class ProcessingInputGuard(QObject):
    INPUT_EVENTS = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.Wheel,
        QEvent.Type.MouseMove,
        QEvent.Type.TabletMove,
        QEvent.Type.InputMethod,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.Shortcut,
        QEvent.Type.ShortcutOverride,
        QEvent.Type.ContextMenu,
        QEvent.Type.TouchBegin,
        QEvent.Type.TouchUpdate,
        QEvent.Type.TouchEnd,
        QEvent.Type.TabletPress,
        QEvent.Type.TabletRelease,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.Drop,
    }

    def __init__(self, app):
        super().__init__(app)
        self.owners = set()
        self.locked = False
        app.installEventFilter(self)

    def acquire(self, owner):
        self.owners.add(id(owner))
        if not self.locked:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.locked = True

    def release(self, owner):
        self.owners.discard(id(owner))
        if self.locked and not self.owners:
            self._release_input()

    def _release_input(self):
        if self.locked and not self.owners:
            QApplication.restoreOverrideCursor()
            self.locked = False

    def eventFilter(self, watched, event):
        if not self.locked:
            return False
        modal = QApplication.activeModalWidget()
        if (
            modal
            and isinstance(watched, QWidget)
            and (watched is modal or modal.isAncestorOf(watched))
        ):
            return False
        if modal and isinstance(watched, QWindow):
            native_window = watched
            while native_window:
                if native_window is modal.windowHandle():
                    return False
                native_window = native_window.transientParent()
        if (
            self.owners
            and event.type() == QEvent.Type.Close
            and isinstance(watched, QWidget)
            and watched.isWindow()
        ):
            event.ignore()
            return True
        if event.type() in self.INPUT_EVENTS:
            event.accept()
            return True
        return False


def processing_guard():
    app = QApplication.instance()
    if not hasattr(app, "_gerber_processing_guard"):
        app._gerber_processing_guard = ProcessingInputGuard(app)
    return app._gerber_processing_guard
