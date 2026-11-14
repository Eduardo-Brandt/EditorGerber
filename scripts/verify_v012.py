"""Windows verification of real Excellon imports, PCB progress and shape editing."""

import hashlib
import json
import os
import sys
from decimal import Decimal as D
from pathlib import Path
from time import monotonic, sleep


def main():
    root = Path(__file__).resolve().parents[1]
    source = Path(sys.argv[1])
    out = root / "output/v012/native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.core.primitives import Point
    from gerber_editor.gerber.writer import GerberWriter, SaveMode
    from gerber_editor.tools.shapes import create_shape
    from gerber_editor.ui.array_dialog import ArrayDialog
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.ui.parameter_dialog import ParameterDialog
    from gerber_editor.viewer3d.window import Viewer3DWindow

    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()
    }
    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    errors = []
    editor.show_error = lambda title, error: errors.append((title, str(error)))
    editor.showMaximized()

    def wait(predicate, timeout=300):
        deadline = monotonic() + timeout
        while not predicate() and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        assert predicate(), "Native check timed out"
        assert not errors, errors

    paths = sorted(source.glob("*.gbr")) + sorted(source.glob("*.drl"))
    editor.open_paths_async(paths)
    wait(lambda: not editor._import_jobs and not editor.import_progress.active)
    assert len(editor.layers) == len(paths)
    drills = [layer for layer in editor.layers if layer.file_format == "excellon"]
    assert len(drills) == 2 and sum(len(layer.objects) for layer in drills) == 1076
    editor.grab().save(str(out / "01_excellon_imported.png"))
    viewer = Viewer3DWindow(editor)
    editor._viewer3d = viewer
    progress, captured = [], set()
    phase = "initial"

    def record(value):
        progress.append((phase, value))
        if 68 <= value < 99 and phase not in captured:
            captured.add(phase)
            viewer.grab().save(str(out / f"02_progress_{phase}.png"))

    viewer.progress.valueChanged.connect(record)
    viewer.showMaximized()
    viewer.activateWindow()
    viewer.rebuild()
    wait(lambda: viewer._job is None and viewer.viewport.mesh is not None)
    assert not viewer.last_error
    assert viewer.progress.value() == 100
    viewer.grab().save(str(out / "03_pcb_with_drills.png"))
    mesh = viewer.viewport.mesh
    from shapely.geometry import Point as ShapePoint

    first_hole = next(layer for layer in drills if layer.objects).objects[0].geometry.position
    assert not mesh.outline.covers(ShapePoint(float(first_hole.x), float(first_hole.y)))
    phase = "update"
    viewer.detail.setCurrentIndex(0)
    viewer.rebuild()
    wait(lambda: viewer._job is None and viewer._mesh_settings[1] == 0.01)
    assert viewer.progress.value() == 100 and not viewer.last_error
    viewer.close()
    for layer in drills:
        assert GerberWriter().serialize(layer) == (source / layer.name).read_bytes()
        for suffix in ("drl", "gbr"):
            GerberWriter().save(
                layer,
                out / f"{Path(layer.name).stem}_copy.{suffix}",
                SaveMode.NORMALIZED,
                overwrite=True,
            )
    for layer in editor.layers:
        layer.visible = False
    shapes = GerberLayer("Formas_F_Silkscreen.gbr", function="F.Silk")
    for kind, points in [
        ("circle", [Point.of(20, 20), Point.of(25, 20)]),
        ("arc", [Point.of(35, 20), Point.of(40, 20), Point.of(35, 25)]),
        ("rectangle", [Point.of(50, 15), Point.of(62, 25)]),
        ("square", [Point.of(68, 15), Point.of(78, 25)]),
    ]:
        shapes.objects += create_shape(shapes, kind, points, D("0.2"), filled=True)
    editor.add_layer(shapes)
    editor.activateWindow()
    QTest.qWait(100)
    editor.grab().save(str(out / "04_filled_shapes.png"))
    circles = GerberLayer("Circulos_F_Silkscreen.gbr", function="F.Silk")
    for x, y, r, width in [(15, 5, 2, "0.2"), (30, 8, 3, "0.4"), (45, 12, 4, "0.6")]:
        circles.objects += create_shape(
            circles, "circle", [Point.of(x, y), Point.of(x + r, y)], D(width)
        )
    editor.add_layer(circles)
    editor.canvas.select_all()
    before_centers = [o.geometry.center for o in circles.objects]
    before_widths = [o.aperture.width for o in circles.objects]
    execute = ParameterDialog.exec

    def edit(dialog):
        def apply():
            dialog.fields["radius"].setValue(5)
            dialog.grab().save(str(out / "05_bulk_properties.png"))
            dialog.accept()

        QTimer.singleShot(120, apply)
        return execute(dialog)

    ParameterDialog.exec = edit
    editor.edit_properties()
    assert [o.geometry.center for o in circles.objects] == before_centers
    assert [o.aperture.width for o in circles.objects] == before_widths
    assert all(o.geometry.radius == 5 for o in circles.objects)
    editor.grab().save(str(out / "06_circles_edited.png"))
    array = ArrayDialog(Point.of(0, 0), editor)
    array.kind.setCurrentIndex(1)
    array.by_radius.setChecked(True)
    array.radius.setValue(12)
    array.count.setValue(6)
    array.show()
    QTest.qWait(80)
    array.grab().save(str(out / "07_polar_radius.png"))
    array.close()
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before
    report = {
        "version": VERSION,
        "files_opened": len(paths),
        "excellon_holes": 1076,
        "3d_progress": progress,
        "filled_shapes": 4,
        "bulk_centers_preserved": True,
        "bulk_widths_preserved": True,
        "original_files_unchanged": True,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    editor.close()
    app.processEvents()
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
