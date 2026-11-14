"""Physical drill cuts, layer order and maximized startup regressions."""

from decimal import Decimal as D
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from shapely.geometry import Point as GeometryPoint

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer, canonical_function, detect_function
from gerber_editor.core.layer_order import ordered_back_to_front
from gerber_editor.core.objects import GerberObject
from gerber_editor.core.primitives import Point
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter
from gerber_editor.tools.drilling import drill_geometry
from gerber_editor.tools.shapes import create_shape, rectangle_region
from gerber_editor.viewer3d.exporters import export_step
from gerber_editor.viewer3d.mesh import build_board

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "drill.gbr"


def board():
    outline = GerberLayer("outline.gbr", function="Edge.Cuts")
    outline.objects = create_shape(
        outline, "rectangle", [Point.of(0, 0), Point.of(20, 10)], D("0.1")
    )
    copper = GerberLayer("F.Cu.gbr", function="F.Cu")
    copper.objects = [GerberObject(rectangle_region(Point.of(0, 0), Point.of(20, 10)), None)]
    drill = GerberParser().parse_file(FIXTURE)
    return outline, copper, drill


def wait_until(qapp, predicate):
    deadline = monotonic() + 10
    while not predicate() and monotonic() < deadline:
        qapp.processEvents()
        QTest.qWait(10)
    assert predicate()


@pytest.mark.parametrize(
    "name,role",
    [
        ("fur", "Drill"),
        ("pcb-PTH.gbr", "Drill.PTH"),
        ("pcb-NPTH.gbr", "Drill.NPTH"),
        ("drill-map.gbr", "Drill drawing"),
    ],
)
def test_drill_detection_distinguishes_real_holes_from_maps(name, role):
    assert detect_function(name)[0] == role


def test_drill_file_function_overrides_name_and_preserves_source():
    data = FIXTURE.read_bytes()
    layer = GerberParser().parse(data, "unrelated_name.gbr")
    assert layer.function == "Drill.PTH"
    assert GerberWriter().serialize(layer) == data
    npth = data.replace(b"Plated,1,2,PTH", b"NonPlated,1,2,NPTH")
    assert GerberParser().parse(npth).function == "Drill.NPTH"
    drawing = data.replace(b"Plated,1,2,PTH,Drill", b"Drillmap")
    assert GerberParser().parse(drawing).function == "Drill drawing"


def test_3d_drill_and_slot_cut_substrate_copper_and_inner_walls():
    layers = board()
    before = [layer.signature() for layer in layers]
    data = GerberWriter().serialize(layers[-1])
    holes = drill_geometry(layers)
    mesh = build_board(layers, tolerance=0.15)
    assert mesh.outline.area == pytest.approx(200 - holes.area, abs=1e-8)
    for part in mesh.parts:
        assert not part.geometry.covers(GeometryPoint(5, 5))
        assert not part.geometry.covers(GeometryPoint(13.5, 3))
        assert not part.geometry.covers(GeometryPoint(18, 8))
    # Hole walls point into the cavity; top/bottom triangles leave it open.
    substrate = next(part for part in mesh.parts if part.key == "substrate")
    xy = substrate.vertices[:, :2] + np.asarray(mesh.center)
    distance = np.linalg.norm(xy - [5, 5], axis=1)
    walls = (np.abs(substrate.vertices[:, 5]) < 0.1) & (np.abs(distance - 0.6) < 1e-5)
    assert np.any(walls)
    assert np.all(np.sum(substrate.vertices[walls, 3:5] * ([5, 5] - xy[walls]), axis=1) > 0)
    assert [layer.signature() for layer in layers] == before
    assert GerberWriter().serialize(layers[-1]) == data


def test_hiding_drill_layer_does_not_fill_physical_holes():
    layers = board()
    original = build_board(layers).outline
    layers[-1].visible = False
    assert build_board(layers).outline.equals(original)
    layers[-1].function = "Drill drawing"
    assert build_board(layers).outline.area == pytest.approx(200)


def test_blind_drill_is_not_silently_cut_through_the_board():
    data = FIXTURE.read_bytes().replace(b"PTH,Drill", b"Blind,Drill")
    drill = GerberParser().parse(data)
    assert drill.function == "Drill.Blind"
    with pytest.raises(ValueError, match="cegos/enterrados"):
        build_board([*board()[:2], drill])


def test_step_contains_real_voids_through_substrate(tmp_path):
    pytest.importorskip("OCP")
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    outline, _, drill = board()
    path = tmp_path / "through_drill.step"
    export_step(build_board([outline, drill]), path)
    reader = STEPControl_Reader()
    assert int(reader.ReadFile(str(path))) == 1
    reader.TransferRoots()
    explorer = TopExp_Explorer(reader.OneShape(), TopAbs_SOLID)
    assert explorer.More()
    solid = TopoDS.Solid_s(explorer.Current())
    assert BRepCheck_Analyzer(solid).IsValid()
    assert BRepClass3d_SolidClassifier(solid, gp_Pnt(5, 5, 0), 1e-7).State() == TopAbs_OUT
    assert BRepClass3d_SolidClassifier(solid, gp_Pnt(1, 1, 0), 1e-7).State() == TopAbs_IN


