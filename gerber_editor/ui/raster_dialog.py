"""Raster artwork preview, monochrome conversion and physical scale."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QLabel, QSpinBox

from gerber_editor.core.primitives import Point
from gerber_editor.tools.raster import binary_image
from gerber_editor.ui.dialog_helpers import buttons, dialog_context, spin


class RasterDialog(QDialog):
    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.locale, self.unit = dialog_context(parent)
        t = self.locale
        self.setWindowTitle(t("Gráfico P&B"))
        self.image = image
        self.width = spin(self.unit.from_mm(20), 0.000001, 10000, self.unit)
        self.x, self.y = spin(0, unit=self.unit), spin(0, unit=self.unit)
        self.mouse_placement = QCheckBox(t("Posicionar pelo mouse"))
        self.mouse_placement.setChecked(True)
        self.pixels, self.threshold = QSpinBox(), QSpinBox()
        self.pixels.setRange(1, 2000)
        self.pixels.setValue(min(800, image.width()))
        self.threshold.setRange(0, 255)
        self.threshold.setValue(128)
        self.invert = QCheckBox(t("Inverter preto/branco"))
        self.preview = QLabel()
        self.preview.setMinimumSize(350, 160)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel(
            t(
                "Cores são convertidas para cinza e depois para preto/branco. Pixels pretos geram geometria."
            )
        )
        self.hint.setWordWrap(True)
        self.placement_hint = QLabel(
            t(
                "Após confirmar, o centro da imagem seguirá o mouse. Clique para posicionar; Esc cancela."
            )
        )
        self.placement_hint.setWordWrap(True)
        self.error = QLabel()
        layout = QFormLayout(self)
        layout.addRow(t("Largura"), self.width)
        layout.addRow(self.mouse_placement)
        for title, field in [
            ("X", self.x),
            ("Y", self.y),
            ("Resolução (pixels)", self.pixels),
            ("Limiar (0–255)", self.threshold),
        ]:
            layout.addRow(t(title), field)
        layout.addRow(self.invert)
        layout.addRow(self.hint)
        layout.addRow(self.placement_hint)
        layout.addRow(self.preview)
        layout.addRow(self.error)
        layout.addRow(buttons(self, t))
        self.pixels.valueChanged.connect(self._preview)
        self.threshold.valueChanged.connect(self._preview)
        self.invert.toggled.connect(self._preview)
        self.mouse_placement.toggled.connect(self._placement_changed)
        self._placement_changed(True)
        self._preview()

    def _placement_changed(self, checked):
        self.x.setEnabled(not checked)
        self.y.setEnabled(not checked)
        self.placement_hint.setVisible(checked)

    def _preview(self):
        try:
            _, preview = binary_image(
                self.image, self.pixels.value(), self.threshold.value(), self.invert.isChecked()
            )
            self.preview.setPixmap(
                QPixmap.fromImage(preview).scaled(500, 200, Qt.AspectRatioMode.KeepAspectRatio)
            )
            self.error.clear()
        except ValueError as exc:
            self.error.setText(self.locale.error(str(exc)))

    def values(self):
        mask, _ = binary_image(
            self.image, self.pixels.value(), self.threshold.value(), self.invert.isChecked()
        )
        return (
            mask,
            Point(self.x.mm, self.y.mm),
            self.width.mm,
        )
