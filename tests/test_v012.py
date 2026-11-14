"""Drill interoperability, filled shapes, selective bulk edits and 3D progress."""

from dataclasses import replace
from decimal import Decimal as D
from math import pi
from time import monotonic, sleep
from types import SimpleNamespace

import pytest
from PySide6.QtTest import QSignalSpy
from shapely.geometry import Point as ShapePoint

from gerber_editor.app.importer import looks_like_gerber
from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject
from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.geometry.rigid import remap_apertures
from gerber_editor.gerber.errors import GerberError, SaveError
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.tools.editable_shapes import edit_shape, recognize, shape_selection
from gerber_editor.tools.shapes import create_shape
from gerber_editor.ui.array_dialog import ArrayDialog
from gerber_editor.ui.parameter_dialog import ParameterDialog
from gerber_editor.viewer3d.mesh import build_board
from gerber_editor.viewer3d.window import Viewer3DWindow


def drill(body, units="METRIC", fmt=""):
    return f"M48\n{fmt}\n{units}\nT1C0.8\n%\nG90\nG05\nT1\n{body}\nM30\n"


@pytest.mark.parametrize(
    "units,fmt,body,x,y",
    [
        ("METRIC", "", "X1.25Y-2.5\nY-3.5", "1.25", "-3.5"),
        ("INCH", "", "X1.0Y-0.5", "25.4", "-12.70"),
        ("METRIC,TZ", ";FILE_FORMAT=3:3", "X1250Y2500", "1.250", "2.500"),
        ("METRIC,LZ", ";FILE_FORMAT=3:3", "X00125Y0025", "1.250", "2.500"),
        ("METRIC,TZ,000.000", "", "X1250Y2500", "1.250", "2.500"),
    ],
)
def test_excellon_coordinates_and_modal_axes(units, fmt, body, x, y):
    layer = GerberParser().parse(drill(body, units, fmt), "NPTH.drl")
    assert layer.file_format == "excellon"
    assert layer.objects[-1].geometry.position == Point.of(x, y)
    for mode in SaveMode:
        assert GerberWriter().serialize(layer, mode)


def test_excellon_slots_routed_arcs_incremental_and_repeat():
    body = (
        "X1.0Y2.0G85X3.0Y2.0\nG00X5.0Y5.0\nM15\nG01X7.0Y5.0\n"
        "G03X5.0Y7.0I-2.0J0.0\nM16\nG05\nG91\nX1.0Y1.0\nR2X1.0Y0.0"
    )
    layer = GerberParser().parse(drill(body))
    assert [type(o.geometry) for o in layer.objects] == [Line, Line, Arc, Flash, Flash, Flash]
    assert layer.objects[-1].geometry.position == Point.of(8, 8)
    for mode in SaveMode:
        GerberWriter().serialize(layer, mode)


@pytest.mark.parametrize(
    "data",
    [
        drill("X123Y456"),  # implicit scale must not be guessed
        drill("G00X1.0Y1.0\nG01X2.0Y1.0"),  # missing plunge
        drill("X1.0Y1.0\nG93X2.0"),  # unsupported origin offset
        drill("X1.0Y1.0").replace("T1C0.8", "T1C0"),
        drill("X1.0Y1.0").replace("M30", ""),
    ],
)
def test_excellon_rejects_ambiguous_or_unhandled_data(data):
    with pytest.raises(GerberError):
        GerberParser().parse(data)


def test_excellon_save_and_gerber_conversion_do_not_touch_original(tmp_path):
    source = tmp_path / "pcb-PTH.drl"
    source.write_text(drill("X2.0Y2.0"))
    before = source.read_bytes()
    layer = GerberParser().parse_file(source)
    assert looks_like_gerber(source)
    assert GerberWriter().serialize(layer) == before
    layer.objects.append(replace(layer.objects[0], geometry=Flash(Point.of(5, 5)), id="extra"))
    for suffix in ("drl", "gbr"):
        target = tmp_path / f"copy.{suffix}"
        GerberWriter().save(layer, target)
        assert len(GerberParser().parse_file(target).objects) == 2
    assert source.read_bytes() == before
    assert layer.file_format == "excellon"
    layer.objects = create_shape(
        layer, "circle", [Point.of(2, 2), Point.of(4, 2)], D("0.2"), filled=True
    )
    with pytest.raises(SaveError, match="Salvar como Gerber"):
        GerberWriter().serialize(layer)


