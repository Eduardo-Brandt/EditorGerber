"""Placement uses the visible corner, independently of copy location or reflection."""

from decimal import Decimal as D

import pytest
from PySide6.QtCore import QByteArray, QMimeData, QPointF, Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog
from shapely import affinity
from shapely.ops import unary_union

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.core.objects import Aperture, GerberObject
from gerber_editor.core.primitives import Flash, Line, Point
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.tools.clipboard import MIME_TYPE, encode
from gerber_editor.tools.shapes import rectangle_region


@pytest.fixture
def drawing(qapp, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(window, "show_error", lambda title, error: pytest.fail(f"{title}: {error}"))
    layer = GerberLayer("placement.gbr", function="F.Silk")
    layer.objects = [
        GerberObject(
            rectangle_region(Point.of(-12, -7), Point.of(-4, -3)), None, group_id="source"
        ),
        GerberObject(rectangle_region(Point.of(-8, -3), Point.of(-4, 2)), None, group_id="source"),
    ]
    layer.saved_signature = layer.signature()
    window.add_layer(layer)
    window.show()
    window.canvas.snap_grid = window.canvas.snap_points = False
    window.canvas.select_all()
    qapp.processEvents()
    yield window, layer
    window.canvas.set_mode("select")
    for current in window.layers:
        current.saved_signature = current.signature()
    QApplication.clipboard().clear()
    window.close()


def bounds(objects):
    return unary_union([object_geometry(obj) for obj in objects]).bounds


def check_preview(window, point):
    window.canvas._cursor = QPointF(float(point.x), float(point.y))
    anchor = window.canvas._placement_anchor
    rect = None
    for path in window.canvas.placement_paths:
        rect = path.boundingRect() if rect is None else rect.united(path.boundingRect())
    assert rect.left() + float(point.x - anchor.x) == pytest.approx(float(point.x), abs=1e-6)
    assert rect.top() + float(point.y - anchor.y) == pytest.approx(float(point.y), abs=1e-6)


@pytest.mark.parametrize("operation", ["paste", "duplicate", "cut", "move"])
def test_corner_follows_cursor_and_commit_matches_preview(drawing, operation):
    window, layer = drawing
    originals = list(layer.objects)
    history = window.history._index
    window.canvas._cursor = QPointF(145, -82)
    if operation == "move":
        window.start_move()
    elif operation == "duplicate":
        window.start_duplicate()
    else:
        (window.cut_clipboard if operation == "cut" else window.copy_clipboard)()
        window.canvas._cursor = QPointF(-250, 70)
        window.paste_clipboard()
    assert window.canvas._placement_anchor == Point.of(-12, -7)
    assert window.history._index == history + (operation == "cut")
    point = Point.of(25, 18)
    check_preview(window, point)
    window._commit_placement(point)
    placed = layer.objects if operation in ("move", "cut") else layer.objects[len(originals) :]
    assert bounds(placed)[:2] == pytest.approx((25, 18), abs=1e-6)
    assert (bounds(placed)[2] - 25, bounds(placed)[3] - 18) == pytest.approx((8, 9))
    if operation in ("paste", "duplicate"):
        assert layer.objects[: len(originals)] == originals
        assert placed[0].group_id != originals[0].group_id
    window.undo_edit()
    if operation == "cut":
        window.undo_edit()
    assert layer.objects == originals


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_mirrored_envelope_is_reanchored_after_reflection(drawing, monkeypatch, axis):
    window, layer = drawing
    before = list(layer.objects)
    window.canvas._cursor = QPointF(187, -214)
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: (args[3][axis], True))
    window.mirror_copy()
    point = Point.of(40, 30)
    check_preview(window, point)
    window._commit_placement(point)
    placed = layer.objects[len(before) :]
    expected = affinity.scale(
        unary_union([object_geometry(o) for o in before]),
        xfact=-1 if axis in (0, 2) else 1,
        yfact=-1 if axis in (1, 2) else 1,
        origin=(0, 0),
    )
    x, y, *_ = expected.bounds
    expected = affinity.translate(expected, 40 - x, 30 - y)
    assert (
        unary_union([object_geometry(o) for o in placed]).symmetric_difference(expected).area < 1e-6
    )
    assert bounds(placed)[:2] == pytest.approx((40, 30))
    assert layer.objects[: len(before)] == before
    window.writer.serialize(layer)


