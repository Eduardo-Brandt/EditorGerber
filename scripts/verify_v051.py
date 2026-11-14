"""Native Windows regression: animated feedback, layer clicks and focus-driven 3D."""

import argparse
import hashlib
import json
import os
import threading
from decimal import Decimal
from pathlib import Path
from time import monotonic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "output" / "v051"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(root / "qa_preferences.json")
    os.environ["EDITOR_GERBER_LOG_DIR"] = str(root / "logs")

    import shiboken6
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gerber_editor.app.diagnostics import Diagnostics
    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import APP_NAME, VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.commands.edit_commands import AddObjects
    from gerber_editor.core.primitives import Point
    from gerber_editor.tools.drawing import create_line
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.viewer3d import window as viewer_module
    from scripts.verify_v05 import demo_layers

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    apply_branding(app)
    apply_theme(app)
    diagnostics = Diagnostics()
    editor = MainWindow(language="pt_BR")
    started, release = threading.Event(), threading.Event()
    original_build = viewer_module.build_board
    builds = []

    def observed_build(*values):
        builds.append(1)
        if len(builds) == 1:
            started.set()
            if not release.wait(10):
                raise TimeoutError("QA did not release mesh worker")
        return original_build(*values)

    viewer_module.build_board = observed_build

    def wait_for(predicate, timeout=15):
        deadline = monotonic() + timeout
        while not predicate() and monotonic() < deadline:
            QTest.qWait(15)
        if not predicate():
            raise AssertionError("Native Qt operation timed out")

    def focus(window):
        window.raise_()
        window.activateWindow()
        wait_for(window.isActiveWindow)

    def unexpected_dialog(*values):
        raise AssertionError(f"Unexpected warning: {values[1:]}")

    QMessageBox.warning = unexpected_dialog
    try:
        for layer in demo_layers():
            editor.add_layer(layer)
        editor.show()
        focus(editor)
        editor.canvas.fit_all()
        token = editor.busy.begin("Carregando…")
        QTest.qWait(100)
        overlay = editor.busy.overlay
        angle = overlay.hourglass.angle
        editor.grab().save(str(root / "01_processing.png"))
        QTest.qWait(160)
        assert overlay.hourglass.angle != angle
        editor.grab().save(str(root / "02_processing_rotated.png"))
        center = editor.canvas.mapTo(editor, editor.canvas.rect().center())
        assert (overlay.geometry().center() - center).manhattanLength() <= 2
        editor.busy.end(token)

        tree = editor.layer_panel.tree
        item = tree.topLevelItem(1)
        key = item.data(0, Qt.ItemDataRole.UserRole)
        target = next(layer for layer in editor.layers if layer.id == key)
        for _ in range(30):
            rect = tree.visualItemRect(item)
            QTest.mouseClick(
                tree.viewport(),
                Qt.MouseButton.LeftButton,
                pos=QPoint(rect.left() + 85, rect.center().y()),
            )
            QTest.qWait(3)
            assert editor.active_layer is target
            for checked in (False, True):
                QTest.mouseClick(
                    tree.viewport(),
                    Qt.MouseButton.LeftButton,
                    pos=QPoint(rect.left() + 9, rect.center().y()),
                )
                QTest.qWait(3)
                assert target.visible is checked
                assert shiboken6.isValid(item)

        editor.show_3d()
        viewer = editor._viewer3d
        focus(viewer)
        wait_for(started.is_set)
        QTest.qWait(100)
        angle = viewer.busy.overlay.hourglass.angle
        viewer.grab().save(str(root / "03_3d_processing.png"))
        QTest.qWait(160)
        assert viewer.busy.overlay.hourglass.angle != angle
        release.set()
        wait_for(lambda: viewer.viewport.mesh is not None and viewer._job is None)
        assert not viewer.last_error and viewer.viewport.isValid()
        first_mesh = viewer.viewport.mesh
        viewer.viewport.yaw, viewer.viewport.distance, viewer.viewport.pan_x = 37, 160, 4
        QTest.qWait(80)
        viewer.grab().save(str(root / "04_before_edit.png"))
        focus(editor)
        copper = next(layer for layer in editor.layers if layer.function == "F.Cu")
        for y in (32, 34, 36):
            obj = create_line(copper, Point.of(28, y), Point.of(55, y), Decimal("0.8"))
            with editor.busy.operation("Atualizando geometria…"):
                editor.history.push(AddObjects(copper, [obj]))
        QTest.qWait(120)
        assert not viewer.isActiveWindow()
        assert len(builds) == 1 and viewer.viewport.mesh is first_mesh
        focus(viewer)
        wait_for(lambda: not viewer._dirty and viewer._job is None)
        assert len(builds) == 2 and viewer.viewport.mesh is not first_mesh
        assert (viewer.viewport.yaw, viewer.viewport.distance, viewer.viewport.pan_x) == (
            37,
            160,
            4,
        )
        QTest.qWait(80)
        viewer.grab().save(str(root / "05_after_return.png"))
        focus(editor)
        for layer in editor.layers:
            layer.saved_signature = layer.signature()
        editor.close_all()
        assert viewer.viewport.mesh is not None
        focus(viewer)
        wait_for(lambda: viewer.viewport.mesh is None)
        viewer.close()
        report = {
            "version": VERSION,
            "native_opengl": True,
            "editor_spinner_rotates": True,
            "viewer_spinner_rotates": True,
            "centered": True,
            "layer_tree_mouse_cycles": 30,
            "mesh_builds": len(builds),
            "edits_coalesced": 3,
            "deferred_refresh_on_activation": True,
            "camera_preserved": True,
            "closed_layers_clear_3d_on_activation": True,
            "external_gerbers_written": False,
        }
        if args.real:
            before = args.real.read_bytes()
            focus(editor)
            editor.open_paths_async([args.real])
            wait_for(lambda: not editor._import_jobs, timeout=60)
            assert len(editor.layers) == 1
            QTest.qWait(80)
            editor.grab().save(str(root / "06_real_gerber.png"))
            item = tree.topLevelItem(0)
            for _ in range(10):
                item.setCheckState(0, Qt.CheckState.Unchecked)
                QTest.qWait(5)
                item.setCheckState(0, Qt.CheckState.Checked)
                QTest.qWait(5)
                assert shiboken6.isValid(item)
            assert args.real.read_bytes() == before
            report["real"] = {
                "objects": len(editor.layers[0].objects),
                "visibility_cycles": 10,
                "sha256_before_after": hashlib.sha256(before).hexdigest(),
            }
        (root / "native_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
        return 0
    finally:
        release.set()
        if editor._viewer3d:
            wait_for(lambda: editor._viewer3d._job is None)
        viewer_module.build_board = original_build
        for layer in editor.layers:
            layer.saved_signature = layer.signature()
        editor.close()
        app.processEvents()
        diagnostics.close()


if __name__ == "__main__":
    raise SystemExit(main())
