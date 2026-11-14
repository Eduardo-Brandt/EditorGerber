"""Translations use the display unit and return exact mm values."""

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel

from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class TranslationDialog(QDialog):
    def __init__(self, copy: bool, parent=None):
        super().__init__(parent)
        self.locale, self.unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Copiar seleção" if copy else "Mover seleção"))
        layout = QFormLayout(self)
        self.dx, self.dy = spin(self.unit.from_mm(1), unit=self.unit), spin(0, unit=self.unit)
        layout.addRow(t("Delta X"), self.dx)
        layout.addRow(t("Delta Y"), self.dy)
        if not copy:
            hint = QLabel(
                t(
                    "Mover objetos importados requer exportação Normalized.\nO arquivo original permanece preservado."
                )
            )
            hint.setWordWrap(True)
            layout.addRow(hint)
        layout.addRow(buttons(self, t))

    def values(self):
        return self.dx.mm, self.dy.mm
