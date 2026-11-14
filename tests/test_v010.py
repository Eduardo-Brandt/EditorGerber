"""Session grouping must be atomic, copy independently and preserve fabrication."""

import json
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtTest import QSignalSpy, QTest

from gerber_editor.app.main_window import MainWindow
from gerber_editor.commands.edit_commands import SetObjectGroups
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject, Polarity
from gerber_editor.core.primitives import Point
from gerber_editor.core.text_entity import TextEntity
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import SaveMode
from gerber_editor.tools.clipboard import decode, encode
from gerber_editor.tools.raster import raster_objects
from gerber_editor.tools.shapes import rectangle_region
from gerber_editor.tools.text_session import text_objects
from gerber_editor.ui.help_dialog import help_html
from gerber_editor.viewer3d.menus import ViewerMenus
from gerber_editor.viewer3d.window import Viewer3DWindow


@pytest.fixture
def drawing(qapp):
    window = MainWindow()
    layer = GerberLayer("F.Silk", function="F.Silk")
    layer.objects = [
        GerberObject(rectangle_region(Point.of(x, 0), Point.of(x + 2, 2)), None) for x in (0, 6, 12)
    ]
    layer.saved_signature = layer.signature()
    window.add_layer(layer)
    window.resize(1100, 720)
    window.show()
    window.activateWindow()
    window.canvas.setFocus()
    window.canvas.snap_grid = window.canvas.snap_points = False
    window.canvas.axes_visible = False
    window.canvas.centerOn(7, 1)
    qapp.processEvents()
    yield window, layer
    if window._viewer3d:
        deadline = monotonic() + 10
        while window._viewer3d._job is not None and monotonic() < deadline:
            QTest.qWait(10)
    window.canvas.set_mode("select")
    for current in window.layers:
        current.saved_signature = current.signature()
    qapp.clipboard().clear()
    window.close()


def select_first_two(window, layer):
    window.canvas.clear_selection()
    window.canvas.select_objects(window.canvas.object_items[obj.id] for obj in layer.objects[:2])


def click(window, x, y, control=False):
    QTest.mouseClick(
        window.canvas.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier if control else Qt.KeyboardModifier.NoModifier,
        window.canvas.mapFromScene(QPointF(x, y)),
    )


def test_group_ungroup_click_ctrl_toggle_and_history_preserve_geometry(drawing):
    window, layer = drawing
    original = list(layer.objects)
    select_first_two(window, layer)
    window.group_action.trigger()
    group_id = layer.objects[0].group_id
    assert group_id and layer.objects[1].group_id == group_id
    assert not layer.objects[2].group_id and not layer.modified
    assert not window.group_action.isEnabled() and window.ungroup_action.isEnabled()
    window.canvas.clear_selection()
    click(window, 1, 1)
    assert len(window.canvas.selected_objects()) == 2
    assert "Grupo" in window.properties.summary.text()
    click(window, 1, 1, control=True)
    assert not window.canvas.selected_objects()
    click(window, 7, 1)
    window.ungroup_action.trigger()
    assert all(obj.group_id is None for obj in layer.objects)
    window.canvas.clear_selection()
    click(window, 1, 1)
    assert len(window.canvas.selected_objects()) == 1
    window.undo_edit()
    window.canvas.clear_selection()
    click(window, 1, 1)
    assert len(window.canvas.selected_objects()) == 2
    window.undo_edit()
    assert all(obj.group_id is None for obj in layer.objects)
    window.redo_edit()
    window.redo_edit()
    assert all(obj.group_id is None for obj in layer.objects)
    assert [obj.geometry for obj in layer.objects] == [obj.geometry for obj in original]
    assert [obj.id for obj in layer.objects] == [obj.id for obj in original]
    assert window.group_action.shortcut().toString() == "Ctrl+G"
    assert window.ungroup_action.shortcut().toString() == "Ctrl+Shift+G"


def test_image_regions_group_automatically_and_move_delete_as_one_unit(drawing):
    window, layer = drawing
    mask = np.array([[1, 1, 1], [1, 0, 0], [1, 1, 0]], dtype=bool)
    layer.objects = raster_objects(layer, mask, Point.of(0, 0), D(3))
    original = list(layer.objects)
    group_id = original[0].group_id
    assert group_id and len({obj.group_id for obj in original}) == 1
    other = raster_objects(layer, mask, Point.of(10, 0), D(3))
    assert other[0].group_id != group_id
    window.refresh()
    window.canvas.select_object(window.canvas.object_items[original[0].id])
    assert len(window.canvas.selected_objects()) == len(original)
    window.start_move(anchor=Point.of(0, 0))
    window._commit_placement(Point.of(3, 2))
    assert all(obj.group_id == group_id for obj in layer.objects)
    for before, after in zip(original, layer.objects, strict=True):
        assert after.bounds.left == before.bounds.left + 3
        assert after.bounds.bottom == before.bounds.bottom + 2
    window.undo_edit()
    window.canvas.select_object(window.canvas.object_items[original[0].id])
    window.delete_selection()
    assert not layer.objects
    window.undo_edit()
    assert all(obj.group_id == group_id for obj in layer.objects)