def test_excellon_holes_cut_through_3d_even_when_hidden():
    holes = GerberParser().parse(drill("X5.0Y5.0"), "pcb-PTH.drl")
    holes.visible = False
    edge = GerberLayer("Edge_Cuts.gbr", function="Edge.Cuts")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(10, 10)], D("0.1"))
    mesh = build_board([edge, holes])
    assert not mesh.outline.covers(ShapePoint(5, 5))
    assert mesh.outline.covers(ShapePoint(1, 1))


@pytest.mark.parametrize(
    "kind,points,area",
    [
        ("circle", [Point.of(2, 2), Point.of(4, 2)], 4 * pi),
        ("arc", [Point.of(2, 2), Point.of(4, 2), Point.of(2, 4)], pi),
        ("square", [Point.of(0, 0), Point.of(4, 3)], 16),
        ("rectangle", [Point.of(0, 0), Point.of(4, 3)], 12),
    ],
)
def test_filled_shapes_and_property_conversion_roundtrip(kind, points, area):
    layer = GerberLayer("F_Silkscreen.gbr")
    filled = create_shape(layer, kind, points, D("0.2"), filled=True)
    assert len(filled) == 1 and filled[0].aperture is None
    assert object_geometry(filled[0]).area == pytest.approx(area, abs=0.02)
    layer.objects = filled
    reopened = GerberParser().parse(GerberWriter().serialize(layer))
    shape = recognize(reopened, reopened.objects)
    assert shape and shape.values["filled"]
    outline = edit_shape(shape, {"filled": False, "width": D("0.4")})
    restored = edit_shape(recognize(layer, outline), {"filled": True})
    assert object_geometry(restored[0]).equals(object_geometry(filled[0]))


