"""Ordered dark/clear composition with reusable, independently editable cells."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import GeometryCollection, box

from gerber_editor.geometry.boolean import compose_layer

MIN_TILED_OBJECTS = 512
DEFAULT_TILE_MM = 16.0
MAX_TILE_COUNT = 1024


@dataclass(frozen=True)
class ComposedTile:
    geometry: object
    paint_geometry: object


class TiledComposition:
    """Immutable geometry snapshot; an update constructs a new spatial index.

    Cells retain Gerber object order and are clipped before composition.
    Unchanged cells share their immutable GEOS result with the old snapshot.
    """

    def __init__(self, objects, geometries, previous=None, processing_pulse=None):
        self.objects = tuple(obj for obj in objects if obj.visible)
        self.geometries = np.asarray([geometries[obj.id] for obj in self.objects], dtype=object)
        nonempty = ~shapely.is_empty(self.geometries)
        if not np.all(nonempty):
            self.objects = tuple(
                obj for obj, keep in zip(self.objects, nonempty, strict=True) if keep
            )
            self.geometries = self.geometries[nonempty]
        self.tree = STRtree(self.geometries)
        self.object_bounds = shapely.bounds(self.geometries)
        self.bounds = tuple(shapely.total_bounds(self.geometries)) if self.objects else (0, 0, 0, 0)
        self.tile_size = DEFAULT_TILE_MM
        if self.objects:
            while self._cell_count() > MAX_TILE_COUNT:
                self.tile_size *= 2
            keys = set(self.keys_for_bounds(self.bounds))
        else:
            keys = set()
        self.tiles = {}
        compatible = previous is not None and previous.tile_size == self.tile_size
        dirty = keys
        if compatible:
            dirty = self._dirty_keys(previous, keys)
        self.changed_keys = frozenset(dirty | (previous.tiles.keys() - keys if previous else set()))
        for index, key in enumerate(sorted(keys)):
            if processing_pulse and index % 4 == 0:
                processing_pulse()
            if compatible and key not in dirty and key in previous.tiles:
                self.tiles[key] = previous.tiles[key]
            else:
                self.tiles[key] = self._compose(key)

    def _cell_count(self):
        left, bottom, right, top = self.bounds
        return (math.floor(right / self.tile_size) - math.floor(left / self.tile_size) + 1) * (
            math.floor(top / self.tile_size) - math.floor(bottom / self.tile_size) + 1
        )

    def keys_for_bounds(self, bounds):
        left, bottom, right, top = bounds
        size = self.tile_size
        for x in range(math.floor(left / size), math.floor(right / size) + 1):
            for y in range(math.floor(bottom / size), math.floor(top / size) + 1):
                yield x, y

    def cell_bounds(self, key):
        x, y = key
        size = self.tile_size
        return x * size, y * size, (x + 1) * size, (y + 1) * size

    def padded_bounds(self, bounds):
        left, bottom, right, top = bounds
        bleed = self.tile_size / 16
        return left - bleed, bottom - bleed, right + bleed, top + bleed

    def _dirty_keys(self, previous, keys):
        old = {
            obj.id: (obj, bounds)
            for obj, bounds in zip(previous.objects, previous.object_bounds, strict=True)
        }
        new = {
            obj.id: (obj, bounds)
            for obj, bounds in zip(self.objects, self.object_bounds, strict=True)
        }
        # Inserting/deleting objects shifts positions but does not reorder the
        # surviving objects. A real reorder may change any subsequent polarity.
        if [obj.id for obj in previous.objects if obj.id in new] != [
            obj.id for obj in self.objects if obj.id in old
        ]:
            return keys
        changed = old.keys() ^ new.keys()
        changed |= {
            object_id
            for object_id in old.keys() & new.keys()
            if old[object_id][0] != new[object_id][0]
        }
        dirty = keys - previous.tiles.keys()
        for object_id in changed:
            for snapshot in (old, new):
                if object_id in snapshot:
                    dirty.update(
                        key
                        for key in self.keys_for_bounds(self.padded_bounds(snapshot[object_id][1]))
                        if key in keys
                    )
        return dirty

    def _compose(self, key):
        core_bounds = self.cell_bounds(key)
        bounds = self.padded_bounds(core_bounds)
        cell = box(*bounds)
        indices = np.sort(self.tree.query(cell))
        if not indices.size:
            return ComposedTile(GeometryCollection(), GeometryCollection())
        shapes = self.geometries[indices].copy()
        object_bounds = self.object_bounds[indices]
        crosses = (
            (object_bounds[:, 0] < bounds[0])
            | (object_bounds[:, 1] < bounds[1])
            | (object_bounds[:, 2] > bounds[2])
            | (object_bounds[:, 3] > bounds[3])
        )
        if np.any(crosses):
            shapes[crosses] = shapely.intersection(shapes[crosses], cell)
        objects = [self.objects[index] for index in indices]
        painted = compose_layer(
            objects, {obj.id: shape for obj, shape in zip(objects, shapes, strict=True)}
        )
        return ComposedTile(painted.intersection(box(*core_bounds)), painted)
