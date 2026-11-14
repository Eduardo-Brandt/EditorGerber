"""Font selection; exported text is always fabrication geometry."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from gerber_editor.core.primitives import Point
from gerber_editor.tools.vector_text import STROKE_FONT
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class TextDialog(QDialog):
    def __init__(self, position: Point, parent=None, entity=None):
        super().__init__(parent)
        self.locale, self.unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Editar texto" if entity else "Inserir texto vetorial"))
        self.text = QLineEdit("PCB-01")
        self.text.setObjectName("vectorText")
        self.kind = QComboBox()
        self.kind.addItem(t("Fonte stroke PCB"), STROKE_FONT)
        self.kind.addItem(t("Fonte do sistema"), "system")
        self.font = QFontComboBox()
        self.bold, self.italic = QCheckBox(t("Negrito")), QCheckBox(t("Itálico"))
        self.height = spin(self.unit.from_mm(2), 0.000001, 10000, self.unit)
        self.stroke = spin(self.unit.from_mm(0.18), 0.000001, 1000, self.unit)
        self.x = spin(self.unit.from_mm(position.x), unit=self.unit)
        self.y = spin(self.unit.from_mm(position.y), unit=self.unit)
        self.rotation = spin(0, -360, 360)
        self.mirror_y = QCheckBox(t("Espelhar texto localmente"))
        layout = QFormLayout(self)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addRow(t("Texto"), self.text)
        layout.addRow(t("Fonte"), self.kind)
        layout.addRow(t("Fonte do sistema"), self.font)
        layout.addRow(self.bold, self.italic)
        layout.addRow(t("Altura"), self.height)
        layout.addRow(t("Espessura"), self.stroke)
        layout.addRow(t("Rotação (graus)"), self.rotation)
        layout.addRow(self.mirror_y)
        layout.addRow("X", self.x)
        layout.addRow("Y", self.y)
        layout.addRow(self.hint)
        layout.addRow(buttons(self, t))
        self.kind.currentIndexChanged.connect(self._font_kind)
        self._font_kind()
        if entity is None and parent and hasattr(parent, "preferences"):
            from decimal import Decimal

            from gerber_editor.core.text_entity import TextEntity

            saved = parent.preferences.data.get("text_defaults", {})
            if saved:
                values = {
                    **saved,
                    "position": position,
                    "height": Decimal(saved["height"]),
                    "stroke": Decimal(saved["stroke"]),
                }
                entity = TextEntity(**values)
        if entity:
            from PySide6.QtGui import QFont

            self.text.setText(entity.text)
            self.kind.setCurrentIndex(0 if entity.family == STROKE_FONT else 1)
            self.font.setCurrentFont(QFont(entity.family))
            self.height.set_mm(entity.height)
            self.stroke.set_mm(entity.stroke)
            self.rotation.setValue(entity.rotation)
            self.bold.setChecked(entity.bold)
            self.italic.setChecked(entity.italic)
            self.mirror_y.setChecked(entity.mirror_y)

    def _font_kind(self):
        system = self.kind.currentData() == "system"
        self.font.setEnabled(system)
        self.bold.setEnabled(system)
        self.italic.setEnabled(system)
        self.stroke.setEnabled(not system)
        self.hint.setText(
            self.locale(
                "O texto mantém a aparência da fonte ao exportar. Não é necessário instalar a fonte para abrir o Gerber."
                if system
                else "Minúsculas são convertidas em maiúsculas na fonte stroke."
            )
        )

    def values(self):
        return {
            "text": self.text.text(),
            "position": Point(self.x.mm, self.y.mm),
            "height": self.height.mm,
            "stroke": self.stroke.mm,
            "family": self.font.currentFont().family()
            if self.kind.currentData() == "system"
            else STROKE_FONT,
            "rotation": self.rotation.value(),
            "bold": self.bold.isChecked(),
            "italic": self.italic.isChecked(),
            "mirror_y": self.mirror_y.isChecked(),
        }
