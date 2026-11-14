"""Native image grouping, group shortcuts, independent copies and HTML help."""

import json
import os
from decimal import Decimal as D
from pathlib import Path
from time import monotonic


def main():
    out = Path(__file__).resolve().parents[1] / "output/v010/native"
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
    layer = GerberLayer("grouped_artwork", function="F.Silk")
    editor.add_layer(layer)
    editor.showMaximized()
    editor.activateWindow()
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
    path = out / "artwork.png"
    assert source.save(str(path))
    QFileDialog.getOpenFileName = staticmethod(lambda *args: (str(path), ""))
    execute = RasterDialog.exec

    def accept(dialog):
        dialog.width.set_mm(D(12))
        QTimer.singleShot(60, dialog.accept)
        return execute(dialog)

    RasterDialog.exec = accept

    def click(x, y):
        point = canvas.mapFromScene(QPointF(x, y))
        QTest.mouseMove(editor.windowHandle(), canvas.viewport().mapTo(editor, point))
        QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.qWait(40)

    def key(keycode, modifiers=Qt.KeyboardModifier.ControlModifier):
        editor.activateWindow()
        canvas.setFocus()
        QTest.qWait(20)
        QTest.keyClick(editor.windowHandle(), keycode, modifiers)
        QTest.qWait(50)

    editor.import_graphic()
    assert not layer.objects and canvas.mode == "placement"
    click(28, 10)
    group = layer.objects[0].group_id
    assert group and len(layer.objects) > 1 and all(obj.group_id == group for obj in layer.objects)
    canvas.clear_selection()
    click(23, 7)
    assert len(canvas.selected_objects()) == len(layer.objects)
    editor.grab().save(str(out / "01_select_whole_image.png"))
    layer.saved_signature = layer.signature()
    data = editor.writer.serialize(layer, SaveMode.NORMALIZED)
    key(Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert all(obj.group_id is None for obj in layer.objects) and not layer.modified
    canvas.clear_selection()
    click(23, 7)
    assert len(canvas.selected_objects()) == 1
    editor.grab().save(str(out / "02_select_ungrouped_part.png"))
    canvas.select_all()
    key(Qt.Key.Key_G)
    regrouped = layer.objects[0].group_id
    assert regrouped and all(obj.group_id == regrouped for obj in layer.objects)
    assert editor.writer.serialize(layer, SaveMode.NORMALIZED) == data and not layer.modified
    key(Qt.Key.Key_Z)
    assert all(obj.group_id is None for obj in layer.objects)
    key(Qt.Key.Key_Y)
    assert all(obj.group_id == regrouped for obj in layer.objects)
    key(Qt.Key.Key_C)
    key(Qt.Key.Key_V)
    assert canvas.mode == "placement"
    copy_group = editor._pending_edit["objects"][0].group_id
    assert copy_group != regrouped
    click(45, 15)
    assert len({obj.group_id for obj in layer.objects}) == 2
    canvas.clear_selection()
    click(23, 7)
    assert all(item.obj.group_id == regrouped for item in canvas.selected_objects())

    editor.chrome.actions["help.usage"].trigger()
    help_dialog = editor._help_dialog
    QTest.qWait(80)
    assert help_dialog.isVisible() and not help_dialog.isModal()
    help_dialog.grab().save(str(out / "03_html_help_index.png"))
    help_dialog.open_section("groups")
    QTest.qWait(80)
    help_dialog.grab().save(str(out / "04_html_help_groups.png"))
    help_dialog.search.setText("agrupada automaticamente")
    help_dialog.find_text()
    assert help_dialog.browser.textCursor().selectedText() == "agrupada automaticamente"
    editor.set_language("en")
    assert "Grouping and ungrouping" in help_dialog.browser.toPlainText()
    help_dialog.grab().save(str(out / "05_html_help_english.png"))
    help_dialog.close()
    editor.set_language("pt_BR")
    editor.show_3d()
    viewer = editor._viewer3d
    deadline = monotonic() + 20
    while viewer._dirty and monotonic() < deadline:
        QTest.qWait(20)
    assert not viewer._dirty and not viewer.last_error
    viewer.show_help()
    assert editor._help_dialog is help_dialog and help_dialog.section == "viewer3d"
    QTest.qWait(80)
    help_dialog.grab().save(str(out / "06_html_help_3d.png"))
    report = {
        "version": VERSION,
        "platform": app.platformName(),
        "image_follows_cursor_and_enters_grouped": True,
        "click_selects_whole_image": True,
        "group_ungroup_shortcuts_work": True,
        "undo_redo_restore_groups": True,
        "copies_are_independent_groups": True,
        "grouping_does_not_modify_gerber_bytes": True,
        "help_modeless_html_search_and_languages": True,
        "3d_help_opens_shared_guide_at_3d_topic": True,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    layer.saved_signature = layer.signature()
    editor.close()
    app.clipboard().clear()
    app.quit()


if __name__ == "__main__":
    main()