def test_window_selection_requires_full_group_but_crossing_picks_whole_group(drawing):
    window, layer = drawing
    select_first_two(window, layer)
    window.group_selection()
    window.canvas.select_window(QRectF(-1, -1, 4, 4), crossing=False)
    assert not window.canvas.selected_objects()
    window.canvas.select_window(QRectF(-1, -1, 4, 4), crossing=True)
    assert len(window.canvas.selected_objects()) == 2
    window.canvas.select_window(QRectF(-1, -1, 10, 4), crossing=False)
    assert len(window.canvas.selected_objects()) == 2


def test_copy_and_array_clones_have_independent_groups(drawing):
    window, layer = drawing
    select_first_two(window, layer)
    window.group_selection()
    original_group = layer.objects[0].group_id
    assert window.copy_clipboard()
    window.paste_clipboard()
    pasted_group = window._pending_edit["objects"][0].group_id
    assert pasted_group and pasted_group != original_group
    assert len({obj.group_id for obj in window._pending_edit["objects"]}) == 1
    window._commit_placement(Point.of(25, 10))
    assert len(layer.objects) == 5
    assert {item.obj.group_id for item in window.canvas.selected_objects()} == {pasted_group}
    window.create_array(
        window.selected_in_order(), {"polar": False, "nx": 3, "ny": 1, "dx": D(5), "dy": D(0)}
    )
    copies = layer.objects[5:]
    assert len(copies) == 4
    assert len({obj.group_id for obj in copies}) == 2
    assert not {obj.group_id for obj in copies} & {original_group, pasted_group}
    window.canvas.clear_selection()
    window.canvas.select_object(window.canvas.object_items[copies[0].id])
    assert len(window.canvas.selected_objects()) == 2


def test_grouping_changes_neither_gerber_bytes_nor_2d_3d_caches(drawing, monkeypatch, qapp):
    window, _ = drawing
    parsed = GerberParser().parse_file(Path(__file__).resolve().parents[1] / "fixtures/basic.gbr")
    window.add_layer(parsed)
    layer = parsed
    viewer = Viewer3DWindow(window)
    window._viewer3d = viewer
    monkeypatch.setattr(viewer, "isVisible", lambda: True)
    monkeypatch.setattr(viewer, "isActiveWindow", lambda: True)
    viewer.rebuild()
    deadline = monotonic() + 10
    while viewer._dirty and monotonic() < deadline:
        QTest.qWait(10)
    assert not viewer._dirty
    mesh, revision = viewer.viewport.mesh, viewer._revision
    before = {mode: window.writer.serialize(layer, mode) for mode in SaveMode}
    display = window.canvas.display_items[layer.id]

    def unexpected(*args):
        pytest.fail("Session grouping recomposed the 2D geometry")

    monkeypatch.setattr(window.canvas.renderer, "paths", unexpected)
    select_first_two(window, layer)
    window.group_selection()
    assert not layer.modified
    assert window.canvas.display_items[layer.id] is display
    assert not viewer._dirty and viewer._revision == revision and viewer.viewport.mesh is mesh
    for mode in SaveMode:
        assert window.writer.serialize(layer, mode) == before[mode]
    restored = GerberParser().parse(before[SaveMode.NORMALIZED])
    assert all(obj.group_id is None for obj in restored.objects)
    window.ungroup_selection()
    assert not layer.modified and viewer._revision == revision


def test_group_selection_emits_one_update_even_with_many_members(drawing):
    window, layer = drawing
    layer.objects = [
        GerberObject(
            rectangle_region(Point.of(index, 0), Point.of(index + 1, 1)), None, group_id="artwork"
        )
        for index in range(1000)
    ]
    window.refresh()
    spy = QSignalSpy(window.canvas.selectionUpdated)
    window.canvas.select_object(window.canvas.object_items[layer.objects[0].id])
    assert spy.count() == 1
    assert len(window.canvas.selected_objects()) == 1000


def test_delete_group_includes_hidden_members(drawing):
    window, layer = drawing
    layer.objects[:2] = [
        replace(obj, group_id="artwork", visible=index == 0)
        for index, obj in enumerate(layer.objects[:2])
    ]
    window.refresh()
    survivor = layer.objects[2]
    window.canvas.select_object(window.canvas.object_items[layer.objects[0].id])
    window.delete_selection()
    assert layer.objects == [survivor]
    assert "2" in window.statusBar().currentMessage()


