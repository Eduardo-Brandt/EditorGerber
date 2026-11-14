"""Spatial composition must retain Gerber polarity and exact document edits."""

from dataclasses import replace
from decimal import Decimal as D

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen, QPixmapCache
from PySide6.QtWidgets import QGraphicsItem
from shapely import union_all
from shapely.geometry import GeometryCollection

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Flash, Point
from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.geometry.tiling import TiledComposition
from gerber_editor.graphics.canvas import Canvas
from gerber_editor.graphics.renderer import painter_path
from gerber_editor.graphics.tiled_items import RenderedTile, TiledLayerItem
from gerber_editor.tools.shapes import rectangle_region


def objects():
    result = [GerberObject(rectangle_region(Point.of(-40, -20), Point.of(100, 80)), None)]
    random = np.random.default_rng(17)
    for index in range(30):
        x, y = random.uniform(-35, 90), random.uniform(-15, 65)
        result.append(
            GerberObject(
                Flash(Point.of(str(x), str(y))),
                Aperture(index + 10, "C", (D(12),)),
                Polarity.CLEAR if index % 3 else Polarity.DARK,
            )
        )
    return result


def compose(objects, previous=None):
    return TiledComposition(objects, {obj.id: object_geometry(obj) for obj in objects}, previous)


def assert_equivalent(objects, composition):
    expected = compose_layer(objects, {obj.id: object_geometry(obj) for obj in objects})
    actual = union_all([tile.geometry for tile in composition.tiles.values()])
    assert actual.symmetric_difference(expected).area < 1e-8


def test_tiled_polarity_matches_whole_layer_across_borders():
    values = objects()
    tiled = compose(values)
    assert len(tiled.tiles) > 6
    assert_equivalent(values, tiled)
    # Clear before any dark must not affect a later dark object.
    values.insert(0, replace(values[-1], polarity=Polarity.CLEAR, id="first-clear"))
    assert_equivalent(values, compose(values))


def test_empty_macro_geometry_and_hidden_layers_have_no_cells():
    values = objects()[:1]
    result = TiledComposition(values, {values[0].id: GeometryCollection()})
    assert not result.tiles
    assert not compose([replace(values[0], visible=False)]).tiles


def test_incremental_move_delete_undo_visibility_and_order():
    original = objects()
    previous = compose(original)
    moved = list(original)
    moved[1] = replace(moved[1], geometry=Flash(Point.of(30, 30)))
    changed = compose(moved, previous)
    assert len(changed.changed_keys) < len(changed.tiles)
    assert any(changed.tiles[key] is previous.tiles[key] for key in changed.tiles)
    assert_equivalent(moved, changed)
    for values in (
        moved[:-1],
        original,
        [replace(original[0], visible=False), *original[1:]],
        list(reversed(original)),
    ):
        changed = compose(values, changed)
        assert_equivalent(values, changed)
    empty = compose([], changed)
    assert not empty.tiles
    assert_equivalent(original, compose(original, empty))


@pytest.mark.parametrize("scale,opacity", [(3.7, 1), (5.333, 0.4), (31.5, 1), (0.7, 1), (0.02, 1)])
def test_cell_clip_does_not_draw_antialias_seams(qapp, scale, opacity):
    values = objects()
    composition = compose(values)
    full = painter_path(compose_layer(values, {obj.id: object_geometry(obj) for obj in values}))
    tiles = {}
    for key, tile in composition.tiles.items():
        left, bottom, right, top = composition.cell_bounds(key)
        tiles[key] = RenderedTile(
            QRectF(left, bottom, right - left, top - bottom),
            tile,
            painter_path(tile.geometry),
            painter_path(tile.paint_geometry),
        )
    canvas = Canvas()
    canvas.resize(801, 603)
    canvas.setBackgroundBrush(QColor("#15413d"))
    canvas.axes_visible = False
    canvas.setTransform(canvas.transform().fromScale(scale, -scale))
    canvas.centerOn(32.123, 32.444)
    display = TiledLayerItem(full)
    display.setPen(QPen(Qt.PenStyle.NoPen))
    display.setBrush(QColor("#df6565"))
    display.setOpacity(opacity)
    canvas.scene().addItem(display)
    canvas.show()
    qapp.processEvents()
    reference = canvas.viewport().grab().toImage()
    display.set_geometry(full, tiles)
    actual = canvas.viewport().grab().toImage()
    a = np.frombuffer(reference.constBits(), dtype=np.uint8).astype(int)
    b = np.frombuffer(actual.constBits(), dtype=np.uint8).astype(int)
    error = np.abs(a - b)
    assert error.max() <= 4
    assert error.mean() < 0.005
    if opacity == 1:
        display.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        cached = canvas.viewport().grab().toImage()
        assert cached == actual
    canvas.close()


