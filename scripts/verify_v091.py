"""Verify cursor-following imported artwork using the real Windows widgets."""

import json
import os
from decimal import Decimal as D
from pathlib import Path


def main():
    out = Path(__file__).resolve().parents[1] / "output/v091/native"
    out.mkdir(parents=True, exist_ok=True)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["EDITOR_GERBER_SETTINGS"] = str(out / "preferences.json")

    from PySide6.QtCore import QPointF, Qt, QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFileDialog

    from gerber_editor.app.main_window import MainWindow
    from gerber_editor.app.metadata import VERSION
    from gerber_editor.app.settings import apply_theme
    from gerber_editor.core.layer import GerberLayer
    from gerber_editor.gerber.writer import SaveMode
    from gerber_editor.ui.branding import apply_branding
    from gerber_editor.ui.raster_dialog import RasterDialog

    app = QApplication([])
    apply_branding(app)
    apply_theme(app)
    editor = MainWindow()
    layer = GerberLayer("imported_artwork", function="F.Silk")
    editor.add_layer(layer)
    editor.showMaximized()
    QTest.qWait(100)
    canvas = editor.canvas
    canvas.snap_grid = canvas.snap_points = False
    canvas.centerOn(20, 15)
    source = QImage(12, 8, QImage.Format.Format_RGB32)
    source.fill(Qt.GlobalColor.white)
    for y in range(8):
        for x in range(12):
            if x < 2 or y < 2 or (3 <= y < 5 and x < 8):
                source.setPixelColor(x, y, Qt.GlobalColor.black)
    image_path = out / "test_artwork.png"
    assert source.save(str(image_path))
    QFileDialog.getOpenFileName = staticmethod(lambda *args: (str(image_path), ""))
    execute = RasterDialog.exec

    def accept(dialog):
        dialog.width.set_mm(D(12))
        assert dialog.mouse_placement.isChecked()
        assert not dialog.x.isEnabled() and not dialog.y.isEnabled()
        QTimer.singleShot(30, lambda: dialog.grab().save(str(out / "01_import_dialog.png")))
        QTimer.singleShot(120, dialog.accept)
        return execute(dialog)

    RasterDialog.exec = accept
    history = editor.history._index
    editor.import_graphic()
    assert not layer.objects and canvas.mode == "placement"
    previews = []
    for index, point in enumerate(((14, 20), (28, 10)), 2):
        position = canvas.mapFromScene(QPointF(*point))
        QTest.mouseMove(editor.windowHandle(), canvas.viewport().mapTo(editor, position))
        QTest.qWait(70)
        assert not layer.objects and editor.history._index == history
        actual = canvas.snap(canvas._cursor)
        assert abs(float(actual.x) - point[0]) < 0.1 and abs(float(actual.y) - point[1]) < 0.1
        previews.append(canvas.viewport().grab().toImage())
        editor.grab().save(str(out / f"0{index}_following_mouse.png"))
    assert previews[0] != previews[1]
    position = canvas.mapFromScene(QPointF(28, 10))
    target = canvas.snap(canvas.mapToScene(position))
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=position)
    QTest.qWait(70)
    assert canvas.mode == "select" and editor._pending_edit is None
    assert editor.history._index == history + 1 and layer.objects
    center = (
        (
            min(obj.bounds.left for obj in layer.objects)
            + max(obj.bounds.right for obj in layer.objects)
        )
        / 2,
        (
            min(obj.bounds.bottom for obj in layer.objects)
            + max(obj.bounds.top for obj in layer.objects)
        )
        / 2,
    )
    assert abs(center[0] - float(target.x)) < 1e-6 and abs(center[1] - float(target.y)) < 1e-6
    editor.grab().save(str(out / "04_placed_at_click.png"))
    saved = layer.signature()
    (out / "imported_at_click.gbr").write_bytes(editor.writer.serialize(layer, SaveMode.NORMALIZED))
    editor.history.undo()
    assert not layer.objects
    editor.history.redo()
    assert layer.signature() == saved
    history = editor.history._index
    editor.import_graphic()
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert layer.signature() == saved and editor.history._index == history
    assert editor._pending_edit is None and not editor.busy.active
    report = {
        "version": VERSION,
        "platform": app.platformName(),
        "mouse_placement_default": True,
        "preview_follows_mouse": True,
        "no_objects_or_history_before_click": True,
        "image_center_matches_click": True,
        "single_import_undo_redo": True,
        "escape_cancels_without_changes": True,
        "normalized_gerber_saved": True,
        "placed_center_mm": center,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    layer.saved_signature = layer.signature()
    editor.close()
    app.quit()


if __name__ == "__main__":
    main()
