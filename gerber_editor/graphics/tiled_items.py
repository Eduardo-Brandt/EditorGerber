"""Viewport-aware painting of composed cells without changing curve detail."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem


@dataclass(frozen=True)
class RenderedTile:
    bounds: QRectF
    geometry: object
    path: QPainterPath
    paint_path: QPainterPath


class TiledLayerItem(QGraphicsPathItem):
    """Keep the exact path API while painting only exposed cells."""

    def __init__(self, path, tiles=None):
        super().__init__(path)
        self.tiles = tiles
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption)

    def set_geometry(self, path, tiles):
        self.tiles = tiles
        self.setPath(path)
        self.update()

    def shape(self):
        # Display layers never participate in selection or snap queries.
        # Only ObjectItem owns a hit shape; constructing/testing this large
        # composed outline on every mouse move is unnecessary.
        return QPainterPath()

    def paint(self, painter, option, widget=None):
        if self.tiles is None:
            super().paint(painter, option, widget)
            return
        transform = painter.deviceTransform()
        scale = hypot(transform.m11(), transform.m12())
        if self.tiles and scale * next(iter(self.tiles.values())).bounds.width() / 16 < 1:
            # At extreme zoom-out a cell's bleed is smaller than one pixel.
            # Fill the complete path so antialias coverage cannot be clipped.
            super().paint(painter, option, widget)
            return
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        for tile in self.tiles.values():
            if not tile.bounds.intersects(option.exposedRect):
                continue
            # The geometry extends beyond the cell. A hard clip partitions
            # device pixels without antialiasing artificial cell boundaries.
            painter.save()
            painter.setClipRect(tile.bounds, Qt.ClipOperation.IntersectClip)
            painter.drawPath(tile.paint_path)
            painter.restore()
