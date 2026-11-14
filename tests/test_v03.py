"""Behavioural coverage for the sixteen requested usability improvements."""

from decimal import Decimal as D
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QKeySequence, QWheelEvent
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
from shapely.geometry import Point as ShapelyPoint

from gerber_editor.app.i18n import Locale
from gerber_editor.app.main_window import MainWindow
from gerber_editor.app.metadata import APP_NAME, CREATED, CREATOR, VERSION, WEBSITE
from gerber_editor.app.preferences import Preferences
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject
from gerber_editor.core.primitives import Point
from gerber_editor.core.units import Unit, vector_text
from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.graphics.canvas import Canvas
from gerber_editor.tools.dimensions import create_dimension
from gerber_editor.tools.raster import binary_image, raster_objects
from gerber_editor.tools.shapes import create_shape, rectangle_region
from gerber_editor.tools.vector_text import vector_text as font_text
from gerber_editor.ui.about_dialog import AboutDialog
from gerber_editor.ui.dimension_dialog import DimensionDialog
from gerber_editor.ui.splash import SplashScreen
from gerber_editor.ui.text_dialog import TextDialog
from gerber_editor.ui.translation_dialog import TranslationDialog

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_save_current_and_save_as_destinations(qapp, tmp_path, monkeypatch):
    source = tmp_path / "original.gbr"
    source.write_bytes((FIXTURES / "basic.gbr").read_bytes())
    original = source.read_bytes()
    window = MainWindow()
    layer = window.open_path(source)
    layer.objects.pop(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    assert not window.save_current()
    assert source.read_bytes() == original
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    assert window.save_current()
    assert len(GerberParser().parse_file(source).objects) == 4
    assert not layer.modified
    destination = tmp_path / "copy.gbr"
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args: (window.t("Preservation · preservar comandos originais"), True),
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(destination), "")
    )
    assert window.save_as()
    assert layer.path == destination.resolve()
    saved_source = source.read_bytes()
    layer.objects.pop(0)
    assert window.save_current()
    assert len(GerberParser().parse_file(destination).objects) == 3
    assert source.read_bytes() == saved_source
    assert window.save_action.shortcut().toString() == "Ctrl+S"
    assert window.save_as_action.shortcut().toString() == "Ctrl+Shift+S"
    window.close()


def test_wheel_zoom_keeps_the_world_point_under_cursor(qapp):
    canvas = Canvas()
    canvas.resize(900, 650)
    canvas.show()
    canvas.centerOn(23, -17)
    qapp.processEvents()
    anchor = QPoint(143, 211)
    before = canvas.mapToScene(anchor)
    event = QWheelEvent(
        QPointF(anchor),
        QPointF(canvas.viewport().mapToGlobal(anchor)),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(canvas.viewport(), event)
    after = canvas.mapToScene(anchor)
    assert (after - before).manhattanLength() < 1 / abs(canvas.transform().m11())
    assert abs(canvas.transform().m11()) == pytest.approx(14.4)
    canvas.close()


def test_measurement_overlay_inverts_crossed_red_pixels(qapp):
    layer = GerberLayer("red.gbr", color="#ff0000")
    layer.objects = [GerberObject(rectangle_region(Point.of(-20, -20), Point.of(20, 20)), None)]
    canvas = Canvas()
    canvas.resize(600, 420)
    canvas.rebuild([layer])
    canvas.show()
    canvas.fit_all()
    canvas.axes_visible = False
    canvas.set_mode("measure")
    canvas._measurement = (Point.of(-10, 2), Point.of(10, 2))
    canvas._cursor = QPointF(10, 2)
    canvas.units = Unit.INCH
    qapp.processEvents()
    bitmap = canvas.viewport().grab().toImage()
    samples = []
    for x in range(-5, 6):
        pixel = canvas.mapFromScene(QPointF(x, 2))
        for offset in range(-2, 3):
            samples.append(bitmap.pixelColor(pixel.x() + offset, pixel.y()))
    assert any(color.red() < 10 and color.green() > 240 and color.blue() > 240 for color in samples)
    assert "1.0000 in" in vector_text(25.4, 0, Unit.INCH)
    assert "1000.0000 mil" in vector_text(25.4, 0, Unit.MIL)
    canvas.close()


def test_live_measurement_and_pending_indicator(qapp):
    from PySide6.QtTest import QTest

    window = MainWindow()
    window.load_demo()
    window.show()
    qapp.processEvents()
    window.canvas.snap_grid = False
    window.set_units("in")
    window.set_tool("measure")
    first = window.canvas.mapFromScene(QPointF(10, 20))
    end = window.canvas.mapFromScene(QPointF(35.4, 20))
    spy = QSignalSpy(window.canvas.measurementChanged)
    QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=first)
    assert window.busy.active
    QTest.mouseMove(window.canvas.viewport(), end)
    qapp.processEvents()
    assert spy.count() > 0
    assert "in" in window.statusBar().currentMessage()
    QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert not window.busy.active
    window.close()


