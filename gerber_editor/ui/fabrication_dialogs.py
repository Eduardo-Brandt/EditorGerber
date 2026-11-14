"""Precise fiducial placement and routing from ordinary selected objects."""

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout

from gerber_editor.core.primitives import Point
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class FiducialDialog(QDialog):
    def __init__(self, position, parent):
        super().__init__(parent)
        self.locale, unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Inserir fiducial"))
        self.x, self.y = (
            spin(unit.from_mm(position.x), unit=unit),
            spin(unit.from_mm(position.y), unit=unit),
        )
        self.copper = spin(unit.from_mm(1), 0.000001, 10000, unit)
        self.mask = spin(unit.from_mm(2), 0.000001, 10000, unit)
        self.side = QComboBox()
        for label, value in (("Frente", "F"), ("Verso", "B"), ("Ambos", "FB")):
            self.side.addItem(t(label), value)
        form = QFormLayout(self)
        for label, field in (
            ("X", self.x),
            ("Y", self.y),
            ("Diâmetro do cobre", self.copper),
            ("Abertura da máscara", self.mask),
            ("Face", self.side),
        ):
            form.addRow(t(label), field)
        form.addRow(buttons(self, t))

    def values(self):
        return {
            "position": Point(self.x.mm, self.y.mm),
            "copper": self.copper.mm,
            "mask": self.mask.mm,
            "side": self.side.currentData(),
        }


class CutoutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.locale, unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Criar recorte ou rasgo"))
        self.kind = QComboBox()
        self.kind.addItems([t("Rasgo pela largura do traço"), t("Recorte por contorno fechado")])
        self.width = spin(unit.from_mm(1), 0.000001, 10000, unit)
        form = QFormLayout(self)
        form.addRow(t("Tipo"), self.kind)
        form.addRow(t("Largura do rasgo"), self.width)
        form.addRow(buttons(self, t))
        self.kind.currentIndexChanged.connect(lambda index: self.width.setEnabled(index == 0))

    def values(self):
        return self.kind.currentIndex() == 1, self.width.mm
