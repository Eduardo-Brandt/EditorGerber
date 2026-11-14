"""Native UI checks and read-only stress import of an entire Gerber folder."""

import argparse
import hashlib
import json
import os
import threading
from pathlib import Path
from time import monotonic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "output" / "v052"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(root / "qa_preferences.json")
    os.environ["EDITOR_GERBER_LOG_DIR"] = str(root / "logs")

    from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from gerber_editor.app.diagnostics import Diagnostics
    from gerber_editor.app.importer import ImportJob
    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import APP_NAME, VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.ui.about_dialog import AboutDialog
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.ui.splash import SplashScreen
    from gerber_editor.ui.support_dialog import SupportDialog
    from scripts.verify_v05 import demo_layers

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    apply_branding(app)
    apply_theme(app)
    diagnostics = Diagnostics()
    editor = MainWindow(language="pt_BR")
    release, started = threading.Event(), threading.Event()
    original_run = ImportJob.run
    original_file_dialog = QFileDialog.getSaveFileName
    errors = []

    def wait_for(predicate, timeout=30):
        deadline = monotonic() + timeout
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(25)
        ready = [False]

        def poll():
            if predicate():
                ready[0] = True
                loop.quit()
            elif monotonic() >= deadline:
                loop.quit()

        timer.timeout.connect(poll)
        timer.start()
        QTimer.singleShot(0, poll)
        loop.exec()
        timer.stop()
        if not ready[0]:
            raise AssertionError("Native Qt check timed out")
        app.processEvents()

    def focus(window):
        window.raise_()
        window.activateWindow()
        wait_for(window.isActiveWindow)

    def unexpected(*values):
        errors.append(str(values[1:]))

    QMessageBox.warning = unexpected
    editor.show_error = lambda *values: errors.append(str(values))
    report = {"version": VERSION}
    try:
        editor.resize(1366, 738)
        editor.show()
        focus(editor)
        splash = SplashScreen(editor.locale)
        splash.show()
        app.processEvents()
        displayed = monotonic()
        splash.grab().save(str(root / "01_splash.png"))
        splash.finish(editor)
        QTest.keyClick(splash, Qt.Key.Key_Escape)
        QTest.qWait(200)
        assert splash.isVisible()
        wait_for(lambda: not splash.isVisible(), timeout=6)
        report["splash_visible_seconds"] = round(monotonic() - displayed, 3)
        assert report["splash_visible_seconds"] >= 3.95
        for layer in demo_layers():
            editor.add_layer(layer)
        QTest.qWait(50)
        editor.canvas.fit_all()
        palette = editor.chrome.tool_palette
        for width, height, image_name in (
            (1366, 738, "02_palette.png"),
            (950, 500, "03_palette_small.png"),
        ):
            editor.resize(width, height)
            QTest.qWait(80)
            assert all(
                palette.rect().contains(button.geometry()) and button.isVisible()
                for button in palette.buttons
            )
            editor.grab().save(str(root / image_name))
        report["all_tools_visible_at_950x500"] = True
        editor.resize(1366, 738)
        editor.show_3d()
        viewer = editor._viewer3d
        focus(viewer)
        wait_for(lambda: viewer.viewport.mesh is not None and viewer._job is None)
        wait_for(lambda: not editor.busy.input_guard.locked)
        assert viewer.viewport.isValid() and not viewer.last_error
        viewer.grab().save(str(root / "04_3d_menus.png"))
        view_menus = [action.menu() for action in viewer.menuBar().actions()]
        assert len(view_menus) == 4
        viewer.realistic_action.trigger()
        assert not viewer.viewport.realistic
        viewer.realistic_action.trigger()
        for dialog_class, image_name in (
            (AboutDialog, "05_about.png"),
            (SupportDialog, "06_support.png"),
        ):
            dialog = dialog_class(viewer)
            dialog.show()
            QTest.qWait(80)
            dialog.grab().save(str(root / image_name))
            dialog.close()
        # Drive the real asynchronous export, recording the selected starting path.
        export_dir = root / "exports"
        export_dir.mkdir(exist_ok=True)
        viewer.remember_export_path(export_dir / "PCB.jpg")
        suggested = []
        QFileDialog.getSaveFileName = lambda *values, **kwargs: (
            suggested.append(values[2]) or str(export_dir / "PCB.wrl"),
            "",
        )
        viewer.export_model("wrl")
        wait_for(lambda: viewer._export_job is None)
        assert (export_dir / "PCB.wrl").is_file()
        assert Path(suggested[0]).parent == export_dir
        viewer.save_jpg(export_dir / "PCB.jpg", 1280, 720)
        report["3d_menus_and_exports"] = True
        focus(editor)
        for layer in editor.layers:
            layer.saved_signature = layer.signature()
        editor.close_all()
        focus(viewer)
        wait_for(lambda: viewer.viewport.mesh is None)
        viewer.close()

        if args.folder:
            paths = sorted(path for path in args.folder.iterdir() if path.is_file())
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
            calls = []

            def paused(job):
                calls.append(job.path.name)
                if len(calls) == 1:
                    started.set()
                    if not release.wait(10):
                        raise TimeoutError("Native QA did not release importer")
                original_run(job)

            ImportJob.run = paused
            focus(editor)
            began = monotonic()
            editor.open_paths_async(paths)
            wait_for(started.is_set)
            QTest.qWait(80)
            editor.grab().save(str(root / "07_batch_processing.png"))
            assert editor.busy.input_guard.locked
            # These native-window events must be discarded while loading.
            QTest.keyClick(editor.windowHandle(), Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
            QTest.mouseClick(editor.windowHandle(), Qt.MouseButton.LeftButton, pos=QPoint(18, 12))
            editor.close()
            assert editor.isVisible() and not editor.layers and not app.activeModalWidget()
            release.set()
            wait_for(lambda: not editor._import_jobs, timeout=900)
            wait_for(lambda: not editor.busy.input_guard.locked)
            assert not errors, errors
            assert len(editor.layers) == len(paths) - 1  # fp-info-cache is auxiliary.
            editor.grab().save(str(root / "08_batch_complete.png"))
            assert before == {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
            }
            report["batch"] = {
                "selected": len(paths),
                "opened": len(editor.layers),
                "ignored_auxiliary": 1,
                "objects": sum(len(layer.objects) for layer in editor.layers),
                "seconds": round(monotonic() - began, 3),
                "input_blocked": True,
                "original_hashes_unchanged": before,
            }
        report["external_gerbers_written"] = False
        report["errors"] = errors
        (root / "native_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
        return 0
    finally:
        release.set()
        ImportJob.run = original_run
        QFileDialog.getSaveFileName = original_file_dialog
        wait_for(lambda: not editor._import_jobs, timeout=900)
        for layer in editor.layers:
            layer.saved_signature = layer.signature()
        editor.close()
        app.processEvents()
        diagnostics.close()


if __name__ == "__main__":
    raise SystemExit(main())
