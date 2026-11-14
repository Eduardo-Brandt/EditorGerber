"""Incremental rendering must preserve hit testing and fabrication geometry."""

import cProfile
import pstats
from dataclasses import replace
from decimal import Decimal as D

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsItem

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Flash, Line, Point
from gerber_editor.graphics.canvas import Canvas


@pytest.fixture
def drawing(qapp):
    aperture = Aperture(10, "C", (D(2),))
    objects = [
        GerberObject(Line(Point.of(0, 0), Point.of(20, 0)), aperture),
        GerberObject(Flash(Point.of(10, 0)), Aperture(11, "C", (D(1),)), Polarity.CLEAR),
        GerberObject(Flash(Point.of(10, 0)), Aperture(12, "C", (D("0.3"),))),
    ]
    layer = GerberLayer("polarity.gbr", objects=objects, color="#ff8866")
    canvas = Canvas()
    canvas.resize(800, 600)
    canvas.active_layer_id = layer.id
    canvas.axes_visible = False
    canvas.rebuild([layer])
    canvas.show()
    canvas.fit_all()
    qapp.processEvents()
    yield canvas, layer
    canvas.close()


def capture(canvas):
    return canvas.viewport().grab().toImage()


def test_unselected_objects_skip_paint_but_keep_hits_and_selection(drawing):
    canvas, layer = drawing
    before = capture(canvas)
    profile = cProfile.Profile()
    profile.runcall(capture, canvas)
    assert not any(
        key[0].endswith("graphics_items.py") and key[2] == "paint"
        for key in pstats.Stats(profile).stats
    )
    canvas.select_window(QRectF(-2, -2, 24, 4), crossing=False)
    assert {item.obj.id for item in canvas.selected_objects()} == {obj.id for obj in layer.objects}
    assert capture(canvas) != before
    assert all(
        not item.flags() & QGraphicsItem.GraphicsItemFlag.ItemHasNoContents
        for item in canvas.selected_objects()
    )
    canvas.clear_selection()
    assert capture(canvas) == before
    assert canvas.snap(QPointF(20.01, 0.01)) == Point.of(20, 0)


def test_appearance_retains_items_and_does_not_prepare_geometry(drawing, monkeypatch):
    canvas, layer = drawing
    items = dict(canvas.object_items)
    display = canvas.display_items[layer.id]
    original = layer.signature()
    selected = items[layer.objects[0].id]
    selected.setSelected(True)

    def unexpected(*args):
        pytest.fail("Appearance change attempted to rebuild geometry")

    monkeypatch.setattr(canvas.renderer, "paths", unexpected)
    for color, opacity, visible in (
        ("#aabbff", 0.4, True),
        ("#00ff00", 1, False),
        ("#00ff00", 1, True),
    ):
        layer.color, layer.opacity, layer.visible = color, opacity, visible
        canvas.rebuild([layer])
        assert canvas.display_items[layer.id] is display
        assert display.brush().color().name() == color
        assert display.opacity() == opacity
        assert display.isVisible() == visible
        assert canvas.object_items == items
        assert all(item.isVisible() == visible for item in items.values())
        assert layer.signature() == original
    canvas.select_all()
    assert len(canvas.selected_objects()) == len(original)


def test_edit_delete_undo_and_close_reuse_unaffected_items(drawing):
    canvas, layer = drawing
    before = capture(canvas)
    original = list(layer.objects)
    items = dict(canvas.object_items)
    first = items[original[0].id]
    first.setSelected(True)
    layer.objects[0] = replace(original[0], geometry=Line(Point.of(0, 5), Point.of(20, 5)))
    canvas.rebuild([layer])
    assert canvas.object_items == items
    assert first.isSelected()
    assert first.obj is layer.objects[0]
    assert first.path().boundingRect().center().y() == 5
    layer.objects.pop()
    canvas.rebuild([layer])
    assert original[-1].id not in canvas.object_items
    assert items[original[-1].id].scene() is None
    layer.objects[:] = original
    canvas.rebuild([layer])
    canvas.clear_selection()
    assert capture(canvas) == before
    assert canvas.object_items[original[1].id] is items[original[1].id]
    # Synchronization must also work when the caller mutates the same list.
    layers = [layer]
    canvas.rebuild(layers)
    layers.clear()
    canvas.rebuild(layers)
    assert not canvas.object_items and not canvas.display_items and not canvas.ghost_items
    assert not canvas.renderer._objects and not canvas.renderer._layers
    assert not canvas.scene().items()
    canvas.rebuild([layer])
    assert len(canvas.object_items) == len(original)


def test_replacing_layer_with_same_identity_updates_selection_owner(drawing):
    canvas, layer = drawing
    replacement = replace(layer, color="#123456")
    canvas.rebuild([replacement])
    canvas.select_all()
    assert all(item.layer is replacement for item in canvas.selected_objects())
    assert all(owner is replacement for _, owner in canvas.ghost_items)


@pytest.mark.parametrize("scale,opacity", [(0.2, 1), (1, 1), (6, 1), (6, 0.4)])
def test_cache_matches_direct_render_after_zoom_pan_and_ghosts(drawing, scale, opacity):
    canvas, layer = drawing
    canvas.scale(scale, scale)
    canvas.centerOn(9.5, 0.25)
    layer.opacity = opacity
    canvas.rebuild([layer])
    canvas.set_ghost_negatives(True)
    display = canvas.display_items[layer.id]
    if opacity < 1:
        assert display.cacheMode() == QGraphicsItem.CacheMode.NoCache
    cached = capture(canvas)
    display.setCacheMode(QGraphicsItem.CacheMode.NoCache)
    assert capture(canvas) == cached
    display.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
    canvas.set_ghost_negatives(False)
    assert capture(canvas) != cached
