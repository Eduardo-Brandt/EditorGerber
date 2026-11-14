"""One application identity and image-derived icon across top-level windows."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon


def application_icon():
    return QIcon(str(Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico"))


def apply_branding(app):
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EBRANDT.EditorGerber")
    app.setWindowIcon(application_icon())
