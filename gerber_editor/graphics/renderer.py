"""Cached Qt paths and ordered layer composition."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainterPath

from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.geometry.tiling import MIN_TILED_OBJECTS, TiledComposition
from gerber_editor.graphics.tiled_items import RenderedTile


def painter_path(geometry) -> QPainterPath:
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    if geometry.is_empty:
        return path
    if geometry.geom_type == "Polygon":
        for ring in [geometry.exterior, *geometry.interiors]:
            coordinates = list(ring.coords)
            path.moveTo(*coordinates[0])
            for coordinate in coordinates[1:]:
                path.lineTo(*coordinate)
            path.closeSubpath()
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            path.addPath(painter_path(part))
    return path


class LayerRenderer:
    def __init__(self):
        self._objects = {}
        self._layers = {}
        self._compositions = {}
        self._flat_geometries = {}
        self._tile_paths = {}
        self.processing_pulse = None

    def adopt(self, prepared: LayerRenderer):
        """Transfer a completed worker's immutable paths into the GUI cache."""
        for layer_id in prepared._layers:
            self._compositions.pop(layer_id, None)
            self._flat_geometries.pop(layer_id, None)
            self._tile_paths.pop(layer_id, None)
        self._objects.update(prepared._objects)
        self._layers.update(prepared._layers)
        self._compositions.update(prepared._compositions)
        self._flat_geometries.update(prepared._flat_geometries)
        self._tile_paths.update(prepared._tile_paths)

    def paths(self, layer):
        signature = layer.signature()
        cached = self._layers.get(layer.id)
        if cached and cached[0] == signature:
            return cached[1], cached[2]
        geometries = {}
        paths = {}
        for index, obj in enumerate(layer.objects):
            if index % 64 == 0 and self.processing_pulse:
                self.processing_pulse()
            record = self._objects.get(obj.id)
            if record is None or record[0] != obj:
                geom = object_geometry(obj)
                record = (obj, geom, painter_path(geom))
                self._objects[obj.id] = record
            geometries[obj.id], paths[obj.id] = record[1], record[2]
        if len(layer.objects) >= MIN_TILED_OBJECTS:
            composition = TiledComposition(
                layer.objects, geometries, self._compositions.get(layer.id), self.processing_pulse
            )
            previous_tiles = self._tile_paths.get(layer.id, {})
            tiles = {}
            composite = QPainterPath()
            composite.setFillRule(Qt.FillRule.OddEvenFill)
            for key, tile in composition.tiles.items():
                previous = previous_tiles.get(key)
                if previous is not None and previous.geometry is tile:
                    rendered = previous
                else:
                    left, bottom, right, top = composition.cell_bounds(key)
                    rendered = RenderedTile(
                        QRectF(left, bottom, right - left, top - bottom),
                        tile,
                        painter_path(tile.geometry),
                        painter_path(tile.paint_geometry),
                    )
                tiles[key] = rendered
                composite.addPath(rendered.path)
            self._compositions[layer.id] = composition
            self._flat_geometries.pop(layer.id, None)
            self._tile_paths[layer.id] = tiles
        else:
            geometry = compose_layer(layer.objects, geometries)
            composite = painter_path(geometry)
            self._flat_geometries[layer.id] = geometry
            self._compositions.pop(layer.id, None)
            self._tile_paths.pop(layer.id, None)
        self._layers[layer.id] = (signature, composite, paths)
        return composite, paths

    def tile_paths(self, layer):
        return self._tile_paths.get(layer.id)

    def geometry_snapshot(self, layers):
        """Share immutable GEOS data with workers, without any Qt paint objects."""
        result = {}
        for layer in layers:
            cached = self._layers.get(layer.id)
            if cached is None or cached[0] != layer.signature():
                continue
            composition = self._compositions.get(layer.id)
            geometry = (
                tuple(tile.geometry for tile in composition.tiles.values())
                if composition is not None
                else self._flat_geometries.get(layer.id)
            )
            if geometry is not None:
                result[layer.id] = cached[0], geometry
        return result

    def prune(self, layers):
        ids = {obj.id for layer in layers for obj in layer.objects}
        self._objects = {key: value for key, value in self._objects.items() if key in ids}
        layer_ids = {layer.id for layer in layers}
        self._layers = {key: value for key, value in self._layers.items() if key in layer_ids}
        self._compositions = {
            key: value for key, value in self._compositions.items() if key in layer_ids
        }
        self._flat_geometries = {
            key: value for key, value in self._flat_geometries.items() if key in layer_ids
        }
        self._tile_paths = {
            key: value for key, value in self._tile_paths.items() if key in layer_ids
        }
