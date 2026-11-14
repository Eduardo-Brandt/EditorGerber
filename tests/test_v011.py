"""KiCad cut-ins, invisible apertures and responsive file batches."""

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QToolBar
from shapely.geometry import Point as ShapePoint

from gerber_editor.app.main_window import MainWindow
from gerber_editor.app.metadata import REPORT_PROBLEM_URL
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject
from gerber_editor.core.primitives import Line, Point, Region
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.gerber.errors import GerberError, SaveError
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.ui.help_dialog import help_html

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "basic.gbr"
HEADER = "%FSLAX46Y46*%%MOMM*%"
CUTIN = [
    (0, 2),
    (2, 2),
    (2, 4),
    (4, 4),
    (4, 2),
    (2, 2),
    (0, 2),
    (0, 0),
    (10, 0),
    (10, 10),
    (0, 10),
    (0, 2),
]


def region(points):
    vertices = [Point.of(*p) for p in points]
    return GerberObject(
        Region((tuple(Line(a, b) for a, b in zip(vertices, vertices[1:], strict=False)),)), None
    )


def wait_until(predicate, timeout=10):
    deadline = monotonic() + timeout
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt operation timed out"


@pytest.fixture
def editor(qapp):
    window = MainWindow()
    window.show()
    yield window
    wait_until(lambda: not window._save_all_running and not window._import_jobs)
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()
    qapp.processEvents()


def dirty_layer(window, path):
    layer = GerberParser().parse(FIXTURE.read_bytes(), path.name, path)
    path.write_bytes(FIXTURE.read_bytes())
    layer.objects.append(replace(layer.objects[0], id=path.stem))
    window.add_layer(layer)
    return layer


@pytest.mark.parametrize("transpose", [False, True])
def test_kicad_cutin_preserves_white_hole_and_exact_source(transpose):
    points = [(y, x) for x, y in CUTIN] if transpose else CUTIN
    obj = region(points)
    geom = object_geometry(obj)
    assert geom.is_valid and geom.area == 96 and len(geom.interiors) == 1
    assert not geom.covers(ShapePoint(3, 3))
    assert geom.covers(ShapePoint(1, 1))
    layer = GerberLayer("KiCad-F_Cu.gbr", objects=[obj])
    writer = GerberWriter()
    source = writer.serialize(layer, SaveMode.NORMALIZED)
    imported = GerberParser().parse(source)
    assert writer.serialize(imported, SaveMode.PRESERVATION) == source
    for mode in SaveMode:
        output = GerberParser().parse(writer.serialize(imported, mode))
        assert output.objects[0].geometry == imported.objects[0].geometry
        assert object_geometry(output.objects[0]).equals(geom)


def test_multiple_cutin_holes_are_not_filled():
    points = CUTIN[:-2] + [
        (0, 10),
        (0, 6),
        (6, 6),
        (6, 8),
        (8, 8),
        (8, 6),
        (6, 6),
        (0, 6),
        (0, 2),
    ]
    geom = object_geometry(region(points))
    assert geom.area == 92 and len(geom.interiors) == 2
    assert not geom.covers(ShapePoint(7, 7))


@pytest.mark.parametrize(
    "points",
    [
        [(0, 0), (5, 5), (5, 0), (0, 5), (0, 0)],  # bow-tie
        [
            (0, 0),
            (2, 2),
            (2, 4),
            (4, 4),
            (4, 2),
            (2, 2),
            (0, 0),
            (10, 0),
            (10, 10),
            (0, 10),
            (0, 0),
        ],  # diagonal bridge
        CUTIN[:7] + [(0, 0), (10, 10), (10, 0), (0, 10), (0, 2)],  # crossed outer ring
        [
            (0, 2),
            (-2, 2),
            (-2, 4),
            (-4, 4),
            (-4, 2),
            (-2, 2),
            (0, 2),
            (0, 0),
            (10, 0),
            (10, 10),
            (0, 10),
            (0, 2),
        ],  # hole outside
    ],
)
def test_invalid_regions_are_still_rejected(points):
    with pytest.raises(GerberError, match="auto-intersectante"):
        object_geometry(region(points))


