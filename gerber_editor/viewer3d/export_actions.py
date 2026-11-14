"""Resolution-controlled GPU images and asynchronous physical model exports."""

import logging
from pathlib import Path

from PySide6.QtCore import QIODevice, QObject, QRunnable, QSaveFile, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QMessageBox,
    QSpinBox,
)

from gerber_editor.ui.dialog_helpers import buttons
from gerber_editor.viewer3d.exporters import export_step, export_wrl


class ImageResolutionDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        t = parent.locale
        self.setWindowTitle(t("Exportar imagem JPG"))
        self.width_pixels, self.height_pixels, self.quality = QSpinBox(), QSpinBox(), QSpinBox()
        for field in (self.width_pixels, self.height_pixels):
            field.setRange(64, 8192)
        self.aspect = parent.viewport.width() / max(1, parent.viewport.height())
        self.width_pixels.setValue(1920)
        self.height_pixels.setValue(round(1920 / self.aspect))
        self.quality.setRange(1, 100)
        self.quality.setValue(95)
        self.lock = QCheckBox(t("Manter proporção"))
        self.lock.setChecked(True)
        self.width_pixels.valueChanged.connect(lambda value: self._sync(value, True))
        self.height_pixels.valueChanged.connect(lambda value: self._sync(value, False))
        form = QFormLayout(self)
        for label, field in (
            ("Largura em pixels", self.width_pixels),
            ("Altura em pixels", self.height_pixels),
            ("Qualidade JPG", self.quality),
        ):
            form.addRow(t(label), field)
        form.addRow(self.lock)
        form.addRow(buttons(self, t))

    def _sync(self, value, width):
        if self.lock.isChecked():
            other = self.height_pixels if width else self.width_pixels
            other.blockSignals(True)
            other.setValue(round(value / self.aspect if width else value * self.aspect))
            other.blockSignals(False)

    def values(self):
        return self.width_pixels.value(), self.height_pixels.value(), self.quality.value()


class ExportSignals(QObject):
    finished = Signal(str, str)


class ExportJob(QRunnable):
    def __init__(self, mesh, path, hidden, kind):
        super().__init__()
        self.mesh, self.path, self.hidden, self.kind = mesh, path, set(hidden), kind
        self.signals = ExportSignals()

    def run(self):
        try:
            (export_step if self.kind == "step" else export_wrl)(self.mesh, self.path, self.hidden)
            self.signals.finished.emit(str(self.path), "")
        except Exception as exc:
            logging.getLogger(__name__).exception("3D model export failed: %s", self.path)
            self.signals.finished.emit(str(self.path), str(exc))


class ExportActions:
    def export_default_path(self, filename):
        directory = self.editor.preferences.data["last_export_directory"]
        if not directory or not Path(directory).is_dir():
            directory = self.editor.last_directory
        return str(Path(directory) / filename)

    def remember_export_path(self, path):
        self.editor.remember(last_export_directory=str(Path(path).resolve().parent))

    def export_jpg(self):
        dialog = ImageResolutionDialog(self)
        if not dialog.exec():
            return
        width, height, quality = dialog.values()
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.locale("Exportar imagem JPG"),
            self.export_default_path("PCB.jpg"),
            "JPEG (*.jpg *.jpeg)",
        )
        if not path:
            return
        self.remember_export_path(path)
        self.progress.setRange(0, 0)
        self.progress.show()
        token = self.busy.begin("Renderizando imagem…")
        self.statusBar().showMessage(self.locale("Renderizando imagem…"))
        self.busy.overlay.repaint()
        try:
            self.save_jpg(path, width, height, quality)
            self.statusBar().showMessage(
                self.locale("Imagem exportada") + f": {Path(path).name} · {width} × {height} px"
            )
        except (ValueError, OSError) as exc:
            QMessageBox.warning(
                self, self.locale("Exportação não concluída"), self.locale.error(str(exc))
            )
        finally:
            self.busy.end(token)
            self.progress.hide()

    def save_jpg(self, path, width, height, quality=95):
        image = self.viewport.capture_image(width, height)
        destination = QSaveFile(str(path))
        if not destination.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError(destination.errorString())
        if not image.save(destination, "JPG", quality) or not destination.commit():
            destination.cancelWriting()
            raise OSError("Não foi possível salvar a imagem.")

    def export_model(self, kind):
        title = self.locale(
            "Exportar STEP com cores" if kind == "step" else "Exportar WRL com cores"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            self.export_default_path(f"PCB.{kind}"),
            "STEP (*.step *.stp)" if kind == "step" else "VRML (*.wrl)",
        )
        if not path or not self.viewport.mesh or self._export_job:
            return
        self.remember_export_path(path)
        self._export_job = ExportJob(self.viewport.mesh, path, self.viewport.hidden, kind)
        self._export_job.signals.finished.connect(self._export_finished)
        self.progress.setRange(0, 0)
        self.progress.show()
        self._export_busy_token = self.busy.begin("Exportando modelo 3D…")
        self.reload_action.setEnabled(False)
        for action in self.export_actions:
            action.setEnabled(False)
        self.statusBar().showMessage(self.locale("Exportando modelo 3D…"))
        QThreadPool.globalInstance().start(self._export_job)

    def _export_finished(self, path, error):
        self._export_job = None
        self.busy.end(self._export_busy_token)
        self._export_busy_token = None
        self.progress.hide()
        self.reload_action.setEnabled(True)
        self._update_export_actions()
        if error:
            QMessageBox.warning(
                self, self.locale("Exportação não concluída"), self.locale.error(error)
            )
        else:
            self.statusBar().showMessage(self.locale("Modelo exportado") + ": " + Path(path).name)
        self.request_refresh()
