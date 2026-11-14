from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from gerber_editor.commands.edit_commands import AddObjects, DeleteObjects
from gerber_editor.commands.undo_stack import UndoStack
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Polarity
from gerber_editor.core.primitives import Arc, Flash, Point, Region
from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.gerber.errors import GerberError, SaveError, UnsupportedGerberError
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.tools.drawing import create_line
from gerber_editor.tools.stroke_font import create_text
from gerber_editor.validation.checks import compare_layers

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HEADER = "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\nD10*\n"


def parse(body):
    return GerberParser().parse(HEADER + body + "\nM02*\n")


def test_basic_geometry():
    layer = GerberParser().parse_file(FIXTURES / "basic.gbr")
    assert [o.kind for o in layer.objects] == ["Line", "Arc", "Flash", "Region", "Flash"]
    assert layer.objects[1].geometry.radius == 2
    assert layer.function == "F.Silk"
    assert layer.objects[-1].polarity == Polarity.CLEAR
    assert not layer.modified


@pytest.mark.parametrize("mode", list(SaveMode))
def test_roundtrip(mode):
    layer = GerberParser().parse_file(FIXTURES / "basic.gbr")
    saved = GerberWriter().serialize(layer, mode)
    compare_layers(layer, GerberParser().parse(saved), mode.value)
    if mode == SaveMode.PRESERVATION:
        assert saved == (FIXTURES / "basic.gbr").read_bytes()


@pytest.mark.parametrize("deleted", [0, 1, 2, 3, 4])
def test_delete_each_construct_preserves_rest(deleted):
    layer = GerberParser().parse_file(FIXTURES / "basic.gbr")
    original = list(layer.objects)
    stack = UndoStack()
    stack.push(DeleteObjects([(layer, {original[deleted].id})]))
    saved = GerberWriter().serialize(layer)
    reopened = GerberParser().parse(saved)
    assert len(reopened.objects) == 4
    compare_layers(layer, reopened, "preservation")
    stack.undo()
    assert layer.objects == original and not layer.modified
    stack.redo()
    assert len(layer.objects) == 4


def test_deleted_modal_draw_does_not_change_next_operation():
    layer = parse("X0Y0D02*X1000000D01*X2000000*X3000000*")
    layer.objects.pop(0)
    saved = GerberWriter().serialize(layer)
    assert len(GerberParser().parse(saved).objects) == 2


def test_deleted_flash_does_not_turn_next_modal_flash_into_move():
    layer = parse("X0Y0D03*X1000000*X2000000*")
    layer.objects.pop(0)
    data = GerberWriter().serialize(layer)
    assert len(GerberParser().parse(data).objects) == 2


def test_delete_all_can_export_empty_layer():
    layer = parse("X0Y0D02*X1000000D01*")
    layer.objects.clear()
    assert not GerberParser().parse(GerberWriter().serialize(layer)).objects


def test_units_omitted_coordinates_and_trailing_suppression():
    layer = GerberParser().parse("%FSTAX24Y24*%%MOIN*%%ADD10C,0.01*%D10*X01Y02D02*X02D01*M02*")
    line = layer.objects[0].geometry
    assert line.start == Point(D("25.4"), D("50.8"))
    assert line.end == Point(D("50.8"), D("50.8"))
    compare_layers(
        layer,
        GerberParser().parse(GerberWriter().serialize(layer, SaveMode.NORMALIZED)),
        "normalized",
    )


def test_normalized_retains_subnanometre_inch_coordinates():
    layer = GerberParser().parse("%FSLAX26Y26*%%MOIN*%%ADD10C,0.01*%D10*X1Y1D03*M02*")
    data = GerberWriter().serialize(layer, SaveMode.NORMALIZED)
    assert b"MOIN" in data
    assert GerberParser().parse(data).objects[0].geometry.position.x == D("0.0000254")


def test_x2_attribute_scopes():
    layer = parse("%TO.N,NET1*%X0Y0D03*%TD.N*%X1000000D03*")
    assert dict(layer.objects[0].attributes)[".N"] == ("NET1",)
    assert layer.objects[1].attributes == ()
    GerberWriter().serialize(layer, SaveMode.NORMALIZED)


def test_full_circle_and_single_quadrant_arcs():
    layer = parse("G75*X1000000Y0D02*G02X1000000Y0I-1000000J0D01*")
    arc = layer.objects[0].geometry
    assert isinstance(arc, Arc) and arc.start == arc.end
    assert layer.bounds.left == pytest.approx(-1.1)
    layer = parse("G74*X1000000Y0D02*G03X0Y1000000I1000000J0D01*")
    assert layer.objects[0].geometry.center == Point.of(0, 0)


