from decimal import Decimal as D
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from shapely.geometry import Point as ShapelyPoint

from gerber_editor.app.importer import looks_like_gerber
from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.primitives import Point
from gerber_editor.geometry.boolean import aperture_shape
from gerber_editor.gerber.errors import GerberError, SaveError, UnsupportedGerberError
from gerber_editor.gerber.macros import expression
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "legacy_cam.gbr"


def test_extensionless_legacy_and_rounded_arc_export(tmp_path):
    path = tmp_path / "srlc"
    path.write_bytes(FIXTURE.read_bytes())
    assert looks_like_gerber(path)
    layer = GerberParser().parse_file(path)
    assert layer.function == "F.Silk"
    assert len(layer.objects) == 4
    assert layer.objects[0].geometry.start == Point.of(1, 2)
    assert GerberWriter().serialize(layer) == path.read_bytes()
    for mode in SaveMode:
        GerberWriter().serialize(layer, mode)
    layer.objects.pop(0)
    for mode in SaveMode:
        target = tmp_path / f"edited_{mode.value}.gbr"
        GerberWriter().save(layer, target, mode)
        assert GerberParser().parse_file(target).function == "F.Silk"
    assert path.read_bytes() == FIXTURE.read_bytes()
    cache = tmp_path / "fp-info-cache"
    cache.write_text("0\n")
    assert not looks_like_gerber(cache)


def test_macro_variables_clear_primitives_and_units():
    data = (
        "%FSLAX26Y26*%%MOIN*%"
        "%AMTEST*$2=$1/2*21,1,$1,$1,0,0,0*1,0,$2,0,0,0*%"
        "%ADD10TEST,0.1*%D10*X0Y0D03*M02*"
    )
    layer = GerberParser().parse(data)
    aperture = layer.objects[0].aperture
    assert aperture.macro[0].values[1] == D("2.54")
    shape = aperture_shape(aperture)
    assert shape.area > 5 and not shape.contains(ShapelyPoint(0, 0))
    for mode in SaveMode:
        GerberWriter().serialize(layer, mode)


@pytest.mark.parametrize("source", ["__import__('os')", "2**3", "1/0", "1e3", "$1[0]", "(1+"])
def test_macro_expressions_are_not_python(source):
    with pytest.raises(GerberError):
        expression(source, {})


def test_negative_image_is_not_silently_accepted():
    with pytest.raises(UnsupportedGerberError, match="IPNEG"):
        GerberParser().parse(FIXTURE.read_bytes().replace(b"IPPOS", b"IPNEG"))


def test_kicad_layout_and_background_import(qapp):
    window = MainWindow()
    assert window.dockWidgetArea(window.layer_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert window.manager_tabs.tabText(0) == "Camadas"
    assert window.manager_tabs.tabText(1) == "Itens"
    assert window.canvas.backgroundBrush().color().name() == "#000000"
    assert not window.canvas.grid_visible
    from PySide6.QtTest import QTest

    window.open_paths_async([FIXTURE])
    for _ in range(100):
        qapp.processEvents()
        if not window._import_jobs:
            break
        QTest.qWait(20)
    assert not window._import_jobs
    assert len(window.layers) == 1
    assert window.layer_combo.currentText() == "legacy_cam.gbr"
    window.grid_action.trigger()
    assert window.canvas.grid_visible
    window.set_tool("line")
    window.canvas.set_mode("select")
    assert window.select_action.isChecked()
    before = len(window.active_layer.objects)
    window.set_tool("measure")
    window.canvas.snap(QPointF(0, 0))
    assert len(window.active_layer.objects) == before
    window.close()


def test_copy_preserves_dark_clear_fabrication_order(qapp):
    window = MainWindow()
    layer = window.open_path(FIXTURE.parent / "basic.gbr")
    original = list(layer.objects)
    window.canvas.select_all()
    window.translate_selected(D(20), D(0), copy=True)
    copied = layer.objects[len(original) :]
    assert [(obj.kind, obj.polarity) for obj in copied] == [
        (obj.kind, obj.polarity) for obj in original
    ]
    GerberWriter().serialize(layer)
    window.history.undo()
    window.close()


def test_move_and_copy_keep_exact_data_and_single_step_undo(qapp):
    window = MainWindow()
    window.load_demo()
    layer = window.active_layer
    original = list(layer.objects)
    window.canvas.select_all()
    window.translate_selected(D("1.25"), D("-2.5"))
    assert len(layer.objects) == len(original)
    assert layer.objects[0].geometry.start.x == original[0].geometry.start.x + D("1.25")
    with pytest.raises(SaveError, match="normalized"):
        GerberWriter().serialize(layer)
    GerberWriter().serialize(layer, SaveMode.NORMALIZED)
    window.history.undo()
    assert layer.objects == original
    window.canvas.select_all()
    window.translate_selected(D("10"), D("0"), copy=True)
    assert len(layer.objects) == len(original) * 2
    assert len({obj.id for obj in layer.objects}) == len(layer.objects)
    GerberWriter().serialize(layer)
    window.history.undo()
    assert layer.objects == original
    window.close()