def test_natural_layer_order_has_silk_front_and_internal_copper_in_order():
    roles = ["B.Cu", "In10.Cu", "F.Cu", "F_Silk", "In2.Cu", "In1.Cu"]
    layers = [GerberLayer(role, function=role) for role in roles]
    result = ordered_back_to_front(layers)
    assert [canonical_function(layer.function) for layer in reversed(result)] == [
        "F.Silk",
        "F.Cu",
        "In1.Cu",
        "In2.Cu",
        "In10.Cu",
        "B.Cu",
    ]


def test_empty_batch_autosorts_and_buttons_reorder_with_undo(qapp, tmp_path):
    window = MainWindow()
    assert not window.layer_panel.up_button.isEnabled()
    assert not window.layer_panel.down_button.isEnabled()
    functions = ["Copper,L4,Bot", "Copper,L3,Inr", "Legend,Top", "Copper,L2,Inr", "Copper,L1,Top"]
    paths = []
    for index, function in enumerate(functions):
        path = tmp_path / f"layer_{index}.gbr"
        path.write_text(
            f"%FSLAX46Y46*%%MOMM*%%TF.FileFunction,{function}*%%ADD10C,1*%D10*X5000000Y5000000D03*M02*"
        )
        paths.append(path)
    window.open_paths_async(paths)
    wait_until(qapp, lambda: not window._import_jobs)
    assert [layer.function for layer in reversed(window.layers)] == [
        "F.Silk",
        "F.Cu",
        "In2.Cu",
        "In3.Cu",
        "B.Cu",
    ]
    signatures = {layer.id: layer.signature() for layer in window.layers}
    original = list(window.layers)
    bottom = window.layers[0]
    item = window.layer_panel.tree.topLevelItem(len(original) - 1)
    window.layer_panel.tree.setCurrentItem(item)
    qapp.processEvents()
    assert window.active_layer is bottom
    assert window.layers == original
    assert (
        window.canvas.display_items[bottom.id].zValue()
        > window.canvas.display_items[original[-1].id].zValue()
    )
    assert not window.layer_panel.down_button.isEnabled()
    QTest.mouseClick(window.layer_panel.up_button, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: window.layers != original)
    assert window.layers[1] is bottom
    assert window.active_layer is bottom
    window.history.undo()
    assert window.layers == original
    window.history.redo()
    assert window.layers[1] is bottom
    assert {layer.id: layer.signature() for layer in window.layers} == signatures
    window.history.undo()
    window.history.undo()
    assert not window.layers
    window.history.redo()
    assert window.layers == original
    window.close()


def test_existing_stack_is_kept_when_importing_another_batch(qapp, tmp_path):
    window = MainWindow()
    existing = GerberLayer("existing.gbr", function="F.Silk")
    window.add_layer(existing)
    paths = []
    for index, function in enumerate(("Legend,Top", "Copper,L1,Top")):
        path = tmp_path / f"added_{index}.gbr"
        path.write_text(
            f"%FSLAX46Y46*%%MOMM*%%TF.FileFunction,{function}*%%ADD10C,1*%D10*X0Y0D03*M02*"
        )
        paths.append(path)
    window.open_paths_async(paths)
    wait_until(qapp, lambda: not window._import_jobs)
    assert window.layers[0] is existing
    assert [layer.function for layer in window.layers[1:]] == ["F.Silk", "F.Cu"]
    window.close()


def test_icon_has_small_windows_sizes_and_large_pcb_coverage(qapp):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage

    from gerber_editor.ui.branding import application_icon

    icon = application_icon()
    assert not icon.isNull()
    assert {QSize(n, n) for n in (16, 24, 32, 48, 64, 128, 256)} <= set(icon.availableSizes())
    image = QImage(str(FIXTURE.parents[1] / "gerber_editor/assets/app_icon.png"))
    # The central crop fills the icon; transparency is no longer required.
    assert not image.isNull()
    pixels = image.convertToFormat(QImage.Format.Format_RGBA8888)
    rgba = np.frombuffer(pixels.constBits(), dtype=np.uint8).reshape(
        image.height(), image.width(), 4
    )
    y, x = np.nonzero(rgba[:, :, 3] > 128)
    assert (x.max() - x.min()) / image.width() > 0.94
    assert (y.max() - y.min()) / image.height() > 0.85


def test_opening_3d_requests_maximized_and_keeps_existing_window(qapp):
    class Viewer:
        visible = False
        maximized_calls = 0

        def isVisible(self):
            return self.visible

        def showMaximized(self):
            self.visible = True
            self.maximized_calls += 1

        def show(self):
            self.visible = True

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def request_refresh(self):
            pass

        def close(self):
            self.visible = False

    window = MainWindow()
    window.add_layer(GerberLayer("layer.gbr"))
    window._viewer3d = Viewer()
    window.show_3d()
    assert window._viewer3d.maximized_calls == 1
    window.show_3d()
    assert window._viewer3d.maximized_calls == 1
    window.close()