@pytest.fixture
def editor(qapp, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(window, "show_error", lambda title, error: pytest.fail(f"{title}: {error}"))
    window.show()
    yield window
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()
    qapp.processEvents()


def circles(layer):
    return remap_apertures(
        layer,
        [
            create_shape(layer, "circle", [Point.of(x, y), Point.of(x + r, y)], D(w))[0]
            for x, y, r, w in [(0, 0, 2, "0.1"), (15, 8, 4, "0.3"), (30, 20, 5, "0.5")]
        ],
    )


def test_bulk_circle_radius_preserves_centers_widths_and_history(editor, monkeypatch):
    layer = GerberLayer("F_Cu.gbr", function="F.Cu")
    layer.objects = circles(layer)
    original = list(layer.objects)
    editor.add_layer(layer)
    editor.canvas.select_all()
    assert editor.properties.edit_button.isEnabled()

    def accept(dialog):
        assert dialog.changes() == {}
        assert not dialog.apply["cx"].isChecked()
        dialog.fields["radius"].setValue(7)
        return True

    monkeypatch.setattr(ParameterDialog, "exec", accept)
    editor.edit_properties()
    assert [o.geometry.center for o in layer.objects] == [o.geometry.center for o in original]
    assert [o.aperture.width for o in layer.objects] == [o.aperture.width for o in original]
    assert all(o.geometry.radius == 7 for o in layer.objects)
    editor.undo_edit()
    assert layer.objects == original
    editor.redo_edit()
    assert all(o.geometry.radius == 7 for o in layer.objects)


def test_bulk_thickness_preserves_exact_arc_geometry(editor, monkeypatch):
    layer = GerberLayer("circles.gbr", objects=[])
    layer.objects = circles(layer)
    original = list(layer.objects)
    editor.add_layer(layer)
    editor.canvas.select_all()

    def accept(dialog):
        dialog.fields["width"].setValue(0.7)
        return True

    monkeypatch.setattr(ParameterDialog, "exec", accept)
    editor.edit_properties()
    assert [o.geometry for o in layer.objects] == [o.geometry for o in original]
    assert all(o.aperture.width == D("0.7") for o in layer.objects)


def test_bulk_flash_diameter_preserves_positions(editor, monkeypatch):
    layer = GerberParser().parse(drill("X1.0Y2.0\nX5.0Y7.0"))
    before = [o.geometry for o in layer.objects]
    editor.add_layer(layer)
    editor.canvas.select_all()

    def accept(dialog):
        dialog.fields["width"].setValue(1.2)
        return True

    monkeypatch.setattr(ParameterDialog, "exec", accept)
    editor.edit_properties()
    assert [o.geometry for o in layer.objects] == before
    assert all(o.aperture.width == D("1.2") for o in layer.objects)
    GerberWriter().serialize(layer)


def test_bulk_no_changes_and_inch_single_dialog_do_not_edit(editor, monkeypatch):
    editor.set_units("in")
    layer = GerberLayer("circles.gbr")
    layer.objects = circles(layer)
    editor.add_layer(layer)
    values = recognize(layer, [layer.objects[1]]).values
    assert ParameterDialog([values], editor).changes() == {}
    editor.canvas.select_all()
    revision = layer.revision
    monkeypatch.setattr(ParameterDialog, "exec", lambda _: True)
    editor.edit_properties()
    assert layer.revision == revision


def test_rectangle_fill_undo_preserves_order_and_other_objects(editor):
    layer = GerberLayer("shapes.gbr")
    first = create_shape(layer, "rectangle", [Point.of(0, 0), Point.of(4, 3)], D("0.2"))
    second = create_shape(layer, "rectangle", [Point.of(10, 5), Point.of(16, 9)], D("0.4"))
    marker = circles(layer)[0]
    layer.objects = remap_apertures(layer, first + [marker] + second)
    marker = layer.objects[len(first)]
    editor.add_layer(layer)
    items = [SimpleNamespace(layer=layer, obj=o) for o in first + second]
    shapes = shape_selection(items)
    assert len(shapes) == 2
    before = list(layer.objects)
    editor._edit_shapes(shapes, {"filled": True})
    assert len(layer.objects) == 3 and layer.objects[1] is marker
    assert all(isinstance(layer.objects[i].geometry, Region) for i in (0, 2))
    editor.undo_edit()
    assert layer.objects == before
    editor.redo_edit()
    assert len(layer.objects) == 3


def test_polar_radius_and_rectangular_spacing_preserve_original(editor):
    layer = GerberLayer("array.gbr")
    layer.objects = [GerberObject(Flash(Point.of(10, 0)), Aperture(10, "C", (D(1),)))]
    original = layer.objects[0]
    editor.add_layer(layer)
    dialog = ArrayDialog(Point.of(0, 0), editor)
    dialog.kind.setCurrentIndex(1)
    dialog.by_radius.setChecked(True)
    dialog.radius.setValue(10)
    dialog.count.setValue(4)
    dialog.rotate.setChecked(False)
    assert not dialog.values()["pick_center"]
    editor.create_array([(layer, [original])], dialog.values())
    assert [o.geometry.position for o in layer.objects] == [
        Point.of(10, 0),
        Point.of(0, 10),
        Point.of(-10, 0),
        Point.of(0, -10),
    ]
    editor.undo_edit()
    dialog.kind.setCurrentIndex(0)
    dialog.nx.setValue(3)
    dialog.ny.setValue(2)
    dialog.dx.setValue(5)
    dialog.dy.setValue(7)
    editor.create_array([(layer, [original])], dialog.values())
    assert len(layer.objects) == 6 and layer.objects[0] is original
    assert layer.objects[-1].geometry.position == Point.of(20, 7)


def test_3d_progress_reaches_100_and_updates_cached_detail(editor, qapp):
    layer = GerberLayer("F_Cu.gbr", function="F.Cu")
    layer.objects = circles(layer)
    editor.add_layer(layer)
    viewer = Viewer3DWindow(editor)
    spy = QSignalSpy(viewer.progress.valueChanged)

    def finish():
        deadline = monotonic() + 10
        while viewer._job is not None and monotonic() < deadline:
            qapp.processEvents()
            sleep(0.01)
        assert viewer._job is None and not viewer.last_error
        values = [spy.at(i)[0] for i in range(spy.count())]
        assert values[-1] == 100 and any(0 < v < 100 for v in values)
        assert not viewer.progress.isVisible()

    viewer.rebuild()
    finish()
    viewer.detail.blockSignals(True)
    viewer.detail.setCurrentIndex(0)
    viewer.detail.blockSignals(False)
    viewer.rebuild()
    finish()
    viewer.close()
