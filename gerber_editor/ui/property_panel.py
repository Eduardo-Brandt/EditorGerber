"""Object inspection with entry to editable geometry and session text."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gerber_editor.app.i18n import Locale
from gerber_editor.core.primitives import Arc, Flash, Line
from gerber_editor.core.units import Unit
from gerber_editor.tools.editable_shapes import shape_selection


class PropertyPanel(QWidget):
    editRequested = Signal()

    def __init__(self, locale=None):
        super().__init__()
        self.locale = locale or Locale()
        self.unit = Unit.MM
        self.summary = QLabel("Nenhum objeto selecionado")
        self.summary.setWordWrap(True)
        self.table = QTableWidget(0, 2)
        self.table.setProperty("readOnlyValues", True)
        self.table.setHorizontalHeaderLabels(["Propriedade", "Valor"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 110)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.summary)
        layout.addWidget(self.table)
        self.edit_button = QPushButton()
        self.locale.bind(self.edit_button, "Editar propriedades…")
        self.edit_button.clicked.connect(self.editRequested)
        self.table.cellDoubleClicked.connect(lambda *_: self.editRequested.emit())
        layout.addWidget(self.edit_button)

    def show_objects(self, items):
        t, unit = self.locale, self.unit

        def number(value):
            return f"{unit.from_mm(value):.6f}"

        def xy(point):
            return number(point.x) + " / " + number(point.y) + " " + unit.value

        self.table.setHorizontalHeaderLabels([t("Propriedade"), t("Valor")])
        self.summary.setText(
            t("{count} objeto(s) selecionado(s)", count=len(items))
            if items
            else t("Nenhum objeto selecionado")
        )
        if (
            items
            and items[0].obj.group_id
            and all(
                item.layer is items[0].layer and item.obj.group_id == items[0].obj.group_id
                for item in items
            )
        ):
            self.summary.setText(t("Grupo com {count} objeto(s)", count=len(items)))
        rows = []
        groups = {item.obj.text_entity.group_id for item in items if item.obj.text_entity}
        self.edit_button.setEnabled(
            len(items) == 1
            or (len(groups) == 1 and all(item.obj.text_entity for item in items))
            or bool(shape_selection(items))
            or bool(
                items
                and not any(item.obj.text_entity for item in items)
                and len({type(item.obj.geometry) for item in items}) == 1
                and len(
                    {
                        (
                            item.obj.aperture.shape,
                            bool(item.obj.aperture.macro),
                            len(item.obj.aperture.parameters),
                        )
                        if item.obj.aperture
                        else None
                        for item in items
                    }
                )
                == 1
            )
        )
        if len(items) == 1:
            obj, layer = items[0].obj, items[0].layer
            rows = [
                ("Tipo", obj.kind),
                ("Camada", layer.name),
                ("Polaridade", obj.polarity.name),
                ("Origem", obj.origin),
                ("ID", obj.id),
            ]
            g = obj.geometry
            if isinstance(g, (Line, Arc)):
                rows += [
                    ("Início X / Y", xy(g.start)),
                    ("Fim X / Y", xy(g.end)),
                ]
            if isinstance(g, Arc):
                rows += [
                    ("Centro X / Y", xy(g.center)),
                    ("Raio", number(g.radius) + " " + unit.value),
                    ("Sentido", "CW" if g.clockwise else "CCW"),
                ]
            if isinstance(g, Flash):
                rows += [("X / Y", xy(g.position))]
            if obj.aperture:
                rows += [
                    ("Aperture", f"D{obj.aperture.code} · {obj.aperture.shape}"),
                    (
                        "Parâmetros",
                        " × ".join(
                            str(v)
                            if obj.aperture.macro or (obj.aperture.shape == "P" and i in (1, 2))
                            else number(v)
                            for i, v in enumerate(obj.aperture.parameters)
                        ),
                    ),
                ]
            rows += [(name, ", ".join(values)) for name, values in obj.attributes]
        if items:
            b = items[0].obj.bounds
            for item in items[1:]:
                b = b.union(item.obj.bounds)
            rows += [
                (t("Bounds mín.") + f" ({unit.value})", f"{number(b.left)}, {number(b.bottom)}"),
                (t("Bounds máx.") + f" ({unit.value})", f"{number(b.right)}, {number(b.top)}"),
                (
                    t("Dimensões") + f" ({unit.value})",
                    f"{number(b.right - b.left)} × {number(b.top - b.bottom)}",
                ),
            ]
        self.table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(t(key)))
            self.table.setItem(row, 1, QTableWidgetItem(value))