@pytest.mark.parametrize(
    "kind,points,count",
    [
        ("rectangle", [Point.of(1, 1), Point.of(5, 3)], 4),
        ("square", [Point.of(1, 1), Point.of(5, 3)], 4),
        ("circle", [Point.of(10, 10), Point.of(12, 10)], 1),
        ("arc", [Point.of(10, 10), Point.of(12, 10), Point.of(10, 12)], 1),
    ],
)
def test_new_shapes_export_in_legacy_precision(kind, points, count):
    layer = GerberParser().parse_file(FIXTURES / "legacy_cam.gbr")
    objects = create_shape(layer, kind, points, D("0.2"))
    assert len(objects) == count
    layer.objects += objects
    for mode in SaveMode:
        GerberWriter().serialize(layer, mode)


def test_system_font_produces_exportable_regions_with_holes(qapp):
    layer = GerberLayer("text.gbr")
    objects = font_text(layer, "O", Point.of(0, 0), D(3), D("0.2"), "Segoe UI")
    assert objects[0].kind == "Flash" and objects[0].aperture.macro
    shape = object_geometry(objects[0])
    bounds = objects[0].bounds
    assert shape.area > 0
    assert not shape.contains(
        ShapelyPoint((bounds.left + bounds.right) / 2, (bounds.bottom + bounds.top) / 2)
    )
    background = GerberObject(rectangle_region(Point.of(-1, -1), Point.of(5, 5)), None)
    objects_on_background = [background, *objects]
    combined = compose_layer(
        objects_on_background, {obj.id: object_geometry(obj) for obj in objects_on_background}
    )
    assert combined.area == pytest.approx(36)
    layer.objects = objects
    GerberWriter().serialize(layer)


def test_raster_color_threshold_and_merged_regions(qapp):
    image = QImage(4, 2, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    for x in (0, 1):
        for y in (0, 1):
            image.setPixelColor(x, y, QColor("red"))
    image.setPixelColor(3, 0, QColor(0, 0, 0, 0))
    mask, _ = binary_image(image, 4, 128)
    assert mask.sum() == 4
    assert not mask[0, 3]  # Transparent pixels are composited over white.
    layer = GerberLayer("graphic.gbr")
    layer.objects = raster_objects(layer, mask, Point.of(0, 0), D(4))
    assert len(layer.objects) == 1
    assert object_geometry(layer.objects[0]).area == 4
    GerberWriter().serialize(layer)
    inverse, _ = binary_image(image, 4, 128, True)
    assert np.array_equal(inverse, ~mask)


def test_dimensions_custom_font_arrow_and_independent_units(qapp):
    layer = GerberLayer("dimension.gbr")
    layer.objects = create_dimension(
        layer,
        Point.of(0, 0),
        Point(D("25.4"), D(0)),
        Point.of(0, 4),
        arrow_mm=D("0.8"),
        text_mm=D("1.5"),
        width_mm=D("0.15"),
        family="Segoe UI",
        unit="in",
        polar=True,
    )
    assert len(layer.objects) >= 6
    assert any(obj.kind == "Region" for obj in layer.objects)
    GerberWriter().serialize(layer)
    window = MainWindow()
    dialog = DimensionDialog(window)
    before = dialog.values()
    dialog.unit.setCurrentText("in")
    assert dialog.values()["unit"] == "in"
    assert dialog.values()["arrow_mm"] == before["arrow_mm"]
    assert dialog.values()["text_mm"] == before["text_mm"]
    dialog.reject()
    window.close()


def test_layers_front_order_double_click_menu_and_close_undo(qapp):
    window = MainWindow()
    first = window.open_path(FIXTURES / "basic.gbr")
    second = window.open_path(FIXTURES / "legacy_cam.gbr")
    assert window.layer_panel.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) == second.id
    assert (
        window.canvas.display_items[second.id].zValue()
        > window.canvas.display_items[first.id].zValue()
    )
    actions = window.layer_panel.options_menu(second).actions()
    assert [action.text() for action in actions] == ["Cor…", "Opacidade…", "Função…"]
    assert window.close_layer(second.id)
    assert window.layers == [first]
    window.history.undo()
    assert window.layers == [first, second]
    assert window.close_all()
    assert not window.layers
    window.history.undo()
    assert window.layers == [first, second]
    window.close()


