"""Verify native OpenGL detail changes and cached GPU uploads."""

import json
import os
from pathlib import Path
from time import monotonic


def main():
    out = Path(__file__).resolve().parents[1] / "output/v081/native3d"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.ui.branding import apply_branding

    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    editor.load_demo()
    editor.showMaximized()
    editor.show_3d()
    viewer = editor._viewer3d

    def wait_until(predicate):
        loop, timer = QEventLoop(), QTimer()
        deadline = monotonic() + 30

        def check():
            if predicate() or monotonic() >= deadline:
                loop.quit()

        timer.timeout.connect(check)
        timer.start(10)
        QTimer.singleShot(0, check)
        loop.exec()
        timer.stop()
        assert predicate(), "Native 3D operation timed out"
        app.processEvents()

    wait_until(lambda: viewer.viewport.mesh is not None and not viewer._dirty)
    assert not viewer.last_error
    assert viewer.isMaximized()
    normal, geometry = viewer.viewport.mesh, viewer._geometry
    viewer.viewport.yaw, viewer.viewport.distance, viewer.viewport.pan_x = 17, 94, 3
    before = viewer.viewport.grabFramebuffer()
    assert not before.isNull() and not viewer.viewport.error
    before.save(str(out / "01_normal.png"))
    timings = {}
    for index, name in ((0, "fine"), (2, "fast"), (1, "normal_cached"), (0, "fine_cached")):
        started = monotonic()
        viewer.detail.setCurrentIndex(index)
        wait_until(lambda: not viewer._dirty and viewer._job is None)
        assert viewer._geometry is geometry
        assert not viewer.last_error
        assert (viewer.viewport.yaw, viewer.viewport.distance, viewer.viewport.pan_x) == (17, 94, 3)
        frame = viewer.viewport.grabFramebuffer()
        assert not frame.isNull() and not viewer.viewport.error
        frame.save(str(out / f"{name}.png"))
        timings[name] = monotonic() - started
        if index == 1:
            assert viewer.viewport.mesh is normal and frame == before
    report = {
        "platform": "Windows/OpenGL",
        "geometry_reused": True,
        "cached_mesh_and_framebuffer_identical": True,
        "camera_preserved": True,
        "triangles": {str(key): mesh.triangles for key, mesh in viewer._mesh_cache.items()},
        "timings_seconds_including_framebuffer_capture": timings,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    viewer.close()
    editor.close()
    app.quit()


if __name__ == "__main__":
    main()
