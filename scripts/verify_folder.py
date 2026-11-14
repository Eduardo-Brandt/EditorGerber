r"""Audit and edit real Gerbers without modifying the input directory.

Example: python -m scripts.verify_folder "C:\Temp\Gerbers\PCB Teste" --capture
Outputs are confined to output/real_verification under this workspace.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QRectF, QStandardPaths  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerber_editor.app.importer import looks_like_gerber  # noqa: E402
from gerber_editor.app.main_window import MainWindow  # noqa: E402
from gerber_editor.app.settings import apply_theme  # noqa: E402
from gerber_editor.gerber.parser import GerberParser  # noqa: E402
from gerber_editor.gerber.writer import GerberWriter, SaveMode  # noqa: E402
from gerber_editor.graphics.renderer import LayerRenderer  # noqa: E402
from gerber_editor.validation.checks import compare_layers  # noqa: E402


def verify(path: Path, output: Path, app, capture: bool) -> dict:
    started = perf_counter()
    original_bytes = path.read_bytes()
    layer = GerberParser().parse(original_bytes, path.name, path)
    assert GerberWriter().serialize(layer) == original_bytes
    renderer = LayerRenderer()
    renderer.paths(layer)
    opened_seconds = perf_counter() - started
    window = MainWindow()
    window.canvas.renderer.adopt(renderer)
    window.add_layer(layer)
    window.resize(1440, 900)
    window.show()
    app.processEvents()
    window.canvas.fit_all()
    app.processEvents()
    if capture:
        window.grab().save(str(output / f"{path.name}_original.png"))
    original_objects = list(layer.objects)
    candidate = next(
        (
            obj
            for obj in layer.objects
            if 0.05 < obj.bounds.right - obj.bounds.left < 3
            and 0.05 < obj.bounds.top - obj.bounds.bottom < 3
        ),
        layer.objects[0],
    )
    b = candidate.bounds
    window.canvas.select_window(
        QRectF(
            b.left - 0.001, b.bottom - 0.001, b.right - b.left + 0.002, b.top - b.bottom + 0.002
        ),
        False,
    )
    selected = {item.obj.id for item in window.canvas.selected_objects()}
    assert candidate.id in selected
    if capture and path.name == "srlc":
        window.canvas.fit_selection()
        app.processEvents()
        window.grab().save(str(output / "srlc_selection_detail.png"))
    window.delete_selection()
    assert layer.objects == [obj for obj in original_objects if obj.id not in selected]
    for mode in SaveMode:
        target = output / f"{path.name}_{mode.value}_edited.gbr"
        GerberWriter().save(layer, target, mode, overwrite=True)
        compare_layers(layer, GerberParser().parse_file(target), mode.value)
    window.history.undo()
    assert layer.objects == original_objects
    window.history.redo()
    assert len(layer.objects) == len(original_objects) - len(selected)
    if capture:
        window.canvas.fit_all()
        app.processEvents()
        window.grab().save(str(output / f"{path.name}_edited.png"))
    assert path.read_bytes() == original_bytes
    result = {
        "file": path.name,
        "objects": len(original_objects),
        "macro_apertures": sum(bool(ap.macro) for ap in layer.apertures.values()),
        "selected_and_deleted": len(selected),
        "remaining_objects": len(layer.objects),
        "original_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "original_unchanged": True,
        "render": "passed",
        "preservation_and_normalized": "passed",
        "undo_redo": "passed",
        "parse_and_geometry_seconds": round(opened_seconds, 3),
        "total_seconds": round(perf_counter() - started, 3),
    }
    layer.saved_signature = layer.signature()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "output" / "real_verification"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
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
    report = {"files": [], "skipped_non_gerber": [], "failures": []}
    for path in sorted(args.folder.iterdir()):
        if not path.is_file():
            continue
        if not looks_like_gerber(path):
            report["skipped_non_gerber"].append(path.name)
            continue
        try:
            result = verify(path, output, app, args.capture)
            report["files"].append(result)
            print(json.dumps(result), flush=True)
        except Exception as exc:
            report["failures"].append({"file": path.name, "error": str(exc)})
            print(f"FAILED {path.name}: {exc}", flush=True)
        gc.collect()
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SystemExit(1 if report["failures"] else 0)


if __name__ == "__main__":
    main()
