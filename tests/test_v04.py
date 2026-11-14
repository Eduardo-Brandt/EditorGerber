"""Interactive edits, fabrication-safe transforms, session text and PCB meshes."""

from dataclasses import replace
from decimal import Decimal as D

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from shapely import affinity

from gerber_editor.app.main_window import MainWindow
from gerber_editor.commands.edit_commands import ReplaceTextGroup
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line, Point
from gerber_editor.core.text_entity import TextEntity
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.geometry.rigid import RigidTransform, remap_apertures
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.graphics.canvas import Canvas
from gerber_editor.graphics.snapping import constrain
from gerber_editor.tools.clipboard import decode, encode
from gerber_editor.tools.object_properties import edit_object
from gerber_editor.tools.shapes import create_shape, rectangle_region
from gerber_editor.tools.text_session import text_objects
from gerber_editor.ui.object_dialog import ObjectDialog
from gerber_editor.viewer3d.mesh import build_board, outline_geometry


@pytest.fixture(autouse=True)
def release_clipboard(qapp):
    yield
    qapp.clipboard().clear()
    qapp.processEvents()


def line_layer():
    layer = GerberLayer("editing.gbr", function="F.Silk")
    ap = Aperture(10, "C", (D("0.2"),))
    layer.objects = [
        GerberObject(Line(Point.of(0, 0), Point.of(10, 0)), ap),
        GerberObject(Line(Point.of(0, 10), Point.of(10, 10)), ap),
    ]
    layer.saved_signature = layer.signature()
    return layer


def window_for(layer, qapp):
    window = MainWindow()
    window.add_layer(layer)
    window.show()
    window.canvas.snap_grid = False
    qapp.processEvents()
    return window


def finish(window):
    window.canvas.set_mode("select")
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()


@pytest.mark.parametrize("angle,expected", [(45, Point.of(4, 4)), (90, Point.of(5, 0))])
def test_ortho_exact_directions(angle, expected):
    assert constrain(Point.of(5, 3), Point.of(0, 0), angle) == expected


def test_point_snap_has_priority_over_grid_and_marks_endpoint(qapp):
    layer = line_layer()
    canvas = Canvas()
    canvas.resize(600, 400)
    canvas.rebuild([layer])
    canvas.show()
    canvas.fit_all()
    qapp.processEvents()
    near = QPointF(10.05, 0.04)
    assert canvas.snap(near) == Point.of(10, 0)
    assert canvas.snap_target == Point.of(10, 0)
    canvas.snap_points = False
    assert canvas.snap(near) != Point.of(10, 0)
    canvas.close()


def test_shift_constrains_mouse_line_without_changing_arc_direction(qapp):
    window = window_for(line_layer(), qapp)
    window.canvas.snap_points = False
    window.set_tool("line")
    canvas = window.canvas
    a = canvas.mapFromScene(QPointF(2, 2))
    b = canvas.mapFromScene(QPointF(8, 5))
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=a)
    QTest.mouseClick(
        canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, b
    )
    g = window.active_layer.objects[-1].geometry
    assert abs(g.end.x - g.start.x) == abs(g.end.y - g.start.y)
    assert not canvas.arc_clockwise
    finish(window)


def test_drag_move_undo_and_escape_keep_original_geometry(qapp):
    layer = line_layer()
    window = window_for(layer, qapp)
    canvas = window.canvas
    canvas.snap_points = False
    initial = list(layer.objects)
    first = canvas.mapFromScene(QPointF(5, 0))
    end = canvas.mapFromScene(QPointF(7, 3))
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton, pos=first)
    assert len(canvas.selected_objects()) == 1
    window.start_move()
    assert canvas.mode == "placement"
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert layer.objects == initial
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseMove(canvas.viewport(), end)
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert layer.objects[0].geometry != initial[0].geometry
    assert layer.objects[1] == initial[1]
    window.history.undo()
    assert layer.objects == initial
    finish(window)


