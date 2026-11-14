"""Explicit per-field application for a homogeneous selection."""

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QLabel

from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin

LABELS = {
    "cx": "Centro X",
    "cy": "Centro Y",
    "radius": "Raio",
    "width": "Diâmetro / espessura",
    "size_x": "Largura",
    "size_y": "Altura",
    "rotation": "Rotação (graus)",
    "start_angle": "Ângulo inicial (graus)",
    "sweep": "Ângulo do arco (graus)",
    "filled": "Preenchido",
    "clockwise": "Sentido horário",
    "sx": "Início X",
    "sy": "Início Y",
    "ex": "Fim X",
    "ey": "Fim Y",
    "length": "Comprimento a partir do início",
    "direction": "Direção (graus)",
    "x": "X",
    "y": "Y",
    "height": "Altura",
    "offset_x": "Deslocamento X",
    "offset_y": "Deslocamento Y",
    "center_x": "Centro de rotação X",
    "center_y": "Centro de rotação Y",
}
ANGULAR = {"rotation", "direction", "start_angle", "sweep"}
POSITIVE = {"radius", "width", "height", "size_x", "size_y", "length", "sweep"}


class ParameterDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.locale, unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Editar propriedades"))
        self.fields, self.apply = {}, {}
        self.initial = dict(values[0])
        self.multiple = len(values) > 1
        layout = QFormLayout(self)
        if self.multiple:
            info = QLabel(
                t("Marque os campos a alterar. Os demais valores serão mantidos em cada objeto.")
            )
            info.setWordWrap(True)
            layout.addRow(info)
        for key, value in self.initial.items():
            if key == "by_length":
                continue
            label = t(LABELS[key])
            if any(v[key] != value for v in values):
                label += " · " + t("Vários valores")
            if isinstance(value, bool):
                field = QCheckBox()
                field.setChecked(value)
                signal = field.toggled
            else:
                angular = key in ANGULAR
                field = spin(
                    value if angular else unit.from_mm(value),
                    0.000001 if key in POSITIVE else -999999,
                    999999,
                    None if angular else unit,
                )
                if angular:
                    self.initial[key] = field.value()
                else:
                    field.set_mm(value)
                signal = field.valueChanged
            field.setObjectName("property_" + key)
            self.fields[key] = field
            check = QCheckBox(label)
            check.setObjectName("apply_" + key)
            self.apply[key] = check
            if self.multiple:
                layout.addRow(check, field)
                signal.connect(lambda *_args, c=check: c.setChecked(True))
            else:
                layout.addRow(label, field)
        layout.addRow(buttons(self, t))

    def changes(self):
        result = {}
        for key, field in self.fields.items():
            value = (
                field.isChecked()
                if isinstance(field, QCheckBox)
                else getattr(field, "mm", field.value())
            )
            if (self.multiple and self.apply[key].isChecked()) or (
                not self.multiple and value != self.initial[key]
            ):
                result[key] = value
        return result
