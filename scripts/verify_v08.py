"""Native verification of drill voids, icon sizes, layer order and maximization."""

import argparse
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from time import monotonic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drill", type=Path, help="Optional real Gerber drill input, read-only")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / "output/v08/native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")
    os.environ["EDITOR_GERBER_LOG_DIR"] = str(out / "logs")

    from PySide6.QtCore import QEventLoop, Qt, QTimer
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from shapely.geometry import Point as GeometryPoint

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.core.primitives import Point
    from gerber_editor.gerber.parser import GerberParser
    from gerber_editor.tools.drilling import drill_geometry
    from gerber_editor.tools.shapes import create_shape
    from gerber_editor.ui.branding import application_icon, apply_branding
    from gerber_editor.viewer3d.exporters import export_step, export_wrl
    from gerber_editor.viewer3d.mesh import build_board

    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    errors = []
    editor.show_error = lambda *values: errors.append(str(values))
    QMessageBox.warning = lambda *values: errors.append(str(values))
    editor.showMaximized()

    def wait_until(predicate, timeout=180):
        loop = QEventLoop()
        timer = QTimer()
        deadline = monotonic() + timeout

        def ready():
            if predicate() or monotonic() >= deadline:
                loop.quit()

        timer.timeout.connect(ready)
        timer.start(25)
        QTimer.singleShot(0, ready)
        loop.exec()
        timer.stop()
        assert predicate(), "Native verification timed out"
        app.processEvents()

    app.processEvents()
    assert editor.isMaximized()
    fixture = (root / "fixtures/drill.gbr").read_bytes()
    source_hash = hashlib.sha256(fixture).hexdigest()
    paths = []
    definitions = [
        ("B_Cu.gbr", "Copper,L4,Bot", "%ADD10R,20X10*%D10*X10000000Y5000000D03*"),
        ("inner2.gbr", "Copper,L3,Inr", "%ADD10C,1*%D10*X2000000Y5000000D02*X18000000Y5000000D01*"),
        ("F_silk.gbr", "Legend,Top", "%ADD10C,0.15*%D10*X2000000Y8000000D02*X7000000Y8000000D01*"),
        ("F_Cu.gbr", "Copper,L1,Top", "%ADD10R,20X10*%D10*X10000000Y5000000D03*"),
        ("inner1.gbr", "Copper,L2,Inr", "%ADD10C,1*%D10*X2000000Y6000000D02*X18000000Y6000000D01*"),
        (
            "F_mask.gbr",
            "Soldermask,Top",
            "%ADD10C,2.2*%D10*X5000000Y5000000D03*%ADD11C,1.8*%D11*X12000000Y3000000D02*X15000000Y3000000D01*",
        ),
        (
            "outline.gbr",
            "Profile,NP",
            "%ADD10C,0.1*%D10*X0Y0D02*X20000000Y0D01*X20000000Y10000000D01*X0Y10000000D01*X0Y0D01*",
        ),
    ]
    for name, function, body in definitions:
        path = out / name
        path.write_text(
            f"%FSLAX46Y46*%%MOMM*%%TF.FileFunction,{function}*%{body}M02*", encoding="ascii"
        )
        paths.append(path)
    drill_path = out / "drill.gbr"
    drill_path.write_bytes(fixture)
    paths.insert(1, drill_path)
    editor.open_paths_async(paths)
    wait_until(lambda: not editor._import_jobs)
    assert not errors, errors
    visual_roles = [layer.function for layer in reversed(editor.layers)]
    assert visual_roles == [
        "F.Silk",
        "F.Mask",
        "F.Cu",
        "In2.Cu",
        "In3.Cu",
        "B.Cu",
        "Drill.PTH",
        "Edge.Cuts",
    ]
    editor.grab().save(str(out / "01_editor_maximized.png"))
    original = list(editor.layers)
    signatures = {layer.id: layer.signature() for layer in original}
    selected = editor.layer_panel.tree.topLevelItem(5)
    editor.layer_panel.tree.setCurrentItem(selected)
    app.processEvents()
    active = editor.active_layer
    QTest.mouseClick(editor.layer_panel.up_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: editor.layers != original)
    assert editor.active_layer is active
    assert editor.layers.index(active) == original.index(active) + 1
    editor.grab().save(str(out / "02_layer_moved.png"))
    editor.history.undo()
    assert editor.layers == original
    editor.history.redo()
    editor.history.undo()
    assert {layer.id: layer.signature() for layer in editor.layers} == signatures

    icon = application_icon()
    preview = QImage(600, 280, QImage.Format.Format_ARGB32)
    preview.fill(QColor("#f3f5f7"))
    painter = QPainter(preview)
    painter.fillRect(0, 140, 600, 140, QColor("#172334"))
    for row in range(2):
        x = 10
        for size in (16, 24, 32, 48, 64, 128):
            painter.drawPixmap(x, row * 140 + 8, icon.pixmap(size, size))
            x += max(60, size + 16)
    painter.end()
    preview.save(str(out / "03_icon_sizes.png"))
    editor.show_3d()
    viewer = editor._viewer3d
    wait_until(lambda: viewer.viewport.mesh is not None or bool(viewer.last_error))
    assert not viewer.last_error, viewer.last_error
    assert viewer.isMaximized()
    mesh = viewer.viewport.mesh
    for point in ((5, 5), (13.5, 3), (18, 8)):
        assert all(not part.geometry.covers(GeometryPoint(*point)) for part in mesh.parts)
    assert not viewer.viewport.error, viewer.viewport.error
    viewer.viewport.standard_view("top")
    app.processEvents()
    frame = viewer.viewport.grabFramebuffer()
    assert not frame.isNull()
    frame.save(str(out / "04_3d_through_holes.png"))
    viewer.grab().save(str(out / "05_viewer_maximized.png"))
    viewer.viewport.standard_view("iso")
    app.processEvents()
    viewer.viewport.grabFramebuffer().save(str(out / "06_3d_inner_walls.png"))
    export_step(mesh, out / "verified_drilled_board.step")
    export_wrl(mesh, out / "verified_drilled_board.wrl")
    report = {
        "version": VERSION,
        "platform": app.platformName(),
        "editor_maximized": editor.isMaximized(),
        "viewer_maximized": viewer.isMaximized(),
        "automatic_visual_order": visual_roles,
        "reorder_undo_redo": True,
        "object_data_unchanged": True,
        "through_drill_slot_and_small_hole": True,
        "native_opengl_framebuffer": [frame.width(), frame.height()],
        "step_wrl_exported": True,
        "drill_fixture_sha256": source_hash,
        "errors": errors,
    }
    assert hashlib.sha256((root / "fixtures/drill.gbr").read_bytes()).hexdigest() == source_hash
    if args.drill:
        data = args.drill.read_bytes()
        real = GerberParser().parse_file(args.drill)
        bounds = real.bounds
        outline = GerberLayer("verification_outline.gbr", function="Edge.Cuts")
        outline.objects = create_shape(
            outline,
            "rectangle",
            [
                Point.of(str(bounds.left - 1), str(bounds.bottom - 1)),
                Point.of(str(bounds.right + 1), str(bounds.top + 1)),
            ],
            Decimal("0.1"),
        )
        actual = build_board([outline, real])
        assert actual.outline.intersection(drill_geometry([real])).area < 1e-8
        assert args.drill.read_bytes() == data
        report["real_drill"] = {
            "file": str(args.drill),
            "objects": len(real.objects),
            "function": real.function,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_unchanged": True,
            "all_drill_centers_are_voids": True,
            "mesh_triangles": actual.triangles,
        }
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    viewer.close()
    editor.close()
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