def test_native_clipboard_cut_paste_preserves_geometry_order_and_undo(qapp):
    layer = line_layer()
    window = window_for(layer, qapp)
    canvas = window.canvas
    canvas.object_items[layer.objects[0].id].setSelected(True)
    canvas._cursor = QPointF(0, 0)
    assert window.copy_clipboard()
    original = list(layer.objects)
    window.cut_clipboard()
    assert len(layer.objects) == 1
    window.paste_clipboard()
    assert canvas.mode == "placement"
    window._commit_placement(Point.of(20, 5))
    assert layer.objects[-1].geometry == Line(Point.of("20.1", "5.1"), Point.of("30.1", "5.1"))
    assert layer.objects[-1].bounds.left == 20 and layer.objects[-1].bounds.bottom == 5
    assert layer.objects[-1].id != original[0].id
    window.history.undo()
    window.history.undo()
    assert layer.objects == original
    assert window.copy_action.shortcut().toString() == "Ctrl+C"
    assert window.cut_action.shortcut().toString() == "Ctrl+X"
    assert window.paste_action.shortcut().toString() == "Ctrl+V"
    finish(window)


@pytest.mark.parametrize(
    "shape,parameters",
    [("R", (D(4), D(2), D(1))), ("O", (D(4), D(2), D(1))), ("P", (D(4), D(5), D(17), D(1)))],
)
def test_rotated_aperture_keeps_shape_and_transparent_holes(shape, parameters):
    obj = GerberObject(Flash(Point.of(0, 0)), Aperture(10, shape, parameters))
    rotated = RigidTransform(angle=37, mirror_x=True).object(obj, D("0.000001"), clone=True)
    expected = affinity.rotate(
        affinity.scale(object_geometry(obj), xfact=-1, yfact=1, origin=(0, 0)), 37, origin=(0, 0)
    )
    assert object_geometry(rotated).symmetric_difference(expected).area < 0.005
    layer = GerberLayer("rotated.gbr", objects=[rotated])
    GerberWriter().serialize(layer, SaveMode.NORMALIZED)


def test_mirror_arc_flips_direction_without_flattening():
    original = GerberObject(
        Arc(Point.of(5, 0), Point.of(0, 5), Point.of(0, 0), False), Aperture(10, "C", (D("0.2"),))
    )
    mirrored = RigidTransform(mirror_x=True).object(original, D("0.000001"), clone=True)
    assert mirrored.geometry.clockwise
    assert mirrored.geometry.start == Point.of(-5, 0)
    assert original.geometry.start == Point.of(5, 0)


def test_oblique_rectangular_stroke_copy_remains_exportable():
    obj = GerberObject(Line(Point.of(0, 0), Point.of(10, 0)), Aperture(10, "R", (D(2), D(1))))
    copied = RigidTransform(angle=30).object(obj, D("0.000001"), clone=True)
    expected = affinity.rotate(object_geometry(obj), 30, origin=(0, 0))
    assert object_geometry(copied).symmetric_difference(expected).area < 0.0001
    GerberWriter().serialize(GerberLayer("copy.gbr", objects=[copied]))


def test_rectangular_and_polar_arrays_are_single_undo_commands(qapp):
    layer = line_layer()
    window = window_for(layer, qapp)
    original = list(layer.objects)
    values = dict(
        polar=False,
        nx=3,
        ny=2,
        dx=D(15),
        dy=D(20),
        count=4,
        sweep=360,
        center=Point.of(0, 0),
        rotate=True,
    )
    window.create_array([(layer, [layer.objects[0]])], values)
    assert len(layer.objects) == len(original) + 5
    assert layer.objects[-1].geometry.start == Point.of(30, 20)
    window.history.undo()
    assert layer.objects == original
    window.create_array([(layer, [layer.objects[0]])], {**values, "polar": True})
    assert len(layer.objects) == len(original) + 3
    assert layer.objects[-1].geometry.end == Point.of(0, -10)
    GerberWriter().serialize(layer)
    window.history.undo()
    finish(window)


def test_polar_array_without_rotation_orbits_the_selection(qapp):
    layer = line_layer()
    window = window_for(layer, qapp)
    values = dict(polar=True, count=4, sweep=360, center=Point.of(0, 0), rotate=False)
    window.create_array([(layer, [layer.objects[0]])], values)
    first_copy = layer.objects[2].geometry
    assert first_copy.start == Point.of(-5, 5)
    assert first_copy.end == Point.of(5, 5)
    window.history.undo()
    finish(window)


