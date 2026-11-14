"""Render the 0.4 editor or exercise the native OpenGL 3D window.

python -m scripts.verify_v04 --native-3d
"""

import argparse
import json
import os
from decimal import Decimal as D
from pathlib import Path


def sample_board():
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.core.objects import Aperture, GerberObject, Polarity
    from gerber_editor.core.primitives import Flash, Line, Point
    from gerber_editor.core.text_entity import TextEntity
    from gerber_editor.tools.shapes import create_shape
    from gerber_editor.tools.text_session import text_objects

    edge = GerberLayer("PCB-Outline.gbr", function="Edge.Cuts", color="#e7d153")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(80, 50)], D("0.15"))
    copper = GerberLayer("PCB-F_Cu.gbr", function="F.Cu", color="#df6565")
    mask = GerberLayer("PCB-F_Mask.gbr", function="F.Mask", color="#5ebd81")
    bottom = GerberLayer("PCB-B_Cu.gbr", function="B.Cu", color="#65a2e6")
    silk = GerberLayer("PCB-F_Silkscreen.gbr", function="F.Silk")
    pad = Aperture(10, "C", (D("3.5"), D("1.2")))
    opening = Aperture(11, "C", (D("4.1"),))
    track = Aperture(12, "C", (D("0.7"),))
    for x in range(12, 69, 8):
        for y in (12, 38):
            position = Point.of(x, y)
            copper.objects.append(GerberObject(Flash(position), pad))
            mask.objects.append(GerberObject(Flash(position), opening))
            edge.objects += create_shape(
                edge, "circle", [position, Point(D(x) + D("0.6"), D(y))], D("0.1")
            )
        copper.objects.append(GerberObject(Line(Point.of(x, 12), Point.of(x, 38)), track))
    bottom.objects = [
        GerberObject(Line(Point.of(12, 12), Point.of(68, 12)), track),
        GerberObject(Line(Point.of(12, 38), Point.of(68, 38)), track),
    ]
    entity = TextEntity("Editor Gerber", Point.of(17, 23), D("3.0"), D("0.25"), "Segoe UI")
    silk.objects = text_objects(silk, entity, Polarity.DARK)
    silk.objects += create_shape(silk, "rectangle", [Point.of(9, 8), Point.of(71, 42)], D("0.25"))
    for layer in (edge, copper, mask, bottom, silk):
        layer.saved_signature = layer.signature()
    return [edge, copper, mask, bottom, silk]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-3d", action="store_true")
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "output" / "v04"
    root.mkdir(parents=True, exist_ok=True)
    (root / "qa_preferences.json").write_text("{}", encoding="utf-8")
    os.environ["EDITOR_GERBER_SETTINGS"] = str(root / "qa_preferences.json")
    os.environ["EDITR_GERBER_SETTINGS"] = str(root / "qa_preferences.json")
    if not args.native_3d:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import numpy as np
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import APP_NAME
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.gerber.writer import GerberWriter, SaveMode
    from gerber_editor.tools.vector_text import ensure_offscreen_font
    from gerber_editor.viewer3d.mesh import build_board

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    ensure_offscreen_font()
    apply_theme(app)
    window = MainWindow(language="pt_BR")
    for layer in sample_board():
        window.add_layer(layer)
    window.show()
    app.processEvents()
    window.canvas.fit_all()
    if not args.native_3d:
        window.grab().save(str(root / "01_editor.png"))
        for layer in window.layers:
            GerberWriter().save(layer, root / layer.name, SaveMode.NORMALIZED, overwrite=True)
        source_unchanged = None
        if args.real:
            import hashlib

            from gerber_editor.core.primitives import Point
            from gerber_editor.geometry.rigid import RigidTransform, remap_apertures
            from gerber_editor.tools.clipboard import decode, encode
            from gerber_editor.tools.shapes import layer_quantum

            source = args.real.read_bytes()
            layer = window.parser.parse_file(args.real)
            mesh = build_board([layer])
            original = list(layer.objects)
            selected, _ = decode(encode(original[:3], Point.of(0, 0)))
            copies = [
                RigidTransform(angle=30, dx=D(100), mirror_x=True).object(
                    obj, layer_quantum(layer), clone=True
                )
                for obj in selected
            ]
            layer.objects += remap_apertures(layer, copies)
            for mode in SaveMode:
                GerberWriter().save(
                    layer, root / f"srlc_v04_{mode.value}.gbr", mode, overwrite=True
                )
            assert layer.objects[: len(original)] == original
            assert args.real.read_bytes() == source
            source_unchanged = {
                "sha256": hashlib.sha256(source).hexdigest(),
                "original_objects": len(original),
                "copied_objects": len(copies),
                "original_objects_preserved": True,
                "both_exports": "passed",
                "triangles": mesh.triangles,
            }
        window.canvas.object_items[window.active_layer.objects[0].id].setSelected(True)
        window.show_properties()
        window.grab().save(str(root / "02_properties.png"))
        from gerber_editor.core.primitives import Line, Point
        from gerber_editor.ui.array_dialog import ArrayDialog
        from gerber_editor.ui.object_dialog import ObjectDialog
        from gerber_editor.ui.splash import SplashScreen
        from gerber_editor.ui.text_dialog import TextDialog

        line = next(obj for obj in window.layers[1].objects if isinstance(obj.geometry, Line))
        entity = window.active_layer.objects[0].text_entity
        dialogs = [
            (ObjectDialog(line, window), "06_geometry_properties.png"),
            (TextDialog(entity.position, window, entity), "07_editable_text.png"),
            (ArrayDialog(Point.of(40, 25), window), "08_array.png"),
        ]
        for dialog, name in dialogs:
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(root / name))
            dialog.reject()
        splash = SplashScreen(window.locale)
        splash.show()
        app.processEvents()
        splash.grab().save(str(root / "09_splashscreen.png"))
        splash.close()
        report = {
            "layers": len(window.layers),
            "mesh_triangles": build_board(window.layers).triangles,
            "real": source_unchanged,
        }
        (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        window.close()
        return 0
    window.show_3d()
    viewer = window._viewer3d
    elapsed = 0

    def check():
        nonlocal elapsed
        elapsed += 1
        if viewer.last_error:
            print("3D ERROR:", viewer.last_error, flush=True)
            app.exit(1)
            return
        if viewer.viewport.mesh and viewer.viewport.isValid():
            image = viewer.viewport.grabFramebuffer().convertToFormat(QImage.Format.Format_RGB32)
            pixels = np.frombuffer(image.bits(), dtype=np.uint8).reshape(
                image.height(), image.bytesPerLine()
            )
            rgb = pixels[:, : image.width() * 4].reshape(image.height(), image.width(), 4)[:, :, :3]
            image.save(str(root / "03_native_3d.png"))
            if rgb.reshape(-1, 3).std(axis=0).max() < 8:
                print("3D ERROR: empty framebuffer", flush=True)
                app.exit(1)
                return
            viewer.grab().save(str(root / "04_native_3d_window.png"))
            viewer.viewport.standard_view("bottom")
            app.processEvents()
            viewer.viewport.grabFramebuffer().save(str(root / "05_native_3d_bottom.png"))
            fmt = viewer.viewport.context().format()
            report = {
                "opengl_context": f"{fmt.majorVersion()}.{fmt.minorVersion()}",
                "triangles": viewer.viewport.mesh.triangles,
                "parts": len(viewer.viewport.mesh.parts),
                "framebuffer": "passed",
            }
            window.set_language("en")
            window.set_units("in")
            assert viewer.thickness.mm == D("1.6")
            assert viewer.thickness.suffix() == " in"
            assert "3D viewer" in viewer.windowTitle()
            app.processEvents()
            viewer.grab().save(str(root / "10_english_3d.png"))
            report["english_and_inch_display"] = "passed"
            (root / "native_3d_report.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps(report, indent=2), flush=True)
            viewer.close()
            window.close()
            app.quit()
        elif elapsed > 40:
            print("3D ERROR: timeout", flush=True)
            app.exit(1)
        else:
            QTimer.singleShot(500, check)

    QTimer.singleShot(1000, check)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
