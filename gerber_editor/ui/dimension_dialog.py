"""Dimension units are independent from the current coordinate display unit."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFontComboBox, QFormLayout, QSpinBox

from gerber_editor.core.units import Unit
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class DimensionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.locale, self.current_unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Cota"))
        self.unit = QComboBox()
        self.unit.addItems(["mm", "in", "mil"])
        self.unit.setCurrentText(self.current_unit.value)
        self.arrow = spin(self.current_unit.from_mm(1), 0.000001, 10000, self.current_unit)
        self.height = spin(self.current_unit.from_mm(1.5), 0.000001, 10000, self.current_unit)
        self.width = spin(self.current_unit.from_mm(0.15), 0.000001, 1000, self.current_unit)
        self.font = QFontComboBox()
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 6)
        self.decimals.setValue(3)
        self.polar = QCheckBox(t("Mostrar ângulo polar"))
        layout = QFormLayout(self)
        for label, widget in [
            ("Unidade", self.unit),
            ("Tamanho da seta", self.arrow),
            ("Altura do texto", self.height),
            ("Espessura", self.width),
            ("Fonte", self.font),
            ("Precisão decimal", self.decimals),
        ]:
            layout.addRow(t(label), widget)
        layout.addRow(self.polar)
        layout.addRow(buttons(self, t))
        self.unit.currentTextChanged.connect(self._units_changed)

    def _units_changed(self, value):
        new_unit = Unit(value)
        for field in (self.arrow, self.height, self.width):
            field.set_unit(new_unit)
        self.current_unit = new_unit

    def values(self):
        return {
            "arrow_mm": self.arrow.mm,
            "text_mm": self.height.mm,
            "width_mm": self.width.mm,
            "family": self.font.currentFont().family(),
            "unit": self.current_unit.value,
            "decimals": self.decimals.value(),
            "polar": self.polar.isChecked(),
        }
