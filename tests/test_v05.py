"""Backups, synchronized editing, fabrication additions and real CAD/QR formats."""

import math
from decimal import Decimal as D
from zipfile import ZipFile

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QPushButton

from gerber_editor.app.backup import backup_project
from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer, canonical_function, detect_function
from gerber_editor.core.objects import Aperture, GerberObject
from gerber_editor.core.primitives import Arc, Flash, Line, Point
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter
from gerber_editor.graphics.snapping import object_points
from gerber_editor.tools.object_properties import edit_object
from gerber_editor.tools.pix import pix_payload, qr_image
from gerber_editor.tools.shapes import create_shape, rectangle_region
from gerber_editor.ui.about_dialog import AboutDialog
from gerber_editor.ui.object_dialog import ObjectDialog
from gerber_editor.ui.support_dialog import SupportDialog
from gerber_editor.ui.text_dialog import TextDialog
from gerber_editor.viewer3d.exporters import export_step, export_wrl
from gerber_editor.viewer3d.mesh import build_board
from gerber_editor.viewer3d.viewport import BoardViewport
from gerber_editor.viewer3d.window import Viewer3DWindow


@pytest.fixture(autouse=True)
def clipboard_cleanup(qapp):
    yield
    qapp.clipboard().clear()
    qapp.processEvents()


def board():
    edge = GerberLayer("outline.gbr", function="Edge.Cuts")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(20, 10)], D("0.1"))
    copper = GerberLayer("F.Cu.gbr", function="F.Cu")
    copper.objects = [
        GerberObject(Line(Point.of(2, 5), Point.of(18, 5)), Aperture(10, "C", (D(1),)))
    ]
    mask = GerberLayer("F.Mask.gbr", function="F.Mask")
    mask.objects = [GerberObject(Flash(Point.of(2, 5)), Aperture(10, "C", (D(2),)))]
    return [edge, copper, mask]


def finish(window):
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()


def test_version_zip_preserves_snapshot_and_excludes_generated_files(tmp_path):
    (tmp_path / "source.py").write_text("first")
    for folder in (".venv", "Backup", "output", "__pycache__"):
        (tmp_path / folder).mkdir(exist_ok=True)
        (tmp_path / folder / "excluded.txt").write_text("skip")
    path = backup_project(tmp_path, "0.4.0")
    with ZipFile(path) as archive:
        assert archive.namelist() == ["source.py"]
        assert archive.testzip() is None
    (tmp_path / "source.py").write_text("second")
    assert backup_project(tmp_path, "0.4.0").read_bytes() == path.read_bytes()
    with ZipFile(path) as archive:
        assert archive.read("source.py") == b"first"
    next_version = backup_project(tmp_path, "0.5.0")
    with ZipFile(next_version) as archive:
        assert archive.read("source.py") == b"second"


def test_layer_activation_raises_preview_and_keeps_stack_and_source_data(qapp):
    window = MainWindow()
    first, second = board()[1:]
    second.opacity = 0.5
    window.add_layer(first)
    window.add_layer(second)
    assert second.opacity == 1
    original_order = list(window.layers)
    before = [layer.signature() for layer in window.layers]
    window._active_changed(first)
    assert (
        window.canvas.display_items[first.id].zValue()
        > window.canvas.display_items[second.id].zValue()
    )
    assert window.layers == original_order
    assert [layer.signature() for layer in window.layers] == before
    finish(window)


def test_line_length_angle_and_end_coordinates_synchronize(qapp):
    obj = board()[1].objects[0]
    dialog = ObjectDialog(obj)
    assert dialog.fields["length"].isEnabled() and dialog.fields["direction"].isEnabled()
    dialog.fields["length"].setValue(10)
    dialog.fields["direction"].setValue(90)
    assert dialog.fields["ex"].mm == pytest.approx(D(2), abs=D("0.000001"))
    assert dialog.fields["ey"].mm == pytest.approx(D(15), abs=D("0.000001"))
    dialog.fields["ex"].setValue(5)
    dialog.fields["ey"].setValue(9)
    assert dialog.fields["length"].mm == D(5)
    assert dialog.fields["direction"].value() == pytest.approx(53.130102, abs=0.000001)
    assert not dialog.values()["by_length"]


def test_double_click_selects_object_and_requests_editor(qapp, monkeypatch):
    window = MainWindow()
    layer = board()[1]
    window.add_layer(layer)
    window.show()
    qapp.processEvents()
    captured = []

    class FakeDialog:
        def __init__(self, obj, parent):
            captured.append(obj.id)

        def exec(self):
            return False

    monkeypatch.setattr("gerber_editor.app.edit_actions.ObjectDialog", FakeDialog)
    position = window.canvas.mapFromScene(QPointF(10, 5))
    spy = QSignalSpy(window.canvas.editRequested)
    QTest.mouseDClick(window.canvas.viewport(), Qt.MouseButton.LeftButton, pos=position)
    assert spy.count() == 1 and captured == [layer.objects[0].id]
    finish(window)


