from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtTest import QTest

from gerber_editor.app.main_window import MainWindow
from gerber_editor.commands.edit_commands import LayerProperty
from gerber_editor.core.primitives import Point
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter
from gerber_editor.validation.checks import compare_layers


def test_logo_window_delete_undo_export_reopen(qapp, tmp_path):
    window = MainWindow()
    window.load_demo()
    window.show()
    qapp.processEvents()
    canvas = window.canvas
    canvas.fit_all()
    qapp.processEvents()
    layer = window.active_layer
    original = list(layer.objects)
    # Actual viewport input, left-to-right window around the manufacturer logo.
    start = canvas.mapFromScene(QPointF(50, 19))
    end = canvas.mapFromScene(QPointF(78, 5))
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(canvas.viewport(), end, delay=20)
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=end)
    selected = {item.obj.id for item in canvas.selected_objects()}
    assert len(selected) > 20
    assert all(obj.bounds.left >= 50 for obj in original if obj.id in selected)
    canvas.setFocus()
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Delete)
    qapp.processEvents()
    assert len(layer.objects) == len(original) - len(selected)
    expected = list(layer.objects)
    window.history.undo()
    assert layer.objects == original
    window.history.redo()
    assert layer.objects == expected
    destination = tmp_path / "silkscreen_edited.gbr"
    GerberWriter().save(layer, destination)
    reopened = GerberParser().parse_file(destination)
    compare_layers(layer, reopened, "preservation")
    assert [obj for obj in original if obj.id not in selected] == layer.objects
    assert len(reopened.objects) == len(expected)
    layer.saved_signature = layer.signature()
    window.close()


def test_active_layer_visibility_crossing_and_properties(qapp):
    window = MainWindow()
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "basic.gbr"
    first = window.open_path(fixture)
    second = window.open_path(fixture)
    canvas = window.canvas
    canvas.select_all()
    assert len(canvas.selected_objects()) == len(second.objects)
    assert all(item.layer is second for item in canvas.selected_objects())
    window.history.push(LayerProperty(second, "visible", False))
    canvas.select_all()
    assert not canvas.selected_objects()
    window.history.undo()
    # A thin window intersects a line, but cannot contain it.
    rect = QRectF(4, 0.9, 1, 0.2)
    canvas.select_window(rect, crossing=False)
    assert not canvas.selected_objects()
    canvas.select_window(rect, crossing=True)
    assert canvas.selected_objects()
    assert window.properties.table.rowCount() > 0
    assert first.visible and second.visible
    window.close()


def test_line_tool_two_clicks_and_text_command(qapp):
    window = MainWindow()
    window.load_demo()
    window.show()
    qapp.processEvents()
    canvas = window.canvas
    canvas.fit_all()
    layer = window.active_layer
    count = len(layer.objects)
    canvas.grid_mm = Decimal("1")
    window.set_tool("line")
    for point in [QPointF(10, 25), QPointF(20, 25)]:
        QTest.mouseClick(
            canvas.viewport(), Qt.MouseButton.LeftButton, pos=canvas.mapFromScene(point)
        )
    assert len(layer.objects) == count + 1
    assert layer.objects[-1].geometry.start == Point.of(10, 25)
    assert layer.objects[-1].geometry.end == Point.of(20, 25)
    window.history.undo()
    assert len(layer.objects) == count
    window.close()
