"""Application entry point: python -m gerber_editor [--demo] [files...]."""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from gerber_editor.app.i18n import Locale
from gerber_editor.app.metadata import APP_NAME
from gerber_editor.app.preferences import Preferences
from gerber_editor.app.settings import apply_theme
from gerber_editor.ui.splash import SplashScreen


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME + " 2D")
    parser.add_argument("files", nargs="*")
    parser.add_argument(
        "--demo", action="store_true", help="Abre serigrafia sintética de demonstração"
    )
    parser.add_argument("--lang", choices=["pt_BR", "en"], help="Interface language")
    parser.add_argument("--no-splash", action="store_true", help="Skip the startup artwork")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Encerra após carregar e desenhar (CI)"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("EBRANDT Tecnologia")
    from gerber_editor.app.diagnostics import Diagnostics

    try:
        diagnostics = Diagnostics()
    except OSError:
        logging.exception("Unable to open diagnostic logs")
        diagnostics = None
    from gerber_editor.ui.branding import apply_branding

    apply_branding(app)
    apply_theme(app)
    locale = Locale(args.lang or Preferences().data["language"])
    splash = None
    if not args.no_splash:
        splash = SplashScreen(locale)
        splash.show()
        app.processEvents()
    from gerber_editor.app.backup import ensure_version_backup
    from gerber_editor.app.main_window import MainWindow

    try:
        ensure_version_backup()
    except OSError:
        logging.getLogger(__name__).exception("Version backup failed")

    window = MainWindow(language=locale.language)
    if args.demo:
        window.load_demo()
    if splash:
        splash.supportRequested.connect(window.show_support)

    def show_editor():
        # A maximized editor can cover a still-visible native splash on Windows.
        # Keep it hidden until the artwork has had its full display time.
        if splash and (delay := splash.remaining_ms()):
            QTimer.singleShot(delay, show_editor)
            return
        window.showMaximized()
        if splash:
            splash.finish(window)
        if args.files:
            if args.smoke_test:
                for path in args.files:
                    window.open_path(path)
            else:
                QTimer.singleShot(0, lambda: window.open_paths_async(args.files))
        if args.smoke_test:
            QTimer.singleShot(1800, app.quit)

    show_editor()
    try:
        return app.exec()
    finally:
        if diagnostics:
            diagnostics.close()


if __name__ == "__main__":
    raise SystemExit(main())
