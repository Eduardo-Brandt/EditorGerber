r"""Render and export the 0.3 feature showcase; optionally extend a real Gerber.

python -m scripts.verify_v03 --real "C:\Temp\Gerbers\PCB Teste\srlc"
Only synthetic outputs/copies under output/v03 are written.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from decimal import Decimal as D
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerber_editor.app.main_window import MainWindow  # noqa: E402
from gerber_editor.app.settings import apply_theme  # noqa: E402
from gerber_editor.commands.edit_commands import AddObjects  # noqa: E402
from gerber_editor.core.layer import GerberLayer  # noqa: E402
from gerber_editor.core.objects import GerberObject, Polarity  # noqa: E402
from gerber_editor.core.primitives import Flash, Point, Region  # noqa: E402
from gerber_editor.gerber.parser import GerberParser  # noqa: E402
from gerber_editor.gerber.writer import GerberWriter, SaveMode  # noqa: E402
from gerber_editor.tools.dimensions import create_dimension  # noqa: E402
from gerber_editor.tools.drawing import circular_aperture  # noqa: E402
from gerber_editor.tools.raster import raster_objects  # noqa: E402
from gerber_editor.tools.shapes import create_shape, rectangle_region  # noqa: E402
from gerber_editor.tools.vector_text import ensure_offscreen_font, vector_text  # noqa: E402
from gerber_editor.ui.dimension_dialog import DimensionDialog  # noqa: E402
from gerber_editor.ui.preferences_dialogs import ShortcutsDialog  # noqa: E402
from gerber_editor.ui.splash import SplashScreen  # noqa: E402
from gerber_editor.ui.text_dialog import TextDialog  # noqa: E402


def annotations(layer, offset=0):
    stage = copy.copy(layer)
    stage.objects = list(layer.objects)
    added = []

    def p(x, y):
        return Point(D(str(x)) + D(offset), D(str(y)))

    def add(objects):
        stage.objects += objects
        added.extend(objects)

    for kind, points in [
        ("rectangle", [p(5, 5), p(14, 10)]),
        ("square", [p(18, 5), p(23, 8)]),
        ("circle", [p(10, 23), p(13.5, 23)]),
        ("arc", [p(23, 23), p(27, 23), p(23, 27)]),
    ]:
        add(create_shape(stage, kind, points, D("0.2")))
    add(vector_text(stage, "Editor Gerber 0.3", p(5, 33), D("3.5"), D("0.2"), "Segoe UI"))
    add(
        create_dimension(
            stage,
            p(5, 15),
            p(30.4, 15),
            p(5, 11.5),
            arrow_mm=D("0.8"),
            text_mm=D("1.5"),
            width_mm=D("0.15"),
            family="Segoe UI",
            unit="in",
        )
    )
    mask = np.array(
        [
            [1, 1, 1, 1, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 1, 0],
            [1, 1, 1, 1, 0, 1, 0, 0],
            [1, 0, 0, 0, 0, 0, 1, 0],
            [1, 1, 1, 1, 1, 0, 0, 1],
        ],
        dtype=bool,
    )
    add(raster_objects(stage, mask, p(36, 5), D(8)))
    add([GerberObject(rectangle_region(p(36, 21), p(42, 27)), None)])
    add([GerberObject(Flash(p(39, 24)), circular_aperture(stage, D(3)), Polarity.CLEAR)])
    return added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "output" / "v03"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["EDITR_GERBER_SETTINGS"] = str(root / "qa_preferences.json")
    if (root / "qa_preferences.json").exists():
        (root / "qa_preferences.json").write_text("{}", encoding="utf-8")
    app = QApplication([])
    ensure_offscreen_font()
    apply_theme(app)
    window = MainWindow()
    layer = GerberLayer("showcase.gbr", function="F.Silk")
    window.add_layer(layer)
    objects = annotations(layer)
    window.history.push(AddObjects(layer, objects, "QA feature showcase"))
    window.resize(1440, 900)
    window.show()
    app.processEvents()
    window.canvas.fit_all()
    window.ghost_action.trigger()
    window.full_cursor_action.trigger()

    def capture(name, widget=window):
        app.processEvents()
        widget.grab().save(str(root / name))

    capture("01_portugues.png")
    window.set_language("en")
    window.canvas.snap_grid = False
    window.set_units("in")
    window.set_tool("measure")
    window.canvas._line_start = Point.of(5, 15)
    window.canvas._cursor = QPointF(30.4, 15)
    window.busy.pending(True, "Escolha o próximo ponto")
    capture("02_english_live_measure.png")
    window.canvas.set_mode("select")
    for cls, name in [
        (TextDialog, "03_font_dialog.png"),
        (DimensionDialog, "04_dimension_dialog.png"),
        (ShortcutsDialog, "05_shortcuts.png"),
    ]:
        if cls is TextDialog:
            dialog = cls(Point.of(5, 5), window)
            dialog.kind.setCurrentIndex(1)
            dialog.font.setCurrentFont(QFont("Segoe UI"))
        elif cls is ShortcutsDialog:
            dialog = cls(window.chrome.actions, window)
        else:
            dialog = cls(window)
        dialog.show()
        capture(name, dialog)
        dialog.reject()
    splash = SplashScreen(window.locale)
    splash.show()
    capture("06_splashscreen.png", splash)
    splash.close()
    for mode in SaveMode:
        GerberWriter().save(layer, root / f"showcase_{mode.value}.gbr", mode, overwrite=True)
    # Standalone O used by the independent renderer to check transparent counters.
    font = GerberLayer("font_counter.gbr")
    font.objects = vector_text(font, "O", Point.of(0, 0), D(3), D("0.2"), "Segoe UI")
    GerberWriter().save(font, root / "font_counter.gbr", overwrite=True)
    font.objects.insert(0, GerberObject(rectangle_region(Point.of(-1, -1), Point.of(5, 5)), None))
    GerberWriter().save(font, root / "font_on_background.gbr", overwrite=True)
    report = {"showcase_objects": len(layer.objects), "exports": "both modes passed", "real": None}
    layer.saved_signature = layer.signature()
    window.close()
    if args.real:
        source = args.real.read_bytes()
        real = GerberParser().parse_file(args.real)
        original = list(real.objects)
        extra = annotations(real, math.ceil(real.bounds.right) + 10)
        real.objects += extra
        for mode in SaveMode:
            GerberWriter().save(real, root / f"srlc_v03_{mode.value}.gbr", mode, overwrite=True)
        assert real.objects[: len(original)] == original
        assert args.real.read_bytes() == source
        report["real"] = {
            "path": str(args.real),
            "original_objects": len(original),
            "added_objects": len(extra),
            "remaining_original_objects": len(original),
            "original_unchanged": True,
            "sha256": hashlib.sha256(source).hexdigest(),
            "both_exports": "passed",
            "multi_contour_regions": sum(
                isinstance(obj.geometry, Region) and len(obj.geometry.contours) > 1
                for obj in original
            ),
        }
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