def test_text_defaults_retain_content_font_style_and_dimensions(qapp):
    window = MainWindow()
    dialog = TextDialog(Point.of(0, 0), window)
    dialog.text.setText("Eduardo")
    dialog.kind.setCurrentIndex(1)
    dialog.height.set_mm(D("3.2"))
    dialog.rotation.setValue(25)
    dialog.bold.setChecked(True)
    window.remember_text(dialog.values())
    next_dialog = TextDialog(Point.of(10, 20), window)
    values = next_dialog.values()
    assert values["text"] == "Eduardo" and values["height"] == D("3.2")
    assert values["bold"] and values["rotation"] == 25
    assert values["family"] == dialog.values()["family"]
    assert values["position"] == Point.of(10, 20)
    finish(window)


def test_snap_midpoints_and_only_cardinal_points_on_the_arc():
    obj = board()[1].objects[0]
    assert Point.of(10, 5) in object_points(obj)
    ap = obj.aperture
    arc = GerberObject(Arc(Point.of(5, 0), Point.of(0, 5), Point.of(0, 0), False), ap)
    points = object_points(arc)
    assert Point.of(5, 0) in points and Point.of(0, 5) in points
    assert Point.of(-5, 0) not in points
    assert any(abs(float(p.x) - 5 / math.sqrt(2)) < 1e-10 and p.x == p.y for p in points)
    circle = GerberObject(Arc(Point.of(5, 0), Point.of(5, 0), Point.of(0, 0), False), ap)
    assert Point.of(-5, 0) in object_points(circle)


def test_fiducials_are_exportable_copper_and_mask_pairs_with_atomic_undo(qapp):
    window = MainWindow()
    window.create_fiducial(Point.of(12, 8), D(1), D(2), "FB")
    assert {layer.function for layer in window.layers} == {"F.Cu", "B.Cu", "F.Mask", "B.Mask"}
    for layer in window.layers:
        assert layer.objects[0].geometry.position == Point.of(12, 8)
        assert layer.objects[0].aperture.width == (
            D(2) if layer.function.endswith("Mask") else D(1)
        )
        reopened = GerberParser().parse(GerberWriter().serialize(layer), "unknown.gbr")
        assert reopened.function == layer.function
    window.history.undo()
    assert not window.layers
    window.history.redo()
    assert len(window.layers) == 4
    finish(window)


def test_routing_slots_cut_substrate_and_copper_even_when_hidden(qapp):
    layers = board()
    window = MainWindow()
    for layer in layers:
        window.add_layer(layer)
    source = list(layers[1].objects)
    window.create_cutouts(source, width=D(2))
    routing = window.active_layer
    assert routing.function == "Route.Cuts"
    assert layers[1].objects == source
    routing.visible = False
    mesh = build_board(window.layers, tolerance=0.001)
    removed = object_geometry(routing.objects[0]).area
    assert mesh.outline.area == pytest.approx(200 - removed, abs=0.01)
    copper_parts = [p for p in mesh.parts if p.key == layers[1].id]
    assert not copper_parts  # Its trace lies completely inside the wider slot.
    reopened = GerberParser().parse(GerberWriter().serialize(routing), "renamed.gbr")
    assert reopened.function == "Route.Cuts"
    window.history.undo()
    assert len(window.layers) == 3
    finish(window)


def test_closed_circle_is_a_filled_cutout_not_a_ring(qapp):
    window = MainWindow()
    edge = board()[0]
    window.add_layer(edge)
    circle = create_shape(edge, "circle", [Point.of(10, 5), Point.of(12, 5)], D("0.1"))
    window.create_cutouts(circle, closed=True)
    mesh = build_board(window.layers, tolerance=0.001)
    assert mesh.outline.area == pytest.approx(200 - math.pi * 4, abs=0.03)
    finish(window)


def test_region_editor_moves_exact_geometry_and_accepts_filled_cutout(qapp):
    layer = board()[0]
    region = GerberObject(rectangle_region(Point.of(5, 3), Point.of(9, 7)), None)
    dialog = ObjectDialog(region)
    values = {**dialog.values(), "offset_x": D(2), "offset_y": D(1)}
    changed = edit_object(layer, region, values)
    assert changed.bounds.left == 7 and changed.bounds.bottom == 4
    window = MainWindow()
    window.add_layer(layer)
    window.create_cutouts([region], closed=True)
    assert build_board(window.layers).outline.area == pytest.approx(200 - 16)
    finish(window)


def test_circular_stroke_slot_keeps_the_island(qapp):
    window = MainWindow()
    edge = board()[0]
    window.add_layer(edge)
    circle = create_shape(edge, "circle", [Point.of(10, 5), Point.of(12, 5)], D("0.1"))
    window.create_cutouts(circle, closed=False, width=D(1))
    routing = window.active_layer
    expected = object_geometry(routing.objects[0]).area
    mesh = build_board(window.layers, tolerance=0.001)
    assert mesh.outline.area == pytest.approx(200 - expected, abs=0.03)
    assert mesh.outline.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(10, 5))
    reopened = GerberParser().parse(GerberWriter().serialize(routing), "cut.gbr")
    assert dict(reopened.objects[0].attributes)["EditorGerberCut"] == ("Stroke",)
    finish(window)