def test_grouping_across_layers_is_not_allowed(drawing):
    window, first = drawing
    second = GerberLayer("other", objects=[replace(first.objects[2], id="other")])
    window.add_layer(second)
    window.canvas.active_only = False
    window.canvas.select_objects(
        [
            window.canvas.object_items[first.objects[0].id],
            window.canvas.object_items[second.objects[0].id],
        ]
    )
    history = window.history._index
    assert not window.group_action.isEnabled()
    window.group_selection()
    assert window.history._index == history and all(
        obj.group_id is None for obj in first.objects + second.objects
    )


@pytest.mark.parametrize("invalid", [[], "x" * 129])
def test_clipboard_rejects_invalid_group_identifiers(drawing, invalid):
    _, layer = drawing
    payload = json.loads(encode(layer.objects, Point.of(0, 0)))
    payload["objects"][0]["group_id"] = invalid
    with pytest.raises(ValueError, match="group"):
        decode(json.dumps(payload).encode())


def test_group_command_undo_restores_previous_memberships(drawing):
    window, layer = drawing
    first, second, third = layer.objects
    window.history.push(SetObjectGroups(layer, {first.id: "first", second.id: "second"}))
    window.history.push(SetObjectGroups(layer, {first.id: "merged", second.id: "merged"}))
    window.undo_edit()
    assert [obj.group_id for obj in layer.objects] == ["first", "second", None]
    assert layer.objects[2] is third


def test_grouped_text_remains_editable_without_losing_manual_group(drawing, monkeypatch):
    window, layer = drawing
    entity = TextEntity("PCB", Point.of(0, 0), D(2), D("0.2"), "Stroke PCB")
    layer.objects = text_objects(layer, entity, Polarity.DARK)
    window.refresh()
    window.canvas.select_object(window.canvas.object_items[layer.objects[0].id])
    window.group_selection()
    group_id = layer.objects[0].group_id

    class TextDialog:
        def __init__(self, *args):
            pass

        def exec(self):
            return True

        def values(self):
            return {
                "text": "PCB-2",
                "position": entity.position,
                "height": entity.height,
                "stroke": entity.stroke,
                "family": entity.family,
            }

    monkeypatch.setattr("gerber_editor.app.edit_actions.TextDialog", TextDialog)
    window.edit_properties()
    assert group_id and all(obj.group_id == group_id for obj in layer.objects)
    assert all(obj.text_entity.text == "PCB-2" for obj in layer.objects)
    window.undo_edit()
    assert all(obj.group_id == group_id and obj.text_entity.text == "PCB" for obj in layer.objects)


@pytest.mark.parametrize(
    "language,heading", [("pt_BR", "Agrupar e desagrupar"), ("en", "Grouping and ungrouping")]
)
def test_html_help_renders_current_shortcuts_and_all_internal_topics(drawing, language, heading):
    import re

    window, _ = drawing
    window.set_language(language)
    window.group_action.setShortcut("Alt+G")
    html = help_html(window)
    assert heading in html and "Alt+G" in html and "{{" not in html
    anchors = re.findall(r'<a name="([^"]+)"', html)
    links = re.findall(r'href="#([^"]+)"', html)
    assert len(anchors) == len(set(anchors)) and set(links) <= set(anchors)
    assert {"images", "groups", "viewer3d", "shortcuts"} <= set(anchors)
    assert heading in window.help_text()


def test_help_window_is_modeless_searchable_reusable_and_translates(drawing, qapp):
    window, _ = drawing
    window.chrome.actions["help.usage"].trigger()
    help_dialog = window._help_dialog
    qapp.processEvents()
    assert help_dialog.isVisible() and not help_dialog.isModal()
    assert "Agrupar e desagrupar" in help_dialog.browser.toPlainText()
    help_dialog.open_section("groups")
    qapp.processEvents()
    assert help_dialog.browser.verticalScrollBar().value() > 0
    help_dialog.search.setText("agrupada automaticamente")
    help_dialog.find_text()
    assert help_dialog.browser.textCursor().selectedText() == "agrupada automaticamente"
    help_dialog.search.setText("zzzz_missing_topic_zzzz")
    help_dialog.find_text()
    assert help_dialog.message.text() == "Texto não encontrado."
    window.set_language("en")
    assert "Grouping and ungrouping" in help_dialog.browser.toPlainText()
    assert help_dialog.windowTitle() == "Editor Gerber Help"
    help_dialog.close()
    window.show_help()
    assert window._help_dialog is help_dialog and help_dialog.isVisible()


def test_3d_help_opens_the_3d_topic_in_shared_html_guide(drawing):
    from types import SimpleNamespace

    window, _ = drawing
    ViewerMenus.show_help(SimpleNamespace(editor=window))
    assert window._help_dialog.isVisible()
    assert window._help_dialog.section == "viewer3d"
