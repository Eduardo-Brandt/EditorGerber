"""Imported graphics preview at the cursor and commit as one reversible edit."""

from decimal import Decimal as D

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog
from shapely.geometry import Point as GeometryPoint

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Polarity
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import SaveMode
from gerber_editor.ui.raster_dialog import RasterDialog


@pytest.fixture
def graphic_import(qapp, tmp_path, monkeypatch):
    window = MainWindow()
    layer = GerberLayer("F.Silk", function="F.Silk")
    window.add_layer(layer)
    window.resize(1100, 720)
    window.show()
    canvas = window.canvas
    canvas.snap_grid = canvas.snap_points = False
    canvas.axes_visible = False
    canvas.centerOn(20, 20)
    qapp.processEvents()
    errors = []
    monkeypatch.setattr(window, "show_error", lambda *values: errors.append(values))
    path = tmp_path / "artwork.png"
    image = QImage(8, 4, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.black)
    assert image.save(str(path))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))

    def configure(*, mouse=True, x=D(0), y=D(0), width=D(12)):
        def accept(dialog):
            assert dialog.mouse_placement.isChecked()
            assert not dialog.x.isEnabled() and not dialog.y.isEnabled()
            dialog.mouse_placement.setChecked(mouse)
            assert dialog.x.isEnabled() == (not mouse)
            dialog.x.set_mm(x)
            dialog.y.set_mm(y)
            dialog.width.set_mm(width)
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(RasterDialog, "exec", accept)

    configure()
    yield window, layer, path, errors, configure
    window.canvas.set_mode("select")
    layer.saved_signature = layer.signature()
    window.close()


def click_point(canvas, x=23, y=17):
    position = canvas.mapFromScene(QPointF(x, y))
    point = canvas.snap(canvas.mapToScene(position))
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=position)
    return point


def test_import_follows_mouse_then_commits_at_image_center_and_undoes(graphic_import, qapp):
    window, layer, path, errors, _ = graphic_import
    canvas = window.canvas
    before, history = path.read_bytes(), window.history._index
    window.import_graphic()
    assert canvas.mode == "placement" and window._pending_edit
    assert not layer.objects and window.history._index == history
    assert canvas._placement_anchor.x == D(6) and canvas._placement_anchor.y == D(3)
    assert window.busy.tool and not window.busy.operations
    assert not window.busy.overlay.isVisible()
    QTest.mouseMove(canvas.viewport(), canvas.mapFromScene(QPointF(15, 15)))
    qapp.processEvents()
    first = canvas.viewport().grab().toImage()
    QTest.mouseMove(canvas.viewport(), canvas.mapFromScene(QPointF(25, 20)))
    qapp.processEvents()
    assert canvas.viewport().grab().toImage() != first
    assert not layer.objects
    point = click_point(canvas)
    assert canvas.mode == "select" and window._pending_edit is None
    assert not canvas.placement_paths and not window.busy.active
    assert len(layer.objects) == 1 and window.history._index == history + 1
    assert window.history._commands[-1].label == "Importar gráfico"
    bounds = layer.objects[0].bounds
    assert (bounds.left + bounds.right) / 2 == pytest.approx(float(point.x), abs=1e-6)
    assert (bounds.bottom + bounds.top) / 2 == pytest.approx(float(point.y), abs=1e-6)
    assert bounds.right - bounds.left == pytest.approx(12)
    assert bounds.top - bounds.bottom == pytest.approx(6)
    placed = layer.signature()
    serialized = window.writer.serialize(layer, SaveMode.NORMALIZED)
    reopened = GerberParser().parse(serialized)
    assert reopened.objects[0].geometry == layer.objects[0].geometry
    window.history.undo()
    assert not layer.objects
    window.history.redo()
    assert layer.signature() == placed
    assert path.read_bytes() == before and not errors


@pytest.mark.parametrize("cancel", ["escape", "right_click"])
def test_cancel_import_discards_preview_without_changing_history(graphic_import, cancel):
    window, layer, _, errors, _ = graphic_import
    history = window.history._index
    window.import_graphic()
    if cancel == "escape":
        QTest.keyClick(window.canvas, Qt.Key.Key_Escape)
    else:
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.RightButton)
    assert not layer.objects and window.history._index == history
    assert window._pending_edit is None and window.canvas.mode == "select"
    assert not window.canvas.placement_paths and not window.busy.active and not errors


def test_manual_coordinates_remain_available_when_mouse_placement_is_disabled(graphic_import):
    window, layer, _, errors, configure = graphic_import
    configure(mouse=False, x=D(31), y=D(17))
    window.import_graphic()
    assert window.canvas.mode == "select" and window._pending_edit is None
    assert len(layer.objects) == 1
    assert layer.objects[0].bounds.left == 31 and layer.objects[0].bounds.bottom == 17
    assert not errors


def test_mouse_import_preserves_orientation_margins_and_clear_polarity(graphic_import):
    window, layer, path, errors, configure = graphic_import
    image = QImage(4, 2, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    image.setPixelColor(0, 0, Qt.GlobalColor.black)
    assert image.save(str(path))
    configure(width=D(4))
    window.polarity_input.setCurrentIndex(1)
    window.import_graphic()
    point = click_point(window.canvas)
    assert len(layer.objects) == 1 and layer.objects[0].polarity == Polarity.CLEAR
    shape = object_geometry(layer.objects[0])
    assert shape.covers(GeometryPoint(float(point.x) - 1.5, float(point.y) + 0.5))
    assert not shape.covers(GeometryPoint(float(point.x) - 1.5, float(point.y) - 0.5))
    assert not errors


def test_blank_image_does_not_start_a_preview_or_create_an_edit(graphic_import):
    window, layer, path, errors, _ = graphic_import
    image = QImage(8, 4, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    assert image.save(str(path))
    history = window.history._index
    window.import_graphic()
    assert errors and not layer.objects
    assert window.canvas.mode == "select" and window._pending_edit is None
    assert window.history._index == history and not window.busy.active
