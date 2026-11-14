"""Check the bundled runtime, assets, 2D and STEP without a Python installation."""

import json
import sys
import traceback
from pathlib import Path


def main(args=None):
    args = sys.argv[1:] if args is None else args
    if len(args) != 1:
        return 2
    out = Path(args[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"frozen": bool(getattr(sys, "frozen", False)), "success": False}
    window = None
    try:
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QApplication

        from gerber_editor.app.main_window import MainWindow
        from gerber_editor.app.metadata import VERSION
        from gerber_editor.app.settings import apply_theme
        from gerber_editor.core.layer import GerberLayer
        from gerber_editor.core.primitives import Point
        from gerber_editor.gerber.parser import GerberParser
        from gerber_editor.gerber.writer import SaveMode
        from gerber_editor.tools.shapes import create_shape
        from gerber_editor.ui.help_dialog import help_html
        from gerber_editor.ui.support_dialog import SupportDialog
        from gerber_editor.viewer3d.exporters import export_step, export_wrl, step_available
        from gerber_editor.viewer3d.mesh import build_board

        app = QApplication.instance() or QApplication([])
        app.setApplicationName("Editor Gerber")
        apply_theme(app)
        window = MainWindow(settings_path=out / "preferences.json")
        window.show_error = lambda title, error: (_ for _ in ()).throw(
            RuntimeError(f"{title}: {error}")
        )
        window.load_demo()
        window.show()
        app.processEvents()
        token = window.busy.begin("Carregando…")
        for width, height in ((900, 650), (1440, 900)):
            window.resize(width, height)
            app.processEvents()
            center = window.canvas.mapTo(window, window.canvas.rect().center())
            assert (window.busy.overlay.geometry().center() - center).manhattanLength() <= 2
        window.busy.end(token)
        data = window.writer.serialize(window.active_layer, SaveMode.NORMALIZED)
        reopened = GerberParser().parse(data)
        assert len(reopened.objects) == len(window.active_layer.objects)
        assert "Editor Gerber" in help_html(window)
        window.set_language("en")
        assert "Getting started" in help_html(window)
        import gerber_editor

        assets = Path(gerber_editor.__file__).parent / "assets"
        assert not QImage(str(assets / "splash.png")).isNull()
        assert not window.windowIcon().isNull()
        support = SupportDialog(window)
        assert not support.image.isNull()
        support.close()
        window.grab().save(str(out / "window.png"))
        edge = GerberLayer("Edge_Cuts.gbr", function="Edge.Cuts")
        from decimal import Decimal

        edge.objects = create_shape(
            edge, "rectangle", [Point.of(0, 0), Point.of(10, 8)], Decimal("0.1")
        )
        drill = GerberParser().parse(
            "M48\nMETRIC\nT1C1.0\n%\nG90\nG05\nT1\nX5.0Y4.0\nM30\n", "test-PTH.drl"
        )
        mesh = build_board([edge, drill])
        assert len(mesh.outline.interiors) == 1
        assert step_available(), "STEP backend was not bundled"
        export_wrl(mesh, out / "pcb.wrl")
        export_step(mesh, out / "pcb.step")
        assert (out / "pcb.step").stat().st_size > 1000
        report.update(
            version=VERSION,
            success=True,
            gerber_roundtrip=True,
            assets=True,
            help_languages=["pt_BR", "en"],
            qr=True,
            drill_3d=True,
            step=True,
            objects=len(reopened.objects),
            triangles=mesh.triangles,
        )
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if window is not None:
            for layer in window.layers:
                layer.saved_signature = layer.signature()
            window.close()
        (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
