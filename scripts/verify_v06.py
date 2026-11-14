"""Native Windows smoke check; exports and preferences remain inside output/v06."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from time import monotonic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--exercise-edits", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve() if args.output else root / "output" / "v06" / "native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")
    os.environ["EDITOR_GERBER_LOG_DIR"] = str(out / "logs")

    from PySide6.QtCore import QEventLoop, QPointF, Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.commands.edit_commands import ReplaceObjects
    from gerber_editor.core.primitives import Line
    from gerber_editor.geometry.rigid import RigidTransform
    from gerber_editor.gerber.parser import GerberParser
    from gerber_editor.gerber.writer import GerberWriter
    from gerber_editor.tools.shapes import layer_quantum
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.validation.checks import compare_layers

    source = (args.file or root / "fixtures" / "basic.gbr").resolve()
    data = source.read_bytes()
    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    errors = []
    editor.show_error = lambda *values: errors.append(str(values))
    QMessageBox.warning = lambda *values: errors.append(str(values))
    editor.resize(1366, 768)
    editor.show()
    app.processEvents()
    heartbeat = []
    timer = QTimer()
    timer.setInterval(25)
    timer.timeout.connect(lambda: heartbeat.append(1))
    timer.start()
    editor.open_paths_async([source])
    loop = QEventLoop()
    poll = QTimer()
    deadline = monotonic() + 180

    def ready():
        if not editor._import_jobs or monotonic() >= deadline:
            loop.quit()

    poll.timeout.connect(ready)
    poll.start(25)
    loop.exec()
    poll.stop()
    timer.stop()
    assert not editor._import_jobs, "Import timeout"
    assert not errors, errors
    assert heartbeat and not editor.busy.input_guard.locked
    app.processEvents()
    layer = editor.active_layer
    original = layer.signature()
    canvas = editor.canvas
    items = dict(canvas.object_items)
    editor.grab().save(str(out / "01_initial.png"))

    first = next(obj for obj in layer.objects if isinstance(obj.geometry, Line))
    bounds = first.bounds
    position = canvas.mapFromScene(
        QPointF((bounds.left + bounds.right) / 2, (bounds.bottom + bounds.top) / 2)
    )
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=position)
    assert canvas.selected_objects()
    canvas.clear_selection()
    canvas.select_object(items[first.id])
    selected = {item.obj.id for item in canvas.selected_objects()}
    editor.grab().save(str(out / "02_selection.png"))
    editor._layer_property(layer, "color", "#d590ff")
    assert canvas.object_items == items
    assert {item.obj.id for item in canvas.selected_objects()} == selected
    editor.grab().save(str(out / "03_recolored.png"))
    editor.history.undo()
    editor._layer_property(layer, "opacity", 0.45)
    editor.history.undo()
    editor._layer_property(layer, "visible", False)
    assert not any(item.isVisible() for item in items.values())
    editor.history.undo()
    canvas.select_object(items[first.id])
    edit_report = {}
    if args.exercise_edits:
        from decimal import Decimal

        original_tiles = dict(canvas.renderer._tile_paths.get(layer.id, {}))
        moved = RigidTransform(dx=Decimal(1), dy=Decimal("0.5")).object(first, layer_quantum(layer))
        started = monotonic()
        with editor.busy.operation("Atualizando geometria…"):
            editor.history.push(ReplaceObjects([(layer, {first.id: moved})]))
        app.processEvents()
        editor.grab().save(str(out / "05_object_moved.png"))
        edit_report["move_and_present_s"] = monotonic() - started
        assert canvas.object_items[first.id] is items[first.id]
        assert canvas.object_items[first.id].obj == moved
        changed = canvas.renderer._compositions.get(layer.id)
        if changed:
            edit_report["changed_cells"] = len(changed.changed_keys)
            edit_report["total_cells"] = len(changed.tiles)
            assert any(
                tile is original_tiles.get(key)
                for key, tile in canvas.renderer._tile_paths[layer.id].items()
            )
        editor.history.undo()
        assert layer.signature() == original
        anchor = canvas.viewport().rect().center()
        before = canvas.mapToScene(anchor)
        canvas.zoom_by(1.2, anchor)
        assert (canvas.mapToScene(anchor) - before).manhattanLength() < 1 / abs(
            canvas.transform().m11()
        )
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.MiddleButton, pos=anchor)
        QTest.mouseMove(canvas.viewport(), anchor + type(anchor)(80, 30))
        QTest.mouseRelease(
            canvas.viewport(), Qt.MouseButton.MiddleButton, pos=anchor + type(anchor)(80, 30)
        )
        app.processEvents()
        assert (canvas.mapToScene(anchor) - before).manhattanLength() > 1
        editor.grab().save(str(out / "06_zoom_pan.png"))
        canvas.fit_all()
        edit_report["native_zoom_anchor_and_mouse_pan"] = True
    editor.delete_selection()
    assert len(layer.objects) < len(original)
    destination = out / "verified_edited.gbr"
    GerberWriter().save(layer, destination)
    compare_layers(layer, GerberParser().parse_file(destination), "preservation")
    editor.history.undo()
    assert layer.signature() == original
    assert canvas.object_items[layer.objects[-1].id] is items[layer.objects[-1].id]
    canvas.clear_selection()
    editor.grab().save(str(out / "04_undo.png"))
    assert source.read_bytes() == data
    report = {
        "version": VERSION,
        "platform": app.platformName(),
        "file": str(source),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "objects": len(original),
        "source_unchanged": True,
        "async_heartbeat_ticks": len(heartbeat),
        "selection_color_opacity_visibility_undo_export_reopen": True,
        "unchanged_items_retained": True,
        "errors": errors,
        "geometry_edit": edit_report,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for current in editor.layers:
        current.saved_signature = current.signature()
    editor.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
