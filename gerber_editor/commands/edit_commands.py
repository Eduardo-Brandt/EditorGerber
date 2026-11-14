"""Document edits preserve identity and fabrication order on Undo."""

from dataclasses import dataclass, field, replace

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject


@dataclass
class DeleteObjects:
    targets: list[tuple[GerberLayer, set[str]]]
    label: str = "Excluir objetos"
    _before: list = field(default_factory=list, init=False)

    def redo(self) -> None:
        self._before = [(layer, list(layer.objects)) for layer, _ in self.targets]
        for layer, ids in self.targets:
            layer.objects[:] = [obj for obj in layer.objects if obj.id not in ids]
            layer.revision += 1

    def undo(self) -> None:
        for layer, objects in self._before:
            layer.objects[:] = objects
            layer.revision += 1


@dataclass
class AddObjects:
    layer: GerberLayer
    objects: list[GerberObject]
    label: str = "Criar objetos"

    def redo(self) -> None:
        self.layer.objects.extend(self.objects)
        self.layer.revision += 1

    def undo(self) -> None:
        ids = {obj.id for obj in self.objects}
        self.layer.objects[:] = [obj for obj in self.layer.objects if obj.id not in ids]
        self.layer.revision += 1


@dataclass
class LayerProperty:
    layer: GerberLayer
    name: str
    value: object
    label: str = "Alterar camada"
    _before: object = field(default=None, init=False)

    def redo(self) -> None:
        self._before = getattr(self.layer, self.name)
        setattr(self.layer, self.name, self.value)

    def undo(self) -> None:
        setattr(self.layer, self.name, self._before)


@dataclass
class ReorderLayers:
    layers: list[GerberLayer]
    ordered: list[GerberLayer]
    label: str = "Reordenar camadas"
    _before: list = field(default_factory=list, init=False)

    def redo(self):
        if len(self.layers) != len(self.ordered) or {layer.id for layer in self.layers} != {
            layer.id for layer in self.ordered
        }:
            raise ValueError("As camadas mudaram durante a ordenação.")
        self._before = list(self.layers)
        self.layers[:] = self.ordered

    def undo(self):
        self.layers[:] = self._before


@dataclass
class AddLayer:
    layers: list[GerberLayer]
    layer: GerberLayer
    label: str = "Abrir camada"

    def redo(self) -> None:
        self.layers.append(self.layer)

    def undo(self) -> None:
        self.layers.remove(self.layer)


@dataclass
class ReplaceObjects:
    targets: list[tuple[GerberLayer, dict[str, GerberObject]]]
    label: str = "Mover objetos"
    _before: list = field(default_factory=list, init=False)

    def redo(self) -> None:
        self._before = [(layer, list(layer.objects)) for layer, _ in self.targets]
        for layer, replacements in self.targets:
            layer.objects[:] = [replacements.get(obj.id, obj) for obj in layer.objects]
            layer.revision += 1

    def undo(self) -> None:
        for layer, objects in self._before:
            layer.objects[:] = objects
            layer.revision += 1


@dataclass
class ReplaceObjectSets:
    """Replace variable-size shapes at their original fabrication positions."""

    layer: GerberLayer
    replacements: list
    label: str = "Editar propriedades"
    _before: list = field(default_factory=list, init=False)

    def redo(self):
        self._before = list(self.layer.objects)
        mapping = {
            obj.id: (index, objects)
            for index, (originals, objects) in enumerate(self.replacements)
            for obj in originals
        }
        inserted, result = set(), []
        for obj in self.layer.objects:
            entry = mapping.get(obj.id)
            if entry is None:
                result.append(obj)
            elif entry[0] not in inserted:
                result.extend(entry[1])
                inserted.add(entry[0])
        self.layer.objects[:] = result
        self.layer.revision += 1

    def undo(self):
        self.layer.objects[:] = self._before
        self.layer.revision += 1


@dataclass
class SetObjectGroups:
    """Change session membership, retaining object order and fabrication state."""

    layer: GerberLayer
    memberships: dict[str, str | None]
    label: str = "Agrupar objetos"
    _before: dict = field(default_factory=dict, init=False)

    def redo(self):
        self._before = {obj.id: obj for obj in self.layer.objects if obj.id in self.memberships}
        self.layer.objects[:] = [
            replace(obj, group_id=self.memberships[obj.id]) if obj.id in self.memberships else obj
            for obj in self.layer.objects
        ]
        self.layer.group_revision += 1

    def undo(self):
        self.layer.objects[:] = [self._before.get(obj.id, obj) for obj in self.layer.objects]
        self.layer.group_revision += 1


@dataclass
class CompositeCommand:
    commands: list
    label: str

    def redo(self) -> None:
        for command in self.commands:
            command.redo()

    def undo(self) -> None:
        for command in reversed(self.commands):
            command.undo()


@dataclass
class CloseLayers:
    layers: list[GerberLayer]
    closing: list[GerberLayer]
    label: str = "Fechar camadas"
    _before: list = field(default_factory=list, init=False)

    def redo(self) -> None:
        self._before = list(self.layers)
        ids = {layer.id for layer in self.closing}
        self.layers[:] = [layer for layer in self.layers if layer.id not in ids]

    def undo(self) -> None:
        self.layers[:] = self._before


@dataclass
class ReplaceTextGroup:
    layer: GerberLayer
    group_id: str
    objects: list[GerberObject]
    label: str = "Editar texto"
    _before: list = field(default_factory=list, init=False)

    def redo(self):
        self._before = list(self.layer.objects)
        result, inserted = [], False
        for obj in self.layer.objects:
            if obj.text_entity and obj.text_entity.group_id == self.group_id:
                if not inserted:
                    result.extend(self.objects)
                    inserted = True
            else:
                result.append(obj)
        self.layer.objects[:] = result
        self.layer.revision += 1

    def undo(self):
        self.layer.objects[:] = self._before
        self.layer.revision += 1
