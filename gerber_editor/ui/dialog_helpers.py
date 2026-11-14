"""Shared localized, unit-aware dialog controls."""

from PySide6.QtWidgets import QDialogButtonBox, QDoubleSpinBox

from gerber_editor.app.i18n import Locale
from gerber_editor.core.units import Unit


class LengthSpin(QDoubleSpinBox):
    """Keep exact mm values when unit conversion rounds only their display."""

    def __init__(self, unit):
        super().__init__()
        self.unit = Unit(unit)
        self.mm = self.unit.to_mm(0)
        self.valueChanged.connect(self._edited)

    def _edited(self, value):
        self.mm = self.unit.to_mm(value)

    def set_mm(self, value):
        self.mm = self.unit.to_mm(0) + value
        self.blockSignals(True)
        self.setValue(float(self.unit.from_mm(self.mm)))
        self.blockSignals(False)

    def set_unit(self, unit):
        self.unit = Unit(unit)
        self.setSuffix(" " + self.unit.value)
        self.set_mm(self.mm)


def dialog_context(parent):
    return getattr(parent, "locale", Locale()), Unit(getattr(parent, "display_unit", "mm"))


def spin(value, minimum=-999999, maximum=999999, unit=None):
    widget = LengthSpin(unit) if unit else QDoubleSpinBox()
    widget.setDecimals(6)
    widget.setRange(minimum, maximum)
    widget.setValue(float(value))
    if unit:
        widget.setSuffix(" " + Unit(unit).value)
        widget.set_mm(Unit(unit).to_mm(value))
    return widget


def buttons(dialog, locale):
    result = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    result.button(QDialogButtonBox.StandardButton.Cancel).setText(locale("Cancelar"))
    result.accepted.connect(dialog.accept)
    result.rejected.connect(dialog.reject)
    return result