def test_large_layer_updates_only_local_tiles_and_preserves_selection(qapp):
    aperture = Aperture(10, "C", (D("0.4"),))
    values = [
        GerberObject(Flash(Point.of(x * 2, y * 2)), aperture) for x in range(40) for y in range(20)
    ]
    layer = GerberLayer("large.gbr", objects=values)
    canvas = Canvas()
    canvas.rebuild([layer])
    assert canvas.display_items[layer.id].shape().isEmpty()
    assert not canvas.object_items[values[0].id].shape().isEmpty()
    before = dict(canvas.renderer._tile_paths[layer.id])
    first = canvas.object_items[values[0].id]
    first.setSelected(True)
    layer.objects[0] = replace(values[0], geometry=Flash(Point.of(2, 2)))
    canvas.rebuild([layer])
    after = canvas.renderer._tile_paths[layer.id]
    assert first.isSelected() and canvas.object_items[values[0].id] is first
    assert any(after[key] is before[key] for key in before)
    assert len(canvas.renderer._compositions[layer.id].changed_keys) < len(after)
    canvas.rebuild([])
    assert not canvas.renderer._tile_paths and not canvas.renderer._compositions
    canvas.close()


def test_stationary_snap_reuses_query_and_edit_invalidates_it(qapp, monkeypatch):
    import gerber_editor.graphics.canvas as canvas_module

    layer = GerberLayer("snap.gbr", objects=objects())
    canvas = Canvas()
    canvas.rebuild([layer])
    original = canvas_module.resolve
    calls = []

    def resolve(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(canvas_module, "resolve", resolve)
    point = QPointF(20, 20)
    assert canvas.snap(point) == canvas.snap(point)
    assert len(calls) == 1
    canvas.rebuild([layer])
    canvas.snap(point)
    assert len(calls) == 2
    canvas.scale(2, 2)
    canvas.snap(point)
    assert len(calls) == 3
    canvas.close()


def test_pan_does_not_query_object_magnets(qapp, monkeypatch):
    canvas = Canvas()
    canvas.snap_grid = False
    canvas._pan = QPoint(10, 10)

    def unexpected(*args):
        pytest.fail("Pan queried object hit shapes")

    monkeypatch.setattr(canvas.scene(), "items", unexpected)
    canvas.snap(QPointF(5, 6))
    assert canvas.snap_target is None
    canvas.close()


def test_multiple_layers_fit_raster_cache_without_repainting(qapp):
    calls = []

    class Display(TiledLayerItem):
        def paint(self, *args):
            calls.append(1)
            super().paint(*args)

    canvas = Canvas()
    canvas.resize(1000, 800)
    assert QPixmapCache.cacheLimit() >= 64 * 1024
    path = QPainterPath()
    path.addRect(QRectF(-100, -100, 200, 200))
    displays = []
    for index in range(8):
        display = Display(path)
        display.setBrush(QColor("#bbaa66"))
        display.setPen(QPen(Qt.PenStyle.NoPen))
        display.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        display.setZValue(index)
        canvas.scene().addItem(display)
        displays.append(display)
    canvas.show()
    qapp.processEvents()
    canvas.viewport().grab()
    canvas.viewport().grab()
    calls.clear()
    canvas.viewport().grab()
    assert not calls
    canvas.close()
