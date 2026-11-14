"""Native 3D rendering parity, incremental edits, drill voids and model export."""

import importlib.util
import json
import os
import sys
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from time import monotonic
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "output/v09/native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from shapely.geometry import Point as GeometryPoint

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.core.objects import GerberObject
    from gerber_editor.core.primitives import Point
    from gerber_editor.geometry.transforms import translate_geometry
    from gerber_editor.gerber.parser import GerberParser
    from gerber_editor.tools.shapes import create_shape, rectangle_region
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.viewer3d.exporters import export_step, export_wrl

    with ZipFile(root / "Backup/Editor_Gerber_v0.8.1-estavel.2026.11.13.221634.zip") as archive:
        path = out / "baseline_mesh.py"
        path.write_bytes(archive.read("gerber_editor/viewer3d/mesh.py"))
    spec = importlib.util.spec_from_file_location("baseline_mesh", path)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)

    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    edge = GerberLayer("outline", function="Edge.Cuts")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(20, 10)], D("0.1"))
    copper = GerberLayer("copper", function="F.Cu")
    copper.objects = [GerberObject(rectangle_region(Point.of(0, 0), Point.of(20, 10)), None)]
    silk = GerberLayer("silk", function="F.Silk")
    silk.objects = [GerberObject(rectangle_region(Point.of(3, 8), Point.of(6, 9)), None)]
    drill = GerberParser().parse_file(root / "fixtures/drill.gbr")
    for layer in (edge, copper, silk, drill):
        editor.add_layer(layer)
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
        assert predicate(), "Native 3D verification timed out"
        app.processEvents()

    wait_until(lambda: viewer.viewport.mesh is not None and not viewer._dirty)
    assert viewer.isMaximized() and not viewer.last_error
    mesh = viewer.viewport.mesh
    expected = baseline.build_board(editor.layers)
    current = viewer.viewport.grabFramebuffer()
    assert not current.isNull() and not viewer.viewport.error
    viewer.viewport.set_mesh(expected)
    reference = viewer.viewport.grabFramebuffer()
    viewer.viewport.set_mesh(mesh)
    assert current == reference
    current.save(str(out / "01_render_matches_stable.png"))

    original = silk.objects[0]
    silk.objects[0] = replace(original, geometry=translate_geometry(original.geometry, D(1), D(0)))
    started = monotonic()
    editor.refresh()
    viewer.request_refresh()
    wait_until(lambda: not viewer._dirty and viewer._job is None)
    edit_seconds = monotonic() - started
    edited = viewer.viewport.mesh
    assert edited.parts[0] is mesh.parts[0]
    assert next(part for part in edited.parts if part.key == copper.id) is next(
        part for part in mesh.parts if part.key == copper.id
    )
    frame = viewer.viewport.grabFramebuffer()
    assert frame != current
    frame.save(str(out / "02_incremental_silk_edit.png"))
    silk.objects[0] = original
    editor.refresh()
    viewer.request_refresh()
    wait_until(lambda: not viewer._dirty and viewer._job is None)
    assert viewer.viewport.grabFramebuffer() == current

    for index in (0, 2, 1):
        viewer.detail.setCurrentIndex(index)
        wait_until(lambda: not viewer._dirty and viewer._job is None)
        assert not viewer.viewport.grabFramebuffer().isNull()
    assert viewer.viewport.grabFramebuffer() == current
    revision = viewer._revision
    copper.color, copper.opacity = "#aabbcc", 0.5
    editor.refresh()
    assert viewer._revision == revision and not viewer._dirty

    first_hole = drill.objects[0]
    drill.objects[0] = replace(
        first_hole, geometry=translate_geometry(first_hole.geometry, D(2), D(0))
    )
    editor.refresh()
    viewer.request_refresh()
    wait_until(lambda: not viewer._dirty and viewer._job is None)
    changed = viewer.viewport.mesh
    assert changed.outline.covers(GeometryPoint(5, 5))
    assert all(not part.geometry.covers(GeometryPoint(7, 5)) for part in changed.parts)
    viewer.viewport.grabFramebuffer().save(str(out / "03_drill_edit.png"))
    export_step(changed, out / "verified_updated_board.step")
    export_wrl(changed, out / "verified_updated_board.wrl")
    assert not viewer.last_error and not viewer.viewport.error
    report = {
        "version": VERSION,
        "platform": app.platformName(),
        "render_identical_to_stable_reference": True,
        "unchanged_substrate_and_copper_reused": True,
        "incremental_silk_edit_seconds_including_editor_refresh": edit_seconds,
        "undo_restores_identical_framebuffer": True,
        "detail_switches_preserve_framebuffer": True,
        "color_opacity_do_not_invalidate_3d": True,
        "drill_edit_updates_real_voids": True,
        "step_wrl_exported": True,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    viewer.close()
    editor.close()
    app.quit()


if __name__ == "__main__":
    main()
