"""Exercise the real entry point and measure native splash/editor visibility."""

import json
import os
import sys
from pathlib import Path
from time import monotonic


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "output/v081/startup"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")
    os.environ["EDITOR_GERBER_LOG_DIR"] = str(out / "logs")

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from gerber_editor import main as entry
    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.ui.branding import application_icon
    from gerber_editor.ui.splash import SplashScreen

    report = {"checkpoints": []}
    show_maximized = MainWindow.showMaximized

    def shown(window):
        report["editor_shown_after_seconds"] = monotonic() - report["shown_at"]
        show_maximized(window)
        QTimer.singleShot(200, lambda: window.grab().save(str(out / "02_editor.png")))

    class ObservedSplash(SplashScreen):
        def showEvent(self, event):
            super().showEvent(event)
            report["shown_at"] = self._shown_at

            def checkpoint():
                editors = [w for w in QApplication.topLevelWidgets() if isinstance(w, MainWindow)]
                report["checkpoints"].append(
                    {
                        "seconds": monotonic() - self._shown_at,
                        "splash_visible": self.isVisible(),
                        "editor_visible": any(w.isVisible() for w in editors),
                    }
                )
                self.grab().save(str(out / "01_splash.png"))

            QTimer.singleShot(3500, checkpoint)

        def hideEvent(self, event):
            report["splash_hidden_after_seconds"] = monotonic() - self._shown_at
            super().hideEvent(event)

    entry.SplashScreen = ObservedSplash
    MainWindow.showMaximized = shown
    sys.argv = [sys.argv[0], "--demo", "--smoke-test"]
    result = entry.main()
    # QApplication still exists long enough to convert the packaged ICO.
    app = QApplication.instance() or QApplication([])
    icon = application_icon()
    preview = QImage(620, 296, QImage.Format.Format_ARGB32)
    preview.fill(QColor("#f3f5f7"))
    painter = QPainter(preview)
    painter.fillRect(0, 148, 620, 148, QColor("#172334"))
    for row in range(2):
        x = 12
        for size in (16, 24, 32, 48, 64, 128):
            painter.drawPixmap(x, row * 148 + 10, icon.pixmap(size, size))
            x += max(62, size + 16)
    painter.end()
    preview.save(str(out / "03_icon_sizes.png"))
    del report["shown_at"]
    assert result == 0
    assert report["checkpoints"]
    assert all(c["splash_visible"] and not c["editor_visible"] for c in report["checkpoints"])
    assert report["editor_shown_after_seconds"] >= 4
    assert report["splash_hidden_after_seconds"] >= 4
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
