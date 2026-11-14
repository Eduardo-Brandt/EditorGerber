"""Cursor-driven edits, a native clipboard, copy arrays and session properties."""

import copy
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QInputDialog

from gerber_editor.commands.edit_commands import (
    AddObjects,
    CompositeCommand,
    ReplaceObjects,
    ReplaceObjectSets,
    ReplaceTextGroup,
    SetObjectGroups,
)
from gerber_editor.core.primitives import Point
from gerber_editor.core.text_entity import TextEntity
from gerber_editor.geometry.boolean import object_geometry
from gerber_editor.geometry.rigid import RigidTransform, remap_apertures
from gerber_editor.gerber.writer import SaveMode
from gerber_editor.graphics.renderer import painter_path
from gerber_editor.tools.clipboard import MIME_TYPE, decode, encode
from gerber_editor.tools.editable_shapes import edit_shape, shape_selection
from gerber_editor.tools.object_properties import edit_object, object_values
from gerber_editor.tools.shapes import layer_quantum
from gerber_editor.tools.text_session import text_objects
from gerber_editor.ui.array_dialog import ArrayDialog
from gerber_editor.ui.object_dialog import ObjectDialog
from gerber_editor.ui.parameter_dialog import ParameterDialog
from gerber_editor.ui.text_dialog import TextDialog


