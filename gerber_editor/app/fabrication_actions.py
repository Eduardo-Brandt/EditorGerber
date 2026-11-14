"""Undoable, exportable fiducials and dedicated PCB routing layers."""

from dataclasses import replace
from uuid import uuid4

from gerber_editor.commands.edit_commands import AddLayer, AddObjects, CompositeCommand
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line
from gerber_editor.geometry.rigid import remap_apertures
from gerber_editor.tools.routing import closed_profiles
from gerber_editor.tools.shapes import layer_quantum, point_on_grid
from gerber_editor.ui.fabrication_dialogs import CutoutDialog, FiducialDialog

ROUTING_ATTRIBUTES = (("EditorGerberRole", ("Route.Cuts",)),)


class FabricationActions:
    def insert_fiducial(self, position):
        dialog = FiducialDialog(position, self)
        if dialog.exec():
            try:
                self.create_fiducial(**dialog.values())
            except ValueError as exc:
                self.show_error("Fiducial não criado", exc)

    def create_fiducial(self, position, copper, mask, side="F"):
        if side not in ("F", "B", "FB"):
            raise ValueError("Face inválida.")
        if copper <= 0 or mask <= copper:
            raise ValueError("A abertura da máscara deve ser maior que o diâmetro do cobre.")
        commands, created = [], []
        for face in side:
            for suffix, diameter, color in (
                ("Cu", copper, "#df6565" if face == "F" else "#65a2e6"),
                ("Mask", mask, "#5ebd81"),
            ):
                role = face + "." + suffix
                layer = next((layer for layer in self.layers if layer.function == role), None)
                if layer is None:
                    bottom_index = 2 + sum(
                        layer.function.startswith("In") and layer.function.endswith(".Cu")
                        for layer in self.layers
                    )
                    function = (
                        (
                            "Copper",
                            "L1" if face == "F" else f"L{bottom_index}",
                            "Top" if face == "F" else "Bot",
                        )
                        if suffix == "Cu"
                        else ("Soldermask", "Top" if face == "F" else "Bot")
                    )
                    layer = GerberLayer(
                        "Fiducials-" + role.replace(".", "_") + ".gbr",
                        function=role,
                        color=color,
                        attributes=((".FileFunction", function),),
                    )
                    commands.append(AddLayer(self.layers, layer))
                p = point_on_grid(position.x, position.y, layer_quantum(layer))
                obj = GerberObject(Flash(p), Aperture(10, "C", (diameter,)))
                objects = remap_apertures(layer, [obj])
                self._validate_objects(objects, layer)
                commands.append(AddObjects(layer, objects, "Inserir fiducial"))
                created.append(layer)
        with self.busy.operation("Inserindo fiducial…"):
            self.active_layer = created[0]
            self.history.push(CompositeCommand(commands, "Inserir fiducial"))

    def new_routing_layer(self):
        layer = GerberLayer(
            "PCB-Route_Cuts.gbr",
            function="Route.Cuts",
            color="#ff77cc",
            attributes=ROUTING_ATTRIBUTES,
        )
        self.add_layer(layer)
        self.statusBar().showMessage(
            self.t("Desenhe contornos fechados ou linhas/arcos com a largura do rasgo.")
        )
        return layer

    def cutouts_from_selection(self):
        selected = [obj for _, objects in self.selected_in_order() for obj in objects]
        if not selected:
            self.new_routing_layer()
            return
        dialog = CutoutDialog(self)
        if dialog.exec():
            closed, width = dialog.values()
            try:
                self.create_cutouts(selected, closed=closed, width=width)
            except ValueError as exc:
                self.show_error("Recorte não criado", exc)

    def create_cutouts(self, selected, *, closed=False, width=None):
        layer = next((layer for layer in self.layers if layer.function == "Route.Cuts"), None)
        commands = []
        if layer is None:
            layer = GerberLayer(
                "PCB-Route_Cuts.gbr",
                function="Route.Cuts",
                color="#ff77cc",
                attributes=ROUTING_ATTRIBUTES,
            )
            commands.append(AddLayer(self.layers, layer))
        if closed:
            geometry = closed_profiles(selected, include_strokes=True)
            if geometry.is_empty and all(isinstance(obj.geometry, (Line, Arc)) for obj in selected):
                raise ValueError("Selecione um contorno fechado para recortar.")
            objects = [
                replace(
                    obj,
                    polarity=Polarity.DARK,
                    id=uuid4().hex,
                    source_tokens=(),
                    origin="created",
                    text_entity=None,
                    attributes=tuple(
                        item for item in obj.attributes if item[0] != "EditorGerberCut"
                    )
                    + (("EditorGerberCut", ("Profile",)),),
                )
                for obj in selected
            ]
            objects = remap_apertures(layer, objects)
        else:
            objects = []
            for obj in selected:
                aperture = obj.aperture
                if width is not None and isinstance(obj.geometry, (Line, Arc)):
                    aperture = Aperture(10, "C", (width,))
                objects.append(
                    replace(
                        obj,
                        aperture=aperture,
                        polarity=Polarity.DARK,
                        id=uuid4().hex,
                        source_tokens=(),
                        origin="created",
                        text_entity=None,
                        attributes=tuple(
                            item for item in obj.attributes if item[0] != "EditorGerberCut"
                        )
                        + (("EditorGerberCut", ("Stroke",)),),
                    )
                )
            objects = remap_apertures(layer, objects)
        self._validate_objects(objects, layer)
        commands.append(AddObjects(layer, objects, "Criar recorte ou rasgo"))
        with self.busy.operation("Gerando recortes…"):
            self.active_layer = layer
            self.history.push(CompositeCommand(commands, "Criar recorte ou rasgo"))