def test_region_contours_union_and_clear_order():
    layer = parse(
        "G36*X0Y0D02*X10000000D01*Y10000000D01*X0D01*Y0D01*"
        "X2000000Y2000000D02*X4000000D01*Y4000000D01*X2000000D01*Y2000000D01*G37*"
    )
    assert isinstance(layer.objects[0].geometry, Region)
    assert object_geometry(layer.objects[0]).area == pytest.approx(100)
    layer = parse("%LPC*%X0Y0D03*%LPD*%X0Y0D03*")
    geoms = {o.id: object_geometry(o) for o in layer.objects}
    assert compose_layer(layer.objects, geoms).area > 0
    layer.objects.reverse()
    assert compose_layer(layer.objects, geoms).is_empty


def test_new_line_and_text_and_undo_branch():
    layer = parse("X0Y0D03*")
    objects = [create_line(layer, Point.of(0, 0), Point.of(1, 1), D("0.2"))]
    objects += create_text(layer, "PCB-01", Point.of(3, 3), D(2), D("0.15"))
    stack = UndoStack()
    stack.push(AddObjects(layer, objects))
    for mode in SaveMode:
        GerberWriter().serialize(layer, mode)
    stack.undo()
    assert len(layer.objects) == 1
    stack.push(AddObjects(layer, objects[:1]))
    assert not stack.can_redo
    with pytest.raises(ValueError):
        create_text(layer, "Olá", Point.of(0, 0), D(1), D("0.1"))


@pytest.mark.parametrize(
    "body",
    [
        "D99*X0Y0D03*",
        "G91*",
        "X0Y0D02*G02X1000000Y0I0J0D01*",
        "G36*X0Y0D02*X1000000D01*G37*",
        "%SRX2Y2I1J1*%",
        "%LR90*%",
    ],
)
def test_invalid_or_unsupported_is_rejected(body):
    with pytest.raises(GerberError):
        parse(body)


def test_macro_usage_rejected_explicitly_but_unused_definition_preserved():
    with pytest.raises(UnsupportedGerberError, match="macro"):
        GerberParser().parse_file(FIXTURES / "macro_unsupported.gbr")
    data = HEADER + "%AMUNUSED*1,1,1,0,0*%\nX0Y0D03*M02*"
    layer = GerberParser().parse(data)
    assert GerberWriter().serialize(layer) == data.encode("ascii")


def test_original_protected_and_atomic_save(tmp_path):
    original = tmp_path / "input.gbr"
    original.write_bytes((FIXTURES / "basic.gbr").read_bytes())
    before = original.read_bytes()
    layer = GerberParser().parse_file(original)
    layer.objects.pop(0)
    with pytest.raises(SaveError):
        GerberWriter().save(layer, original)
    target = tmp_path / "input_edited.gbr"
    report = GerberWriter().save(layer, target)
    assert report.object_count == 4 and report.bounds_match
    assert original.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_unrepresentable_coordinates_refused():
    layer = parse("X0Y0D03*")
    line = create_line(layer, Point.of(0, 0), Point(D("1.00000001"), D(0)), D("0.2"))
    layer.objects.append(line)
    with pytest.raises(SaveError, match="precisão"):
        GerberWriter().serialize(layer)


def test_modified_imported_object_requires_normalized():
    layer = parse("X0Y0D03*")
    layer.objects[0] = replace(layer.objects[0], geometry=Flash(Point.of(2, 2)))
    with pytest.raises(SaveError):
        GerberWriter().serialize(layer)
    GerberWriter().serialize(layer, SaveMode.NORMALIZED)


def test_empty_new_layer_exports():
    layer = GerberLayer("new.gbr")
    assert not GerberParser().parse(GerberWriter().serialize(layer)).objects


def test_file_attributes_are_validated_and_stale_checksum_removed():
    layer = parse("%TF.FileFunction,Legend,Top*%%TF.MD5,oldchecksum*%X0Y0D03*X1000000D03*")
    layer.objects.pop(0)
    saved = GerberWriter().serialize(layer)
    assert b"TF.FileFunction,Legend,Top" in saved
    assert b"TF.MD5" not in saved
    layer.attributes = ((".FileFunction", ("Legend", "Bot")),)
    with pytest.raises(SaveError, match="Atributos de arquivo"):
        GerberWriter().serialize(layer)
    GerberWriter().serialize(layer, SaveMode.NORMALIZED)


@pytest.mark.parametrize("shape", ["C,NaN", "R,1XInfinity"])
def test_nonfinite_aperture_is_rejected(shape):
    with pytest.raises(GerberError):
        GerberParser().parse(f"%FSLAX46Y46*%%MOMM*%%ADD10{shape}*%M02*")
