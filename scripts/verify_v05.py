"""Native rendering/export QA and reproducible 0.5 feature captures."""

import argparse
import json
import os
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from uuid import uuid4


def demo_layers():
    from gerber_editor.app.fabrication_actions import ROUTING_ATTRIBUTES
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.core.objects import Aperture, GerberObject
    from gerber_editor.core.primitives import Line, Point
    from gerber_editor.tools.shapes import create_shape
    from scripts.verify_v04 import sample_board

    layers = sample_board()
    backside = GerberLayer("PCB-B_Mask.gbr", function="B.Mask")
    backside.objects = [replace(obj, id=uuid4().hex) for obj in layers[2].objects]
    layers.append(backside)
    routing = GerberLayer(
        "PCB-Route_Cuts.gbr", function="Route.Cuts", color="#ff77cc", attributes=ROUTING_ATTRIBUTES
    )
    routing.objects = [
        GerberObject(Line(Point.of(30, 18), Point.of(50, 18)), Aperture(10, "C", (D(2),)))
    ]
    routing.objects += create_shape(
        routing, "circle", [Point.of(65, 25), Point.of(68, 25)], D("0.1")
    )
    layers.append(routing)
    for layer in layers:
        layer.saved_signature = layer.signature()
    return layers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-3d", action="store_true")
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "output" / "v05"
    root.mkdir(parents=True, exist_ok=True)
    preferences = root / ("native_preferences.json" if args.native_3d else "preferences.json")
    preferences.write_text("{}", encoding="utf-8")
    os.environ["EDITOR_GERBER_SETTINGS"] = str(preferences)
    if args.native_3d:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import APP_NAME, VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.tools.vector_text import ensure_offscreen_font
    from gerber_editor.ui.branding import apply_branding

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    apply_branding(app)
    ensure_offscreen_font()
    apply_theme(app)
    window = MainWindow(language="pt_BR")
    for layer in demo_layers():
        window.add_layer(layer)
    window.create_fiducial(
        __import__("gerber_editor.core.primitives", fromlist=["Point"]).Point.of(6, 25),
        D(1),
        D(2),
        "F",
    )
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.show()
    app.processEvents()
    window.canvas.fit_all()
    if not args.native_3d:
        from gerber_editor.core.primitives import Point
        from gerber_editor.gerber.writer import GerberWriter
        from gerber_editor.ui.about_dialog import AboutDialog
        from gerber_editor.ui.fabrication_dialogs import CutoutDialog, FiducialDialog
        from gerber_editor.ui.object_dialog import ObjectDialog
        from gerber_editor.ui.splash import SplashScreen
        from gerber_editor.ui.support_dialog import SupportDialog
        from gerber_editor.viewer3d.mesh import build_board

        window.grab().save(str(root / "01_editor.png"))
        dialogs = [
            (AboutDialog(window), "02_about.png"),
            (SupportDialog(window), "03_support.png"),
            (ObjectDialog(window.layers[1].objects[-2], window), "04_line_editor.png"),
            (FiducialDialog(Point.of(6, 25), window), "05_fiducial.png"),
            (CutoutDialog(window), "06_cutouts.png"),
        ]
        for dialog, name in dialogs:
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(root / name))
            dialog.reject()
            if isinstance(dialog, SupportDialog):
                dialog.image.save(str(root / "Pix_Editor_Gerber.png"))
                (root / "Pix_Copia_e_Cola.txt").write_text(dialog.payload, encoding="utf-8")
        splash = SplashScreen(window.locale)
        splash.show()
        app.processEvents()
        splash.grab().save(str(root / "07_splashscreen.png"))
        splash.close()
        for layer in window.layers:
            GerberWriter().save(layer, root / layer.name, overwrite=True)
        report = {
            "version": VERSION,
            "triangles": build_board(window.layers).triangles,
            "original_gerbers_written": False,
        }
        if args.real:
            import hashlib

            before = args.real.read_bytes()
            layer = window.parser.parse_file(args.real)
            mesh = build_board([layer])
            assert args.real.read_bytes() == before
            report["real"] = {
                "objects": len(layer.objects),
                "triangles": mesh.triangles,
                "sha256": hashlib.sha256(before).hexdigest(),
            }
        (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
        window.close()
        return 0
    window.show_3d()
    viewer = window._viewer3d
    attempts = 0

    def fail(*values):
        print("QA ERROR:", *values, flush=True)
        app.exit(1)

    QMessageBox.warning = fail

    def check():
        nonlocal attempts
        attempts += 1
        if viewer.last_error:
            fail(viewer.last_error)
            return
        if viewer.viewport.mesh and viewer.viewport.isValid():
            mesh = viewer.viewport.mesh
            viewer.grab().save(str(root / "08_native_3d.png"))
            viewer.save_jpg(root / "PCB_2560x1440.jpg", 2560, 1440)
            from PySide6.QtGui import QImage

            image = QImage(str(root / "PCB_2560x1440.jpg"))
            assert (image.width(), image.height()) == (2560, 1440)
            from PySide6.QtTest import QTest

            viewer.flip_action.trigger()
            QTest.qWait(650)
            assert abs(viewer.viewport.flip_angle % 360 - 180) < 0.001
            viewer.grab().save(str(root / "09_native_flipped.png"))
            viewer.flip_action.trigger()
            QTest.qWait(650)
            assert viewer.viewport.flip_angle % 360 < 0.001
            from gerber_editor.viewer3d.exporters import export_wrl

            export_wrl(mesh, root / "PCB_with_cutouts.wrl")
            from PySide6.QtWidgets import QFileDialog

            target = root / "PCB_with_cutouts.step"
            if target.exists():
                target.unlink()
            original_dialog = QFileDialog.getSaveFileName
            QFileDialog.getSaveFileName = lambda *args, **kwargs: (str(target), "")
            try:
                viewer.export_model("step")
            finally:
                QFileDialog.getSaveFileName = original_dialog
            for _ in range(600):
                if viewer._export_job is None:
                    break
                QTest.qWait(100)
            assert viewer._export_job is None and target.is_file()
            owner = 0
            if os.name == "nt":
                import ctypes

                get_owner = ctypes.windll.user32.GetWindow
                get_owner.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                get_owner.restype = ctypes.c_void_p
                owner = get_owner(int(viewer.winId()), 4) or 0
                assert owner == 0
            report = {
                "version": VERSION,
                "context": str(viewer.viewport.context().format().majorVersion()),
                "triangles": mesh.triangles,
                "materials": len(mesh.parts),
                "jpg_size": [2560, 1440],
                "step_bytes": (root / "PCB_with_cutouts.step").stat().st_size,
                "wrl_bytes": (root / "PCB_with_cutouts.wrl").stat().st_size,
                "native_owner": owner,
                "icon": not viewer.windowIcon().isNull(),
                "animated_flip": True,
                "asynchronous_step_export": True,
            }
            (root / "native_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2), flush=True)
            viewer.close()
            window.close()
            app.quit()
        elif attempts < 60:
            QTimer.singleShot(500, guarded_check)
        else:
            fail("timeout")

    def guarded_check():
        try:
            check()
        except Exception as exc:
            import traceback

            traceback.print_exc()
            fail(str(exc))

    QTimer.singleShot(1000, guarded_check)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