def test_property_width_and_length_do_not_change_shared_apertures(qapp):
    layer = line_layer()
    before = layer.objects[1]
    dialog = ObjectDialog(layer.objects[0])
    values = {
        **dialog.values(),
        "width": D("0.7"),
        "length": D(20),
        "direction": 90,
        "by_length": True,
    }
    edited = edit_object(layer, layer.objects[0], values)
    assert edited.geometry.start == Point.of(0, 0)
    assert edited.geometry.end == Point.of(0, 20)
    assert edited.aperture.code != before.aperture.code
    assert before.aperture.width == D("0.2")
    layer.objects[0] = edited
    GerberWriter().serialize(layer)


def test_circle_radius_and_arc_sweep_are_editable(qapp):
    layer = GerberLayer("arc.gbr")
    obj = create_shape(layer, "circle", [Point.of(0, 0), Point.of(3, 0)], D("0.2"))[0]
    dialog = ObjectDialog(obj)
    values = {**dialog.values(), "radius": D(8), "sweep": 90, "clockwise": True}
    edited = edit_object(layer, obj, values)
    assert edited.geometry.radius == D(8)
    assert edited.geometry.end == Point.of(0, -8)
    layer.objects = [edited]
    GerberWriter().serialize(layer)


def test_session_text_clipboard_move_edit_save_and_undo(qapp):
    layer = GerberLayer("text.gbr")
    entity = TextEntity("PCB", Point.of(5, 5), D(2), D("0.2"), "Stroke PCB")
    layer.objects = text_objects(layer, entity, Polarity.DARK)
    originals = list(layer.objects)
    copied, anchor = decode(encode(originals, entity.position))
    assert anchor == entity.position and copied[0].text_entity == entity
    groups = {}
    moved = [
        RigidTransform(dx=D(10)).object(obj, D("0.000001"), clone=True, group_ids=groups)
        for obj in copied
    ]
    assert len({obj.text_entity.group_id for obj in moved}) == 1
    assert moved[0].text_entity.position == Point.of(15, 5)
    replacement = replace(entity, text="PCB-2", family="Segoe UI")
    command = ReplaceTextGroup(
        layer,
        entity.group_id,
        remap_apertures(layer, text_objects(layer, replacement, Polarity.DARK)),
    )
    command.redo()
    assert all(obj.text_entity.text == "PCB-2" for obj in layer.objects)
    data = GerberWriter().serialize(layer)
    assert all(obj.text_entity is None for obj in GerberParser().parse(data).objects)
    assert layer.objects[0].text_entity == replacement
    command.undo()
    assert layer.objects == originals


def test_outline_holes_and_layer_material_heights_do_not_modify_sources():
    edge = GerberLayer("outline.gbr", function="Edge.Cuts")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(40, 30)], D("0.1"))
    edge.objects += create_shape(edge, "rectangle", [Point.of(10, 10), Point.of(20, 20)], D("0.1"))
    assert outline_geometry([edge]).area == pytest.approx(1100)
    copper = GerberLayer(
        "copper.gbr",
        function="B.Cu",
        objects=[GerberObject(rectangle_region(Point.of(1, 1), Point.of(4, 4)), None)],
    )
    before = (edge.signature(), copper.signature())
    mesh = build_board([edge, copper], thickness=1.6)
    assert not mesh.estimated_outline
    assert mesh.size == (40, 30, 1.6)
    assert mesh.triangles > 12
    assert np.all(mesh.parts[-1].vertices[:, 2] < -0.8)
    assert (edge.signature(), copper.signature()) == before
    edge.visible = False
    assert not build_board([edge, copper]).estimated_outline
    top = mesh.parts[0].vertices
    top = top[(top[:, 5] == 1)].reshape(-1, 3, 6)
    area = 0
    for tri in top:
        a, b = tri[1, :2] - tri[0, :2], tri[2, :2] - tri[0, :2]
        area += abs(a[0] * b[1] - a[1] * b[0]) / 2
    assert area == pytest.approx(1100)


def test_estimated_3d_outline_and_help_splash(qapp):
    layer = line_layer()
    assert build_board([layer]).estimated_outline
    window = window_for(layer, qapp)
    assert window.viewer3d_action.shortcut().toString() == "Alt+3"
    window.chrome.actions["help.splash"].trigger()
    assert window._help_splash.isVisible()
    QTest.keyClick(window._help_splash, Qt.Key.Key_Escape)
    assert not window._help_splash.isVisible()
    finish(window)
