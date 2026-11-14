"""Editable dimensions for selected curves and flashes."""

import math

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout

from gerber_editor.core.primitives import Arc, Flash, Line, Region
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class ObjectDialog(QDialog):
    def __init__(self, obj, parent=None):
        super().__init__(parent)
        self.locale, unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Editar propriedades"))
        self.fields = {}
        self.layout = QFormLayout(self)

        def add(key, label, value, angular=False, positive=False):
            widget = spin(
                value if angular else unit.from_mm(value),
                0.000001 if positive else -999999,
                999999,
                None if angular else unit,
            )
            self.fields[key] = widget
            self.layout.addRow(t(label), widget)

        g = obj.geometry
        if isinstance(g, Line):
            add("sx", "Início X", g.start.x)
            add("sy", "Início Y", g.start.y)
            add("ex", "Fim X", g.end.x)
            add("ey", "Fim Y", g.end.y)
            length = math.hypot(float(g.end.x - g.start.x), float(g.end.y - g.start.y))
            add("length", "Comprimento a partir do início", length, positive=True)
            add(
                "direction",
                "Direção (graus)",
                math.degrees(math.atan2(float(g.end.y - g.start.y), float(g.end.x - g.start.x))),
                True,
            )
            check = QCheckBox(t("Definir fim por comprimento e direção"))
            self.fields["by_length"] = check
            self.layout.addRow(check)
            check.toggled.connect(self._line_mode)
            check.hide()  # Kept in values for API compatibility; inputs now synchronize live.
            self._syncing = False
            for key in ("sx", "sy", "ex", "ey"):
                self.fields[key].valueChanged.connect(
                    lambda _=0, source=key: self._sync_line(source)
                )
            for key in ("length", "direction"):
                self.fields[key].setEnabled(True)
                self.fields[key].valueChanged.connect(
                    lambda _=0, source=key: self._sync_line(source)
                )
        elif isinstance(g, Arc):
            add("cx", "Centro X", g.center.x)
            add("cy", "Centro Y", g.center.y)
            add("radius", "Raio", g.radius, positive=True)
            start, sweep = g.angles()
            add("start_angle", "Ângulo inicial (graus)", math.degrees(start), True)
            add("sweep", "Ângulo do arco (graus)", abs(math.degrees(sweep)), True, True)
            check = QCheckBox(t("Sentido horário"))
            check.setChecked(g.clockwise)
            self.fields["clockwise"] = check
            self.layout.addRow(check)
        elif isinstance(g, Flash):
            add("x", "X", g.position.x)
            add("y", "Y", g.position.y)
        elif isinstance(g, Region):
            add("offset_x", "Deslocamento X", 0)
            add("offset_y", "Deslocamento Y", 0)
            add("rotation", "Rotação (graus)", 0, True)
            add("center_x", "Centro de rotação X", (obj.bounds.left + obj.bounds.right) / 2)
            add("center_y", "Centro de rotação Y", (obj.bounds.bottom + obj.bounds.top) / 2)
        ap = obj.aperture
        if ap and not ap.macro and (isinstance(g, Flash) or ap.shape == "C"):
            add(
                "width",
                "Diâmetro / espessura" if ap.shape == "C" else "Largura",
                ap.parameters[0],
                positive=True,
            )
            if ap.shape in ("R", "O"):
                add("height", "Altura", ap.parameters[1], positive=True)
        self.initial = self.values()
        self.layout.addRow(buttons(self, t))

    def _line_mode(self, checked):
        # All fields stay editable; the most recent edit controls the other pair.
        pass

    def _sync_line(self, source):
        if self._syncing:
            return
        from decimal import Decimal

        self._syncing = True
        try:
            x, y = self.fields["sx"].mm, self.fields["sy"].mm
            if source in ("length", "direction"):
                length = self.fields["length"].mm
                angle = math.radians(self.fields["direction"].value())
                self.fields["ex"].set_mm(x + length * Decimal(str(math.cos(angle))))
                self.fields["ey"].set_mm(y + length * Decimal(str(math.sin(angle))))
                self.fields["by_length"].setChecked(True)
            else:
                dx, dy = self.fields["ex"].mm - x, self.fields["ey"].mm - y
                self.fields["length"].set_mm((dx * dx + dy * dy).sqrt())
                self.fields["direction"].setValue(math.degrees(math.atan2(float(dy), float(dx))))
                self.fields["by_length"].setChecked(False)
        finally:
            self._syncing = False

    def values(self):
        return {
            key: field.isChecked()
            if isinstance(field, QCheckBox)
            else getattr(field, "mm", field.value())
            for key, field in self.fields.items()
        }