@pytest.mark.parametrize(
    "obj",
    [
        GerberObject(Line(Point.of(-20, -15), Point.of(-8, -15)), Aperture(10, "C", (D("0.6"),))),
        GerberObject(
            Flash(Point.of(-10, 8)),
            Aperture(
                10,
                "MACRO",
                (),
                (),
                (MacroPrimitive(20, (D(1), D(2), D(4), D(0), D(12), D(0), D(0))),),
            ),
        ),
    ],
)
def test_corner_includes_real_stroke_and_macro_extents(drawing, obj):
    window, layer = drawing
    layer.objects = [obj]
    window.refresh()
    window.canvas.select_all()
    window.start_duplicate()
    left, bottom, *_ = object_geometry(obj).bounds
    assert float(window.canvas._placement_anchor.x) == pytest.approx(left)
    assert float(window.canvas._placement_anchor.y) == pytest.approx(bottom)
    point = Point.of(11, 13)
    check_preview(window, point)
    window._commit_placement(point)
    assert bounds(layer.objects[1:])[:2] == pytest.approx((11, 13), abs=1e-6)


def test_legacy_clipboard_anchor_is_not_reused(drawing):
    window, layer = drawing
    mime = QMimeData()
    mime.setData(MIME_TYPE, QByteArray(encode(layer.objects, Point.of(950, -700))))
    QApplication.clipboard().setMimeData(mime)
    window.paste_clipboard()
    assert window.canvas._placement_anchor == Point.of(-12, -7)
    check_preview(window, Point.of(20, 15))


def test_drag_keeps_grab_point_and_cancel_keeps_history(drawing):
    window, layer = drawing
    original = list(layer.objects)
    history = window.history._index
    grab = Point.of(-9, -5)
    window.start_move(anchor=grab)
    assert window.canvas._placement_anchor == grab
    assert window.canvas.snap_excluded == frozenset(o.id for o in original)
    window._commit_placement(Point.of(-5, -2))
    assert layer.objects[0].geometry == rectangle_region(Point.of(-8, -4), Point.of(0, 0))
    window.undo_edit()
    assert layer.objects == original
    window.canvas.select_all()
    window.start_duplicate()
    QTest.keyClick(window.canvas, Qt.Key.Key_Escape)
    assert layer.objects == original and window.history._index == history
    assert window._pending_edit is None and not window.canvas.placement_paths


def test_snap_places_corner_on_grid(drawing):
    window, layer = drawing
    window.canvas.snap_grid = True
    window.canvas.grid_mm = D(2)
    window.start_duplicate()
    window.canvas._cursor = QPointF(25.4, 17.3)
    point = window.canvas.snap(window.canvas._cursor)
    assert point == Point.of(26, 18)
    check_preview(window, point)
    window._commit_placement(point)
    assert bounds(layer.objects[2:])[:2] == pytest.approx((26, 18))


def test_begin_placement_reads_current_mouse_position_without_waiting_for_move(
    drawing, monkeypatch
):
    window, _ = drawing
    assert window.copy_clipboard()
    viewport = window.canvas.viewport()
    pixel = viewport.rect().center()
    monkeypatch.setattr(QCursor, "pos", lambda: viewport.mapToGlobal(pixel))
    window.canvas._cursor = QPointF(900, -800)
    window.paste_clipboard()
    assert window.canvas._cursor == window.canvas.mapToScene(pixel)
    check_preview(window, window.canvas.snap(window.canvas._cursor))