@pytest.mark.parametrize(
    "name,role",
    [
        ("PCB_F_Cu.gbr", "F.Cu"),
        ("PCB_B_Cu.gbr", "B.Cu"),
        ("Inner1.gbr", "In1.Cu"),
        ("PCB-Iner2_Cu.gbr", "In2.Cu"),
        ("pin1.gbr", "Mechanical"),
    ],
)
def test_copper_layer_names_are_classified_without_false_back_matches(name, role):
    assert detect_function(name)[0] == role
    if role.startswith("In"):
        assert canonical_function(role.replace("In", "Inner")) == role


def test_mask_has_visible_copper_relief_and_inner_layers_generate_tracks():
    layers = board()
    inner = GerberLayer("Inner1", objects=list(layers[1].objects), function="Inner1")
    mesh = build_board([*layers, inner])
    mask_parts = [p for p in mesh.parts if p.key == layers[2].id]
    assert len(mask_parts) == 2 and mask_parts[0].color != mask_parts[1].color
    assert mask_parts[0].z_max > mask_parts[1].z_max
    internal = next(p for p in mesh.parts if p.key == inner.id)
    assert -0.8 < internal.z_max < 0.8 and len(internal.vertices)


def test_pan_follows_vertical_drag_and_flip_is_reversible(qapp):
    viewport = BoardViewport()
    for pitch in (50, -50, 0):
        viewport.pitch = pitch
        viewport.pan_x = viewport.pan_y = viewport.pan_z = 0
        viewport.pan_by(0, 10)
        yaw, angle = math.radians(viewport.yaw), math.radians(pitch)
        screen_up = np.array(
            [-math.sin(angle) * math.cos(yaw), -math.sin(angle) * math.sin(yaw), math.cos(angle)]
        )
        assert np.dot([viewport.pan_x, viewport.pan_y, viewport.pan_z], screen_up) > 0
    viewport.flip_board(False)
    assert viewport.flip_angle == 180
    viewport.flip_board(False)
    assert viewport.flip_angle == 0
    viewport.close()


def test_3d_is_an_independent_top_level_window_with_app_icon(qapp):
    window = MainWindow()
    viewer = Viewer3DWindow(window)
    assert viewer.parentWidget() is None and viewer.isWindow()
    assert not viewer.windowIcon().isNull()
    assert viewer.flip_action.shortcut().toString() == "F"
    viewer.close()
    finish(window)


def test_pix_matches_official_bcb_crc_example_and_qr_has_quiet_zone(qapp):
    code = pix_payload("123e4567-e12b-12d1-a456-426655440000", "Fulano de Tal", "BRASILIA")
    assert code.endswith("63041D3D")
    assert "540" not in code  # No amount field in this static example.
    image = qr_image(code)
    assert image.width() == image.height() and image.pixelColor(0, 0).lightness() == 255
    window = MainWindow()
    support = SupportDialog(window)
    assert "2350fa9a-0838-447f-a9e9-87677a6bf7bf" in support.payload
    assert any(
        "PayPal" in b.text() and not b.isEnabled() for b in support.findChildren(QPushButton)
    )
    about = AboutDialog(window)
    assert "GPLv3" in " ".join(
        label.text()
        for label in about.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)
    )
    finish(window)


def test_wrl_is_loaded_by_independent_vrml_reader(tmp_path):
    vtk_import = pytest.importorskip("vtkmodules.vtkIOImport")
    mesh = build_board(board())
    path = tmp_path / "pcb.wrl"
    export_wrl(mesh, path)
    importer = vtk_import.vtkVRMLImporter()
    importer.SetFileName(str(path))
    importer.Update()
    actors = importer.GetRenderer().GetActors()
    assert actors.GetNumberOfItems() == len(mesh.parts)
    actors.InitTraversal()
    assert actors.GetNextActor().GetBounds()[1] == pytest.approx(0.020)


def test_step_reopens_with_solid_geometry_and_material_colors(tmp_path):
    pytest.importorskip("OCP")
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    mesh = build_board(board())
    path = tmp_path / "pcb.step"
    export_step(mesh, path)
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    document = TDocStd_Document(TCollection_ExtendedString("QA"))
    assert reader.Transfer(document)
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    roots = TDF_LabelSequence()
    shapes.GetFreeShapes(roots)
    assert roots.Length() == 1
    assert BRepCheck_Analyzer(shapes.GetShape_s(roots.Value(1))).IsValid()
    colors = TDF_LabelSequence()
    XCAFDoc_DocumentTool.ColorTool_s(document.Main()).GetColors(colors)
    assert colors.Length() >= 4