class EditActions:
    def group_selection(self):
        targets = self.selected_in_order()
        if len(targets) != 1 or len(targets[0][1]) < 2:
            self.statusBar().showMessage(
                self.t("Selecione dois ou mais objetos da mesma camada."), 6000
            )
            return
        layer, objects = targets[0]
        groups = {obj.group_id for obj in objects}
        if len(groups) == 1 and None not in groups:
            return
        self.canvas.set_mode("select")
        group_id = uuid4().hex
        self.history.push(SetObjectGroups(layer, {obj.id: group_id for obj in objects}))

    def ungroup_selection(self):
        commands = [
            SetObjectGroups(
                layer, {obj.id: None for obj in objects if obj.group_id}, "Desagrupar objetos"
            )
            for layer, objects in self.selected_in_order()
            if any(obj.group_id for obj in objects)
        ]
        if commands:
            self.canvas.set_mode("select")
            self.history.push(CompositeCommand(commands, "Desagrupar objetos"))

    def selected_in_order(self):
        ids, seen = set(), set()
        for item in self.canvas.selected_objects():
            key = (item.layer.id, self.canvas._selection_key(item.obj) or item.obj.id)
            if key not in seen:
                seen.add(key)
                ids.update(member.obj.id for member in self.canvas.selection_members(item))
        return [
            (layer, [obj for obj in layer.objects if obj.id in ids])
            for layer in self.layers
            if any(obj.id in ids for obj in layer.objects)
        ]

    def cursor_point(self):
        return self.canvas.snap(self.canvas._cursor)

    def copy_clipboard(self):
        objects = [obj for _, objects in self.selected_in_order() for obj in objects]
        if not objects:
            return False
        mime = QMimeData()
        mime.setData(MIME_TYPE, QByteArray(encode(objects, self.cursor_point())))
        mime.setText(f"Editor Gerber: {len(objects)} objects")
        QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage(self.t("Seleção copiada. Ctrl+V posiciona pelo cursor."), 6000)
        return True

    def cut_clipboard(self):
        if self.copy_clipboard():
            self.delete_selection()

    def paste_clipboard(self):
        try:
            layer = self._drawing_layer()
            mime = QApplication.clipboard().mimeData()
            if mime is None or not mime.hasFormat(MIME_TYPE):
                return
            objects, _ = decode(mime.data(MIME_TYPE))
            groups = {}
            objects = [
                RigidTransform().object(obj, layer_quantum(layer), clone=True, group_ids=groups)
                for obj in objects
            ]
            objects = remap_apertures(layer, objects)
            self._begin_edit({"kind": "paste", "layer": layer, "objects": objects})
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            self.show_error("Não foi possível colar", exc)

    def start_move(self, checked=False, *, anchor=None):
        targets = self.selected_in_order()
        if targets:
            edit = {"kind": "move", "targets": targets}
            if anchor is not None:
                edit["anchor"] = anchor
            self._begin_edit(edit)

    def start_duplicate(self):
        if self.copy_clipboard():
            self.paste_clipboard()

    def _begin_edit(self, edit):
        with self.busy.operation("Preparando edição…"):
            objects = edit.get("objects") or [
                obj for _, values in edit["targets"] for obj in values
            ]
            paths = [painter_path(object_geometry(obj)) for obj in objects]
            if "anchor" not in edit:
                # Use the actual preview envelope, including stroke/aperture
                # extents. Conservative model bounds can offset macro pads.
                bounds = None
                for path in paths:
                    if not path.isEmpty():
                        rect = path.boundingRect()
                        bounds = rect if bounds is None else bounds.united(rect)
                if bounds is None:
                    left = min(obj.bounds.left for obj in objects)
                    bottom = min(obj.bounds.bottom for obj in objects)
                else:
                    left, bottom = bounds.left(), bounds.top()
                # Scene Y points up, so its minimum Y is the bottom edge.
                edit["anchor"] = Point(Decimal(str(left)), Decimal(str(bottom)))
                position = self.canvas.viewport().mapFromGlobal(QCursor.pos())
                if self.canvas.viewport().rect().contains(position):
                    self.canvas._cursor = self.canvas.mapToScene(position)
            excluded = [obj.id for obj in objects] if edit["kind"] == "move" else []
            self.canvas.begin_placement(edit["anchor"], paths, excluded)
            self._pending_edit = edit
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        self.statusBar().showMessage(self.t("Clique para posicionar; Esc cancela"))

    def _cancel_edit(self):
        self._pending_edit = None

    def _commit_placement(self, point):
        edit = self._pending_edit
        if not edit:
            return
        try:
            dx, dy = point.x - edit["anchor"].x, point.y - edit["anchor"].y
            transform = RigidTransform(dx=dx, dy=dy)
            with self.busy.operation("Atualizando geometria…"):
                if edit["kind"] == "move":
                    targets = []
                    for layer, objects in edit["targets"]:
                        current = {obj.id: obj for obj in layer.objects}
                        if layer not in self.layers or not all(
                            current.get(obj.id) == obj for obj in objects
                        ):
                            raise ValueError("A seleção mudou durante a operação.")
                        replacements = {
                            obj.id: transform.object(obj, layer_quantum(layer)) for obj in objects
                        }
                        self._validate_objects(replacements.values(), layer)
                        targets.append((layer, replacements))
                    self.history.push(ReplaceObjects(targets))
                else:
                    layer = edit["layer"]
                    if layer not in self.layers:
                        raise ValueError("A camada de destino foi fechada.")
                    objects = [
                        transform.object(obj, layer_quantum(layer)) for obj in edit["objects"]
                    ]
                    self.commit_created(
                        layer, remap_apertures(layer, objects), edit.get("label", "Colar objetos")
                    )
                    self.canvas.clear_selection()
                    self.canvas.select_objects(
                        self.canvas.object_items[obj.id]
                        for obj in objects
                        if obj.id in self.canvas.object_items
                    )
            self.canvas.set_mode("select")
        except ValueError as exc:
            self.show_error("Geometria não criada", exc)
            self.canvas.set_mode("select")

    def _validate_objects(self, objects, layer=None):
        objects = list(objects)
        for obj in objects:
            object_geometry(obj)
        layer = layer or self.active_layer
        if layer and objects:
            probe = copy.copy(layer)
            probe.objects = objects
            self.writer.serialize(probe, SaveMode.NORMALIZED)

    def mirror_copy(self):
        selected = [obj for _, objects in self.selected_in_order() for obj in objects]
        if not selected:
            return
        choices = [self.t("Espelhar X"), self.t("Espelhar Y"), self.t("Espelhar X e Y")]
        choice, ok = QInputDialog.getItem(
            self, self.t("Cópia espelhada"), self.t("Eixo de reflexão"), choices, 0, False
        )
        if not ok:
            return
        try:
            layer = self._drawing_layer()
            index = choices.index(choice)
            transform = RigidTransform(mirror_x=index in (0, 2), mirror_y=index in (1, 2))
            groups = {}
            objects = [
                transform.object(obj, layer_quantum(layer), clone=True, group_ids=groups)
                for obj in selected
            ]
            self._begin_edit(
                {
                    "kind": "paste",
                    "layer": layer,
                    "objects": remap_apertures(layer, objects),
                }
            )
        except ValueError as exc:
            self.show_error("Geometria não criada", exc)

    def copy_array(self):
        if not self.canvas.selected_objects():
            return
        dialog = ArrayDialog(self.cursor_point(), self)
        if dialog.exec():
            values = dialog.values()
            if values["polar"] and values["pick_center"]:
                targets = self.selected_in_order()
                self.canvas.set_mode("pick_center")
                self._pending_edit = {"kind": "array", "targets": targets, "values": values}
                self.busy.pending(True, "Escolha o centro da matriz polar")
            else:
                self.create_array(self.selected_in_order(), values)

    def _point_picked(self, point):
        edit = self._pending_edit
        self.canvas.set_mode("select")
        self._pending_edit = None
        if edit and edit["kind"] == "array":
            self.create_array(edit["targets"], {**edit["values"], "center": point})

    def create_array(self, targets, values):
        try:
            if values["polar"] and values.get("by_radius"):
                import math

                from gerber_editor.core.primitives import Point

                radius = values["radius"]
                if radius <= 0:
                    raise ValueError("O raio deve ser positivo.")
                selected = [o for _, objects in targets for o in objects]
                bounds = selected[0].bounds
                for obj in selected[1:]:
                    bounds = bounds.union(obj.bounds)
                anchor = Point(
                    Decimal(str((bounds.left + bounds.right) / 2)),
                    Decimal(str((bounds.bottom + bounds.top) / 2)),
                )
                angle = math.radians(values["center_direction"])
                values = {
                    **values,
                    "center": Point(
                        anchor.x + radius * Decimal(str(math.cos(angle))),
                        anchor.y + radius * Decimal(str(math.sin(angle))),
                    ),
                }
            if values["polar"] and values["count"] > 1 and values["sweep"] == 0:
                raise ValueError("O ângulo da matriz polar não pode ser zero.")
            count = values["count"] if values["polar"] else values["nx"] * values["ny"]
            total = sum(len(objects) for _, objects in targets) * (count - 1)
            if total > 200000:
                raise ValueError("A matriz excede 200000 objetos. Reduza a quantidade de cópias.")
            commands = []
            with self.busy.operation("Gerando matriz…"):
                for layer, originals in targets:
                    objects = []
                    for index in range(1, count):
                        if values["polar"]:
                            divisor = count if abs(values["sweep"]) == 360 else max(1, count - 1)
                            angle = values["sweep"] * index / divisor
                            transform = RigidTransform(angle=angle, center=values["center"])
                            if not values["rotate"]:
                                # Orbit the group's anchor, keeping its orientation.
                                bounds = originals[0].bounds
                                for obj in originals[1:]:
                                    bounds = bounds.union(obj.bounds)
                                from gerber_editor.core.primitives import Point

                                anchor = Point(
                                    Decimal(str((bounds.left + bounds.right) / 2)),
                                    Decimal(str((bounds.bottom + bounds.top) / 2)),
                                )
                                end = transform.point(anchor)
                                transform = RigidTransform(dx=end.x - anchor.x, dy=end.y - anchor.y)
                        else:
                            transform = RigidTransform(
                                dx=values["dx"] * (index % values["nx"]),
                                dy=values["dy"] * (index // values["nx"]),
                            )
                        groups = {}
                        objects.extend(
                            transform.object(
                                obj, layer_quantum(layer), clone=True, group_ids=groups
                            )
                            for obj in originals
                        )
                    objects = remap_apertures(layer, objects)
                    self._validate_objects(objects, layer)
                    if objects:
                        commands.append(AddObjects(layer, objects, "Matriz de cópias"))
                if commands:
                    self.history.push(CompositeCommand(commands, "Matriz de cópias"))
        except ValueError as exc:
            self.show_error("Geometria não criada", exc)

    def edit_properties(self):
        selected = self.canvas.selected_objects()
        if not selected:
            return
        layer, obj = selected[0].layer, selected[0].obj
        entity = obj.text_entity
        try:
            if entity and all(
                item.obj.text_entity == entity and item.layer is layer for item in selected
            ):
                dialog = TextDialog(entity.position, self, entity)
                if dialog.exec():
                    with self.busy.operation("Gerando texto…"):
                        self.remember_text(dialog.values())
                        replacement = TextEntity(**dialog.values(), group_id=entity.group_id)
                        objects = text_objects(layer, replacement, obj.polarity)
                        if obj.group_id:
                            objects = [replace(value, group_id=obj.group_id) for value in objects]
                        self._validate_objects(objects, layer)
                        self.history.push(ReplaceTextGroup(layer, entity.group_id, objects))
            elif shapes := shape_selection(selected):
                dialog = ParameterDialog([shape.values for shape in shapes], self)
                if dialog.exec() and (changes := dialog.changes()):
                    self._edit_shapes(shapes, changes)
            elif len(selected) > 1 and self.properties.edit_button.isEnabled():
                baselines = [object_values(item.obj) for item in selected]
                dialog = ParameterDialog(baselines, self)
                if dialog.exec() and (changes := dialog.changes()):
                    commands = []
                    with self.busy.operation("Atualizando geometria…"):
                        by_layer = {}
                        for item, baseline in zip(selected, baselines, strict=True):
                            values = {**baseline, **changes, "_changed": set(changes)}
                            if "length" in changes or "direction" in changes:
                                values["by_length"] = True
                            changed = edit_object(item.layer, item.obj, values)
                            by_layer.setdefault(item.layer.id, (item.layer, []))[1].append(changed)
                        for layer, objects in by_layer.values():
                            objects = remap_apertures(layer, objects)
                            self._validate_objects(objects, layer)
                            commands.append(
                                ReplaceObjects(
                                    [(layer, {o.id: o for o in objects})], "Editar propriedades"
                                )
                            )
                        self.history.push(CompositeCommand(commands, "Editar propriedades"))
            elif len(selected) == 1:
                dialog = ObjectDialog(obj, self)
                if dialog.exec() and dialog.values() != dialog.initial:
                    values = dialog.values()
                    values["_changed"] = {
                        key for key, value in values.items() if value != dialog.initial[key]
                    }
                    with self.busy.operation("Atualizando geometria…"):
                        changed = edit_object(layer, obj, values)
                        self._validate_objects([changed], layer)
                        self.history.push(
                            ReplaceObjects([(layer, {obj.id: changed})], "Editar propriedades")
                        )
        except ValueError as exc:
            self.show_error("Geometria não criada", exc)

    def _edit_shapes(self, shapes, changes):
        commands, by_layer = [], {}
        with self.busy.operation("Atualizando geometria…"):
            for shape in shapes:
                by_layer.setdefault(shape.layer.id, (shape.layer, []))[1].append(
                    (shape.objects, edit_shape(shape, changes))
                )
            for layer, replacements in by_layer.values():
                flat = remap_apertures(layer, [o for _, objects in replacements for o in objects])
                self._validate_objects(flat, layer)
                offset, updated = 0, []
                for originals, objects in replacements:
                    updated.append((originals, flat[offset : offset + len(objects)]))
                    offset += len(objects)
                commands.append(ReplaceObjectSets(layer, updated))
            self.history.push(CompositeCommand(commands, "Editar propriedades"))
