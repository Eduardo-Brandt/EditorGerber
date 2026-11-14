"""Rectangular and polar copy parameters, expressed in the selected length unit."""

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLabel, QSpinBox

from gerber_editor.core.primitives import Point
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class ArrayDialog(QDialog):
    def __init__(self, center, parent=None):
        super().__init__(parent)
        self.locale, unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Matriz de cópias"))
        self.kind = QComboBox()
        self.kind.addItems([t("Retangular"), t("Polar")])
        self.nx, self.ny, self.count = QSpinBox(), QSpinBox(), QSpinBox()
        for field in (self.nx, self.ny, self.count):
            field.setRange(1, 1000)
            field.setValue(2)
        self.count.setValue(6)
        self.dx = spin(unit.from_mm(10), unit=unit)
        self.dy = spin(unit.from_mm(10), unit=unit)
        self.cx = spin(unit.from_mm(center.x), unit=unit)
        self.cy = spin(unit.from_mm(center.y), unit=unit)
        self.sweep = spin(360, -360, 360)
        self.by_radius = QCheckBox(t("Definir matriz polar pelo raio"))
        self.radius = spin(unit.from_mm(10), 0.000001, 999999, unit)
        self.center_direction = spin(180, -360, 360)
        self.rotate = QCheckBox(t("Girar também os objetos"))
        self.rotate.setChecked(True)
        self.pick_center = QCheckBox(t("Escolher centro pelo mouse"))
        self.pick_center.setChecked(True)
        layout = QFormLayout(self)
        note = QLabel(
            t(
                "As quantidades incluem o original. No modo por raio, o centro fica na direção indicada a partir do original, que permanece no lugar."
            )
        )
        note.setWordWrap(True)
        layout.addRow(note)
        for label, widget in [
            ("Tipo de matriz", self.kind),
            ("Colunas (inclui original)", self.nx),
            ("Linhas (inclui original)", self.ny),
            ("Passo X", self.dx),
            ("Passo Y", self.dy),
            ("Quantidade polar (inclui original)", self.count),
            ("Ângulo total (graus)", self.sweep),
            ("Raio polar", self.radius),
            ("Direção do centro (graus)", self.center_direction),
            ("Centro X", self.cx),
            ("Centro Y", self.cy),
        ]:
            layout.addRow(t(label), widget)
        layout.addRow(self.pick_center)
        layout.addRow(self.by_radius)
        layout.addRow(self.rotate)
        layout.addRow(buttons(self, t))
        self.kind.currentIndexChanged.connect(self._mode)
        self.pick_center.toggled.connect(self._mode)
        self.by_radius.toggled.connect(self._mode)
        self._mode()

    def _mode(self, *_):
        polar = self.kind.currentIndex() == 1
        for field in (self.nx, self.ny, self.dx, self.dy):
            field.setEnabled(not polar)
        for field in (self.count, self.sweep, self.rotate, self.by_radius):
            field.setEnabled(polar)
        by_radius = polar and self.by_radius.isChecked()
        if by_radius and self.pick_center.isChecked():
            self.pick_center.blockSignals(True)
            self.pick_center.setChecked(False)
            self.pick_center.blockSignals(False)
        self.radius.setEnabled(by_radius)
        self.center_direction.setEnabled(by_radius)
        self.pick_center.setEnabled(polar and not by_radius)
        for field in (self.cx, self.cy):
            field.setEnabled(polar and not by_radius and not self.pick_center.isChecked())

    def values(self):
        return {
            "polar": self.kind.currentIndex() == 1,
            "nx": self.nx.value(),
            "ny": self.ny.value(),
            "dx": self.dx.mm,
            "dy": self.dy.mm,
            "count": self.count.value(),
            "sweep": self.sweep.value(),
            "center": Point(self.cx.mm, self.cy.mm),
            "rotate": self.rotate.isChecked(),
            "pick_center": self.pick_center.isChecked() and not self.by_radius.isChecked(),
            "by_radius": self.by_radius.isChecked(),
            "radius": self.radius.mm,
            "center_direction": self.center_direction.value(),
        }
