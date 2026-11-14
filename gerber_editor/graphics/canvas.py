"""CAD canvas: world Y-up, selection, pan/zoom and two-click line placement."""

from __future__ import annotations

import math
from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmapCache
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from gerber_editor.core.objects import Polarity
from gerber_editor.core.primitives import Point
from gerber_editor.core.units import Unit
from gerber_editor.graphics.graphics_items import ObjectItem
from gerber_editor.graphics.overlays import draw_overlays
from gerber_editor.graphics.renderer import LayerRenderer
from gerber_editor.graphics.snapping import resolve
from gerber_editor.graphics.tiled_items import TiledLayerItem


class Canvas(QGraphicsView):
    coordinatesChanged = Signal(float, float)
    selectionUpdated = Signal()
    lineCreated = Signal(object, object)
    textRequested = Signal(object)
    zoomChanged = Signal(float)
    modeChanged = Signal(str)
    distanceMeasured = Signal(float, float, float)
    measurementChanged = Signal(float, float, float)
    shapeRequested = Signal(str, object, bool)
    operationPending = Signal(bool, str)
    placementCommitted = Signal(object)
    placementCancelled = Signal()
    dragStarted = Signal(object)
    pointPicked = Signal(object)
    editRequested = Signal()
    fiducialRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Several board layers each need a viewport-sized pixmap. Qt's small
        # default cache otherwise evicts one layer while drawing the next.
        # Storage is allocated on demand and remains bounded by Qt.
        if QPixmapCache.cacheLimit() < 64 * 1024:
            QPixmapCache.setCacheLimit(64 * 1024)
        self.setObjectName("gerberCanvas")
        self.setScene(QGraphicsScene(self))
        self.scene().setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.scene().selectionChanged.connect(self._selection_changed)
        self.renderer = LayerRenderer()
        self.layers = []
        self.active_layer_id = None
        self.active_only = True
        self.object_items = {}
        self.display_items = {}
        self.ghost_items = []
        self._hit_groups = {}
        self._layer_signatures = {}
        self._layer_owners = {}
        self._layer_presentation = {}
        self._layer_bounds = {}
        self._selection_groups = {}
        self._group_revisions = {}
        self._highlighted_ids = set()
        self.grid_mm = Decimal("0.635")
        self.grid_visible = False
        self.axes_visible = True
        self.snap_grid = True
        self.snap_points = True
        self.snap_target = None
        self.snap_excluded = frozenset()
        self._snap_cache = None
        self.ortho_angle = 45
        self.units = Unit.MM
        self.polar = False
        self.full_cursor = False
        self.ghost_negatives = False
        self.quantum_mm = Decimal("0.000001")
        self.arc_clockwise = False
        self._shift_held = False
        self.mode = "select"
        self._press = None
        self._pan = None
        self._rubber = None
        self._line_start = None
        self._shape_points = []
        self._measurement = None
        self._cursor = QPointF()
        self._placement_anchor = None
        self.placement_paths = []
        self._drag_active = False
        self._drag_candidate = False
        self._press_scene = None
        self.last_anchor = Point.of(0, 0)
        self.setMouseTracking(True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#000000"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.scale(12, -12)
        self.scene().setSceneRect(-100, -100, 200, 200)

    def _selection_changed(self):
        selected = {item.obj.id for item in self.selected_objects()}
        for object_id in selected ^ self._highlighted_ids:
            item = self.object_items.get(object_id)
            if item is not None:
                item.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemHasNoContents, object_id not in selected
                )
                item.update()
        self._highlighted_ids = selected
        self.viewport().update()
        self.selectionUpdated.emit()

    def set_mode(self, mode: str):
        if self.mode in ("placement", "pick_center"):
            self.placementCancelled.emit()
        self.mode = mode
        self._line_start = None
        self._shape_points = []
        self._measurement = None
        self._placement_anchor = None
        self.placement_paths = []
        self.snap_excluded = frozenset()
        self._drag_active = False
        self._drag_candidate = False
        self._press = self._rubber = None
        self.operationPending.emit(False, "")
        self.setCursor(
            Qt.CursorShape.ArrowCursor if mode == "select" else Qt.CursorShape.CrossCursor
        )
        self.viewport().update()
        self.modeChanged.emit(mode)

    def zoom_by(self, factor: float, anchor=None):
        target = abs(self.transform().m11()) * factor
        if 0.02 < target < 100000:
            anchor = anchor if anchor is not None else self.viewport().rect().center()
            before = self.mapToScene(anchor)
            self.scale(factor, factor)
            after = self.mapToScene(anchor)
            delta = after - before
            self.translate(delta.x(), delta.y())
            self.zoomChanged.emit(target)

    def set_ghost_negatives(self, visible):
        self.ghost_negatives = visible
        for item, layer in self.ghost_items:
            item.setVisible(visible and layer.visible)
        self.viewport().update()

    def rebuild(self, layers):
        """Synchronize scene contents, retaining unchanged items and raster caches."""
        self.layers = list(layers)
        self._snap_cache = None
        signals_blocked = self.scene().blockSignals(True)
        geometry_changed = False
        try:
            current_ids = {layer.id for layer in layers}
            for layer_id in self._layer_signatures.keys() - current_ids:
                geometry_changed = True
                for obj in self._layer_signatures.pop(layer_id):
                    self._remove_object_item(obj.id)
                self.scene().removeItem(self._hit_groups.pop(layer_id))
                self.scene().removeItem(self.display_items.pop(layer_id))
                self._layer_presentation.pop(layer_id)
                self._layer_owners.pop(layer_id)
                self._layer_bounds.pop(layer_id)
                self._selection_groups.pop(layer_id, None)
                self._group_revisions.pop(layer_id, None)
                self._remove_ghosts(layer_id)
            for layer in layers:
                signature = layer.signature()
                previous = self._layer_signatures.get(layer.id)
                if previous is None or previous != signature:
                    geometry_changed = True
                    self._sync_layer_geometry(layer, signature, previous)
                elif (
                    self._layer_owners[layer.id] is not layer
                    or self._group_revisions.get(layer.id) != layer.group_revision
                ):
                    self._sync_selection_groups(layer, signature)
                    self.ghost_items = [
                        (item, layer if owner.id == layer.id else owner)
                        for item, owner in self.ghost_items
                    ]
                self._layer_owners[layer.id] = layer
                presentation = (layer.color, layer.opacity, layer.visible)
                if self._layer_presentation.get(layer.id) != presentation:
                    display = self.display_items[layer.id]
                    display.setBrush(QColor(layer.color))
                    display.setOpacity(layer.opacity)
                    # Transparent pixmaps can round alpha differently from
                    # direct painting; retain exact layer blending in that case.
                    display.setCacheMode(
                        QGraphicsItem.CacheMode.DeviceCoordinateCache
                        if layer.opacity == 1.0
                        else QGraphicsItem.CacheMode.NoCache
                    )
                    display.setVisible(layer.visible)
                    self._hit_groups[layer.id].setVisible(layer.visible)
                    for ghost, owner in self.ghost_items:
                        if owner.id == layer.id:
                            ghost.setOpacity(layer.opacity)
                            ghost.setVisible(layer.visible and self.ghost_negatives)
                    self._layer_presentation[layer.id] = presentation
            self.set_active_layer(self.active_layer_id)
            if geometry_changed:
                self.renderer.prune(layers)
                bounds = QRectF()
                for rect in self._layer_bounds.values():
                    bounds = bounds.united(rect)
                if not bounds.isEmpty():
                    padding = max(bounds.width(), bounds.height(), 20) * 2
                    self.scene().setSceneRect(bounds.adjusted(-padding, -padding, padding, padding))
        finally:
            self.scene().blockSignals(signals_blocked)
        self._selection_changed()

    def _remove_object_item(self, object_id):
        item = self.object_items.pop(object_id)
        item.setParentItem(None)
        self.scene().removeItem(item)

    def _remove_ghosts(self, layer_id):
        retained = []
        for item, layer in self.ghost_items:
            if layer.id == layer_id:
                self.scene().removeItem(item)
            else:
                retained.append((item, layer))
        self.ghost_items = retained

    def _sync_layer_geometry(self, layer, signature, previous):
        composite, paths = self.renderer.paths(layer)
        tiles = self.renderer.tile_paths(layer)
        if previous is None:
            display = TiledLayerItem(composite, tiles)
            display.setPen(QPen(Qt.PenStyle.NoPen))
            display.setBrush(QColor(layer.color))
            self.scene().addItem(display)
            # Qt invalidates this cache on path/brush/scale changes and evicts
            # pixmaps through its shared, bounded QPixmapCache.
            display.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
            self.display_items[layer.id] = display
            group = QGraphicsRectItem()
            group.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)
            group.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene().addItem(group)
            self._hit_groups[layer.id] = group
        else:
            self.display_items[layer.id].set_geometry(composite, tiles)
            ids = {obj.id for obj in signature}
            for obj in previous:
                if obj.id not in ids:
                    self._remove_object_item(obj.id)
            self._remove_ghosts(layer.id)
        has_hidden_objects = False
        for index, obj in enumerate(signature):
            if index % 128 == 0 and getattr(self, "processing_pulse", None):
                self.processing_pulse()
            item = self.object_items.get(obj.id)
            if item is None:
                item = ObjectItem(obj, layer, paths[obj.id])
                item.setParentItem(self._hit_groups[layer.id])
                self.object_items[obj.id] = item
            else:
                if item.obj != obj:
                    item.setPath(paths[obj.id])
                    item.obj = obj
                item.layer = layer
            item.setVisible(obj.visible)
            has_hidden_objects = has_hidden_objects or not obj.visible
            if obj.polarity == Polarity.CLEAR and obj.visible:
                ghost = TiledLayerItem(paths[obj.id])
                ghost.setPen(QPen(Qt.PenStyle.NoPen))
                ghost.setBrush(QColor(155, 155, 155, 135))
                self.scene().addItem(ghost)
                ghost.setOpacity(layer.opacity)
                ghost.setVisible(layer.visible and self.ghost_negatives)
                self.ghost_items.append((ghost, layer))
        self._sync_selection_groups(layer, signature)
        bounds = self._hit_groups[layer.id].childrenBoundingRect()
        if has_hidden_objects:
            bounds = QRectF()
            for obj in signature:
                if obj.visible:
                    bounds = bounds.united(self.object_items[obj.id].sceneBoundingRect())
        self._layer_bounds[layer.id] = bounds
        self._layer_presentation.pop(layer.id, None)

    @staticmethod
    def _selection_key(obj):
        if obj.group_id:
            return "group", obj.group_id
        if obj.text_entity:
            return "text", obj.text_entity.group_id
        return None

    def _sync_selection_groups(self, layer, signature):
        groups = {}
        for obj in signature:
            item = self.object_items[obj.id]
            item.obj, item.layer = obj, layer
            key = self._selection_key(obj)
            if key is not None:
                groups.setdefault(key, []).append(item)
        self._selection_groups[layer.id] = groups
        self._group_revisions[layer.id] = layer.group_revision
        self._layer_signatures[layer.id] = signature

    def selection_members(self, item):
        key = self._selection_key(item.obj)
        return self._selection_groups.get(item.layer.id, {}).get(key, (item,))

    def set_active_layer(self, layer_id):
        self.active_layer_id = layer_id
        for order, layer in enumerate(self.layers):
            # Raise only the presentation; the manager's saved stack is unchanged.
            depth = len(self.layers) if layer.id == layer_id else order
            self.display_items[layer.id].setZValue(depth * 10)
            self._hit_groups[layer.id].setZValue(10000 + depth)
        for item, layer in self.ghost_items:
            item.setZValue(self.display_items[layer.id].zValue() + 1)
        self.viewport().update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.mode == "select":
            self._press = self._rubber = None
            self._drag_candidate = self._drag_active = False
            candidates = [
                item for item in self.items(event.position().toPoint()) if self.eligible(item)
            ]
            if candidates:
                self.clear_selection()
                self.select_object(candidates[0])
                self.editRequested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eligible(self, item):
        return (
            isinstance(item, ObjectItem)
            and item.isVisible()
            and (not self.active_only or item.layer.id == self.active_layer_id)
        )

    def selected_objects(self) -> list[ObjectItem]:
        return [item for item in self.scene().selectedItems() if isinstance(item, ObjectItem)]

    def clear_selection(self):
        self.scene().clearSelection()

    def select_all(self):
        self.scene().blockSignals(True)
        for item in self.object_items.values():
            item.setSelected(self.eligible(item))
        self.scene().blockSignals(False)
        self._selection_changed()

    def select_window(self, rect: QRectF, crossing: bool, additive: bool = False):
        self.scene().blockSignals(True)
        if not additive:
            self.clear_selection()
        mode = (
            Qt.ItemSelectionMode.IntersectsItemShape
            if crossing
            else Qt.ItemSelectionMode.ContainsItemShape
        )
        seen = set()
        for item in self.scene().items(rect, mode):
            if self.eligible(item):
                key = (item.layer.id, self._selection_key(item.obj) or item.obj.id)
                if key in seen:
                    continue
                seen.add(key)
                if (
                    not crossing
                    and item.obj.group_id
                    and any(
                        not rect.contains(member.sceneBoundingRect())
                        for member in self.selection_members(item)
                    )
                ):
                    continue
                self.select_object(item)
        self.scene().blockSignals(False)
        self._selection_changed()

    def fit_all(self):
        rect = QRectF()
        for layer in self.layers:
            if layer.visible:
                rect = rect.united(self._layer_bounds[layer.id])
        self._fit(rect)

    def fit_selection(self):
        rect = QRectF()
        for item in self.selected_objects():
            rect = rect.united(item.sceneBoundingRect())
        self._fit(rect)

    def _fit(self, rect):
        if rect.isEmpty():
            return
        self.resetTransform()
        self.scale(1, -1)
        margin = max(rect.width(), rect.height(), 1) * 0.06
        self.fitInView(
            rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.zoomChanged.emit(abs(self.transform().m11()))

    def constraint_anchor(self):
        if self._placement_anchor:
            return self._placement_anchor
        if self._line_start:
            return self._line_start
        if self._shape_points:
            return self._shape_points[-1] if self.mode == "dimension" else self._shape_points[0]
        return self.last_anchor

    def snap(self, point: QPointF, reference=None) -> Point:
        anchor = reference or self.constraint_anchor()
        key = (
            point.x(),
            point.y(),
            anchor,
            self.mode,
            self._shift_held,
            abs(self.transform().m11()),
            self.snap_grid,
            self.snap_points,
            self.grid_mm,
            self.quantum_mm,
            self.ortho_angle,
            self.snap_excluded,
            self._pan is not None,
        )
        if self._snap_cache is not None and self._snap_cache[0] == key:
            self.snap_target = self._snap_cache[2]
            return self._snap_cache[1]
        result = resolve(self, point, reference)
        self._snap_cache = key, result, self.snap_target
        return result

    def begin_placement(self, anchor, paths, excluded=()):
        self.set_mode("placement")
        self._placement_anchor = anchor
        self.placement_paths = paths
        self.snap_excluded = frozenset(excluded)
        self.operationPending.emit(True, "Clique para posicionar; Esc cancela")
        self.viewport().update()

    def select_object(self, item, selected=True):
        self.select_objects((item,), selected)

    def select_objects(self, items, selected=True):
        blocked = self.scene().blockSignals(True)
        try:
            seen = set()
            for item in items:
                key = (item.layer.id, self._selection_key(item.obj) or item.obj.id)
                if key in seen:
                    continue
                seen.add(key)
                for member in self.selection_members(item):
                    member.setSelected(selected)
        finally:
            self.scene().blockSignals(blocked)
        if not blocked:
            self._selection_changed()

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120
        factor = 1.2**steps
        self.zoom_by(factor, event.position().toPoint())
        event.accept()

    def mousePressEvent(self, event):
        position = event.position().toPoint()
        self._cursor = self.mapToScene(position)
        self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = position
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.set_mode("select")
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        point = self.snap(self.mapToScene(position))
        if self.mode == "pick_center":
            self.pointPicked.emit(point)
            return
        if self.mode == "placement":
            self.last_anchor = point
            self.placementCommitted.emit(point)
            return
        if self.mode in ("line", "measure"):
            if self._line_start is None:
                self._line_start = point
                self._measurement = None
                self.operationPending.emit(True, "Escolha o próximo ponto")
            else:
                first = self._line_start
                self._line_start = None
                self.operationPending.emit(False, "")
                if self.mode == "line":
                    self.lineCreated.emit(first, point)
                else:
                    self._measurement = (first, point)
                    dx, dy = (
                        float(point.x - first.x),
                        float(point.y - first.y),
                    )
                    self.distanceMeasured.emit(dx, dy, math.hypot(dx, dy))
            self.viewport().update()
            return
        if self.mode in ("arc", "circle", "rectangle", "square", "dimension"):
            self._shape_points.append(point)
            needed = 3 if self.mode in ("arc", "dimension") else 2
            if len(self._shape_points) == needed:
                points = self._shape_points
                self._shape_points = []
                self.operationPending.emit(False, "")
                self.shapeRequested.emit(self.mode, points, self.arc_clockwise)
            else:
                self.operationPending.emit(True, "Escolha o próximo ponto")
            self.viewport().update()
            return
        if self.mode in ("text", "fiducial"):
            (self.textRequested if self.mode == "text" else self.fiducialRequested).emit(point)
            return
        self._press = position
        self._press_scene = point
        candidates = [i for i in self.items(position) if self.eligible(i)]
        control = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._drag_candidate = bool(candidates and not control)
        if candidates and not control and not candidates[0].isSelected():
            self.clear_selection()
            self.select_object(candidates[0])
        self._rubber = None
        event.accept()

    def mouseMoveEvent(self, event):
        self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        position = event.position().toPoint()
        self._cursor = self.mapToScene(position)
        self.coordinatesChanged.emit(self._cursor.x(), self._cursor.y())
        if self.mode == "measure" and self._line_start:
            endpoint = self.snap(self._cursor)
            dx, dy = float(endpoint.x - self._line_start.x), float(endpoint.y - self._line_start.y)
            self.measurementChanged.emit(dx, dy, math.hypot(dx, dy))
        if self._pan is not None:
            delta = position - self._pan
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan = position
        elif self._press is not None and (position - self._press).manhattanLength() > 4:
            if self._drag_candidate:
                self.dragStarted.emit(self._press_scene)
                self._drag_active = self.mode == "placement"
            else:
                self._rubber = position
        self.viewport().update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            point = self.snap(self.mapToScene(event.position().toPoint()))
            self.last_anchor = point
            self.placementCommitted.emit(point)
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            self.setCursor(
                Qt.CursorShape.ArrowCursor if self.mode == "select" else Qt.CursorShape.CrossCursor
            )
            return
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        end = event.position().toPoint()
        additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if self._rubber is not None:
            rect = QRectF(self.mapToScene(self._press), self.mapToScene(end)).normalized()
            self.select_window(rect, crossing=end.x() < self._press.x(), additive=additive)
        else:
            candidates = [i for i in self.items(end) if self.eligible(i)]
            if candidates:
                item = candidates[0]
                if not additive and not item.isSelected():
                    self.clear_selection()
                self.select_object(item, not item.isSelected() if additive else True)
            elif not additive:
                self.clear_selection()
        self._press, self._rubber = None, None
        self._drag_candidate = False
        self.viewport().update()

    def keyPressEvent(self, event):
        self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.viewport().update()
        if event.key() == Qt.Key.Key_Escape:
            self.set_mode("select")
            self.clear_selection()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self._shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.viewport().update()
        super().keyReleaseEvent(event)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        step = float(self.grid_mm)
        while step * abs(self.transform().m11()) < 16:
            step *= 10
        pen = QPen(QColor("#303c4d"), 0)
        painter.setPen(pen)
        left, bottom = math.floor(rect.left() / step) * step, math.floor(rect.top() / step) * step
        if self.grid_visible and rect.width() / step < 300 and rect.height() / step < 300:
            x = left
            while x <= rect.right():
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += step
            y = bottom
            while y <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += step
        if self.axes_visible:
            painter.setPen(QPen(QColor("#000078"), 0))
            painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        draw_overlays(self, painter, rect)
