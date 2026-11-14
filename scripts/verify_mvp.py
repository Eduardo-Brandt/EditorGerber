r"""Reproduce the silkscreen workflow and render the app itself for visual QA.

Run: .venv\Scripts\python.exe -m scripts.verify_mvp
Artifacts are synthetic files under output/verification/; user files are not read.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, QStandardPaths  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerber_editor.app.main_window import MainWindow  # noqa: E402
from gerber_editor.app.settings import apply_theme  # noqa: E402
from gerber_editor.gerber.parser import GerberParser  # noqa: E402
from gerber_editor.gerber.writer import GerberWriter, SaveMode  # noqa: E402
from gerber_editor.validation.checks import compare_layers  # noqa: E402


def main():
    destination = Path(__file__).resolve().parents[1] / "output" / "verification"
    destination.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    # Qt's Windows offscreen plugin does not enumerate system fonts. Load a local
    # installed font for QA only; font binaries are never copied/distributed.
    if not QFontDatabase.families():
        roots = [
            Path(p)
            for p in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.FontsLocation)
        ]
        if os.environ.get("SystemRoot"):
            roots.append(Path(os.environ["SystemRoot"]) / "Fonts")
        for root in roots:
            font = root / "segoeui.ttf"
            if font.exists() and QFontDatabase.addApplicationFont(str(font)) >= 0:
                break
    apply_theme(app)
    window = MainWindow()
    window.resize(1440, 900)
    window.load_demo()
    window.show()
    app.processEvents()
    window.canvas.fit_all()
    layer = window.active_layer
    original_bytes = layer.source.data
    (destination / layer.name).write_bytes(original_bytes)
    original_count = len(layer.objects)

    def capture(name):
        app.processEvents()
        QTest.qWait(100)
        if not window.grab().save(str(destination / name)):
            raise RuntimeError("Falha ao renderizar PNG da janela Qt.")

    capture("01_original.png")
    window.canvas.select_window(QRectF(50, 5, 28, 14), crossing=False)
    selected_count = len(window.canvas.selected_objects())
    if selected_count < 20:
        raise AssertionError("Janela de seleção não encontrou o logo.")
    capture("02_selected.png")
    window.delete_selection()
    capture("03_deleted.png")
    for mode in SaveMode:
        path = destination / f"silkscreen_{mode.value}_edited.gbr"
        GerberWriter().save(layer, path, mode, overwrite=True)
        reopened = GerberParser().parse_file(path)
        compare_layers(layer, reopened, mode.value)
    window.history.undo()
    assert len(layer.objects) == original_count
    window.history.redo()
    assert len(layer.objects) == original_count - selected_count
    assert (destination / layer.name).read_bytes() == original_bytes
    layer.saved_signature = layer.signature()
    window.close()
    reopened_window = MainWindow()
    reopened_window.open_path(destination / "silkscreen_preservation_edited.gbr")
    reopened_window.resize(1440, 900)
    reopened_window.show()
    app.processEvents()
    reopened_window.canvas.fit_all()
    QTest.qWait(100)
    reopened_window.grab().save(str(destination / "04_reopened.png"))
    reopened_window.close()
    report = {
        "original_objects": original_count,
        "deleted_logo_objects": selected_count,
        "remaining_objects": original_count - selected_count,
        "undo_redo": "passed",
        "original_bytes_unchanged": True,
        "preservation_roundtrip": "exact logical geometry and attributes",
        "normalized_roundtrip": "exact logical geometry and attributes",
        "visual_capture": "Qt offscreen render of the application",
    }
    (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