def test_zero_circle_is_invisible_but_survives_both_save_modes():
    data = HEADER + "%ADD10C,0.000000*%D10*X0Y0D03*X1000000Y0D01*M02*"
    layer = GerberParser().parse(data)
    assert len(layer.objects) == 2
    assert all(object_geometry(obj).is_empty for obj in layer.objects)
    for mode in SaveMode:
        output = GerberParser().parse(GerberWriter().serialize(layer, mode))
        assert all(obj.aperture.width == 0 for obj in output.objects)


@pytest.mark.parametrize("definition", ["C,-0.1", "R,0X1", "O,1X0", "P,0X6"])
def test_other_nonpositive_apertures_still_fail(definition):
    with pytest.raises(GerberError, match="positiva"):
        GerberParser().parse(HEADER + f"%ADD10{definition}*%M02*")


def test_excellon_header_is_recognized():
    layer = GerberParser().parse("M48\nMETRIC\n%\nG90\nM30\n", "NexCLP-PTH.drl")
    assert layer.file_format == "excellon" and not layer.objects


def test_report_link_and_batch_icons(editor, monkeypatch):
    urls = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: urls.append(url.toString()) or True
    )
    editor.chrome.actions["help.report_problem"].trigger()
    assert urls == [REPORT_PROBLEM_URL]
    toolbar_actions = [a for bar in editor.findChildren(QToolBar) for a in bar.actions()]
    for action in [editor.save_all_action, editor.close_all_action]:
        assert action in toolbar_actions and not action.icon().isNull()
    assert REPORT_PROBLEM_URL in help_html(editor)
    editor.set_language("en")
    assert editor.save_all_action.text() == "Save all files"
    assert "Report problems" in help_html(editor)


def test_batch_declined_writes_nothing(editor, tmp_path, monkeypatch):
    layers = [dirty_layer(editor, tmp_path / f"{i}.gbr") for i in range(2)]
    before = [layer.path.read_bytes() for layer in layers]
    monkeypatch.setattr(editor, "_confirm_save_all", lambda requests: False)
    assert not editor.save_all()
    assert [layer.path.read_bytes() for layer in layers] == before
    assert all(layer.modified for layer in layers)
    assert not editor.busy.operations and not editor.save_progress.active


def test_batch_validates_files_and_counts_only_success(editor, tmp_path, monkeypatch):
    layers = [dirty_layer(editor, tmp_path / f"{i}.gbr") for i in range(3)]
    expected = [len(layer.objects) for layer in layers]
    confirmed, values = [], []
    monkeypatch.setattr(editor, "_confirm_save_all", lambda req: confirmed.append(req) or True)
    editor.save_progress.valueChanged.connect(values.append)
    assert editor.save_all()
    assert editor.save_progress.maximum() == 3 and editor.save_progress.value() == 0
    assert not editor.close_all() and not editor.save_all()
    wait_until(lambda: not editor._save_all_running)
    assert len(confirmed) == 1 and all(r.overwrite for r in confirmed[0])
    assert values == [0, 1, 2, 3]
    assert [len(GerberParser().parse_file(layer.path).objects) for layer in layers] == expected
    assert all(not layer.modified for layer in layers) and not editor.busy.operations
    # Unchanged files require no new confirmation or rewriting.
    monkeypatch.setattr(editor, "_confirm_save_all", lambda req: pytest.fail("unchanged batch"))
    assert editor.save_all()


def test_batch_failure_stops_and_keeps_remaining_dirty(editor, tmp_path, monkeypatch):
    layers = [dirty_layer(editor, tmp_path / f"{i}.gbr") for i in range(3)]
    before = [layer.path.read_bytes() for layer in layers]
    save = GerberWriter.save

    def fail_second(writer, layer, target, mode, **kw):
        if target == layers[1].path:
            raise SaveError("simulated failure")
        return save(writer, layer, target, mode, **kw)

    monkeypatch.setattr(GerberWriter, "save", fail_second)
    monkeypatch.setattr(editor, "_confirm_save_all", lambda requests: True)
    errors = []
    monkeypatch.setattr(editor, "show_error", lambda title, message: errors.append(message))
    assert editor.save_all()
    wait_until(lambda: not editor._save_all_running)
    assert editor.save_progress.value() == 1 and editor.save_progress.maximum() == 3
    assert not layers[0].modified and all(layer.modified for layer in layers[1:])
    assert [layer.path.read_bytes() for layer in layers[1:]] == before[1:]
    assert len(errors) == 1 and "1 de 3" in errors[0] and "simulated failure" in errors[0]