def test_grid_language_shortcuts_and_units_persist(qapp, tmp_path):
    path = tmp_path / "custom_preferences.json"
    preferences = Preferences(path)
    preferences.set(shortcuts={"tool.measure": "F8"}, grids_mm=["0.127", "0.635"], grid_mm="0.127")
    window = MainWindow(settings_path=path)
    window.load_demo()
    objects = list(window.active_layer.objects)
    assert window.measure_action.shortcut().toString() == "F8"
    window.set_units("mil")
    window.set_language("en")
    assert window.save_action.text() == "Save"
    assert window.measure_action.shortcut().toString() == "F8"
    assert window.active_layer.objects == objects
    assert window.drawing_width_mm == D("0.2")
    window.grid_combo.setEditText("50 mil")
    window.custom_grid()
    assert window.canvas.grid_mm == D("1.27")
    assert Preferences(path).data["grid_mm"] == "1.2700"
    assert "tool.measure" in Preferences(path).data["shortcuts"]
    second = MainWindow(settings_path=path)
    assert second.locale.language == "en"
    assert second.display_unit == Unit.MIL
    assert second.measure_action.shortcut() == QKeySequence("F8")
    window.close()
    second.close()


def test_dialogs_show_selected_units_without_changing_mm(qapp):
    window = MainWindow()
    window.set_units("in")
    dialog = TextDialog(Point.of(25, 12), window)
    assert dialog.x.suffix() == " in"
    assert dialog.values()["position"] == Point.of(25, 12)
    move = TranslationDialog(False, window)
    move.dx.setValue(1)
    assert move.values()[0] == D("25.4")
    window.close()


def test_cursor_ghost_and_polar_are_presentation_only(qapp):
    window = MainWindow()
    layer = window.open_path(FIXTURES / "basic.gbr")
    original = GerberWriter().serialize(layer)
    window.full_cursor_action.trigger()
    window.ghost_action.trigger()
    window.polar_action.trigger()
    assert window.canvas.full_cursor
    assert window.canvas.ghost_negatives
    assert window.canvas.polar
    assert window.canvas.ghost_items
    assert all(item.isVisible() for item, _ in window.canvas.ghost_items)
    assert GerberWriter().serialize(layer) == original
    window.chrome.coordinates(3, 4)
    assert "R 5.0000" in window.coordinates.text()
    assert "53.13" in window.coordinates.text()
    window.close()


def test_preferences_follow_corrected_application_name(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QStandardPaths

    legacy = tmp_path / "Editr Gerber" / "preferences.json"
    Preferences(legacy).set(units="mil", shortcuts={"tool.measure": "F8"})
    destination = tmp_path / "Editor Gerber" / "preferences.json"
    monkeypatch.delenv("EDITR_GERBER_SETTINGS")
    monkeypatch.delenv("EDITOR_GERBER_SETTINGS")
    monkeypatch.setattr(
        QStandardPaths, "writableLocation", lambda location: str(destination.parent)
    )
    preferences = Preferences()
    assert preferences.path == destination
    assert preferences.data["units"] == "mil"
    assert preferences.data["shortcuts"] == {"tool.measure": "F8"}
    preferences.set(language="en")
    assert destination.is_file()
    assert Preferences(legacy).data["language"] == "pt_BR"


def test_english_catalog_covers_bound_ui_and_metadata(qapp):
    window = MainWindow(language="en")
    catalog = window.locale.catalog
    missing = {
        source
        for _, _, source in window.locale.bindings
        if source not in catalog and source not in ("mm", "in", "mil")
    }
    assert not missing
    assert window.measure_action.shortcut() == QKeySequence("Shift+A")
    shortcuts = [
        a.shortcut().toString()
        for a in window.chrome.actions.values()
        if not a.shortcut().isEmpty()
    ]
    assert len(shortcuts) == len(set(shortcuts)), "Default shortcuts must be unambiguous"
    about = AboutDialog(window)
    text = " ".join(
        label.text()
        for label in about.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
    )
    assert CREATOR in text and WEBSITE in text and VERSION in text and CREATED in text
    splash = SplashScreen(Locale("en"))
    assert not splash.pixmap().isNull()
    assert APP_NAME == "Editor Gerber"
    splash.show()
    qapp.processEvents()
    assert not splash.grab().isNull()
    splash.close()
    window.close()