def test_new_destination_cancel_and_duplicate_abort_before_writing(editor, tmp_path, monkeypatch):
    existing = dirty_layer(editor, tmp_path / "existing.gbr")
    new = GerberLayer("new.gbr", objects=[region(CUTIN)])
    editor.add_layer(new)
    before = existing.path.read_bytes()
    monkeypatch.setattr(editor, "_choose_save_destination", lambda *a, **kw: None)
    assert not editor.save_all() and existing.path.read_bytes() == before
    monkeypatch.setattr(
        editor, "_choose_save_destination", lambda *a, **kw: (existing.path, SaveMode.NORMALIZED)
    )
    errors = []
    monkeypatch.setattr(editor, "show_error", lambda title, message: errors.append(message))
    assert not editor.save_all() and "mesmo destino" in errors[0]
    assert existing.path.read_bytes() == before and new.path is None


def test_new_layer_gets_destination_after_worker_success(editor, tmp_path, monkeypatch):
    layer = GerberLayer("new.gbr", objects=[region(CUTIN)])
    editor.add_layer(layer)
    target = tmp_path / "new_saved.gbr"
    monkeypatch.setattr(
        editor, "_choose_save_destination", lambda *a, **kw: (target, SaveMode.NORMALIZED)
    )
    monkeypatch.setattr(editor, "_confirm_save_all", lambda requests: True)
    assert editor.save_all() and layer.path is None
    wait_until(lambda: not editor._save_all_running)
    assert layer.path == target and not layer.modified
    assert object_geometry(GerberParser().parse_file(target).objects[0]).area == 96


def test_warning_has_cancel_default_and_destinations(editor, tmp_path, monkeypatch):
    dirty_layer(editor, tmp_path / "original.gbr")
    seen = []

    def decline(dialog):
        seen.append((dialog.text(), dialog.informativeText(), dialog.detailedText()))
        assert dialog.defaultButton().text() == editor.t("Cancelar")
        return 0

    monkeypatch.setattr(QMessageBox, "exec", decline)
    assert not editor.save_all()
    assert "pode demorar" in seen[0][0] and "originais" in seen[0][1]
    assert str(tmp_path / "original.gbr") in seen[0][2]


def test_save_worker_keeps_event_loop_responsive(editor, tmp_path, monkeypatch):
    dirty_layer(editor, tmp_path / "large.gbr")
    entered, release = Event(), Event()
    save = GerberWriter.save

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return save(*args, **kwargs)

    monkeypatch.setattr(GerberWriter, "save", delayed)
    monkeypatch.setattr(editor, "_confirm_save_all", lambda req: True)
    assert editor.save_all()
    try:
        wait_until(entered.is_set)
        pulses = []
        QTimer.singleShot(0, lambda: pulses.append(True))
        wait_until(lambda: bool(pulses))
        assert editor._save_all_running and editor.save_progress.value() == 0
        assert not editor.close()
    finally:
        release.set()
    wait_until(lambda: not editor._save_all_running)


def test_import_progress_includes_errors_and_appended_paths(editor, tmp_path, monkeypatch):
    valid = tmp_path / "good.gbr"
    valid.write_bytes(FIXTURE.read_bytes())
    invalid = tmp_path / "bad.gbr"
    invalid.write_text("invalid input")
    values, errors = [], []
    editor.import_progress.valueChanged.connect(values.append)
    monkeypatch.setattr(editor, "show_error", lambda *args: errors.append(args))
    editor.open_paths_async([valid, invalid])
    editor.open_paths_async([valid])
    assert editor.import_progress.maximum() == 3
    wait_until(lambda: not editor._import_jobs and not editor.import_progress.active)
    assert values == [0, 1, 2, 3] and len(editor.layers) == 2 and len(errors) == 1
