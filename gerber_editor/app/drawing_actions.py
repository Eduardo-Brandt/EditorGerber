"""Drawing tool coordination; logical geometry is built outside the widgets."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QImage
from PySide6.QtWidgets import QFileDialog

from gerber_editor.commands.edit_commands import AddObjects
from gerber_editor.core.objects import Polarity
from gerber_editor.core.text_entity import TextEntity
from gerber_editor.tools.dimensions import create_dimension
from gerber_editor.tools.drawing import create_line
from gerber_editor.tools.raster import raster_objects
from gerber_editor.tools.shapes import create_shape, layer_quantum, point_on_grid
from gerber_editor.tools.text_session import text_objects
from gerber_editor.ui.dimension_dialog import DimensionDialog
from gerber_editor.ui.raster_dialog import RasterDialog
from gerber_editor.ui.text_dialog import TextDialog


class DrawingActions:
    def remember_text(self, values):
        saved = {key: value for key, value in values.items() if key != "position"}
        for key in ("height", "stroke"):
            saved[key] = str(saved[key])
        self.remember(text_defaults=saved)

    def set_tool(self, mode):
        if mode not in ("select", "measure", "fiducial") and not self.active_layer:
            self.statusBar().showMessage(self.t("Abra ou crie uma camada antes de desenhar."), 6000)
            self.canvas.set_mode("select")
            return
        self.canvas.set_mode(mode)
        messages = {
            "select": "Seleção: clique ou janela → contém; janela ← cruza. Ctrl adiciona. Esc cancela.",
            "line": "Clique no início e no fim. Esc cancela.",
            "measure": "Clique no início e no fim. Esc cancela.",
            "arc": "Clique no centro, no início e no fim do arco. Esc cancela.",
            "circle": "Clique no centro e em um ponto do círculo. Esc cancela.",
            "rectangle": "Clique em dois cantos opostos. Esc cancela.",
            "square": "Clique em dois cantos opostos. Esc cancela.",
            "text": "Clique no ponto de inserção. Esc cancela.",
            "fiducial": "Clique na posição do fiducial ou use snap a um ponto.",
            "dimension": "Clique nos dois pontos medidos e na posição da cota.",
        }
        self.statusBar().showMessage(self.t(messages[mode]))

    def _mode_changed(self, mode):
        getattr(self, mode + "_action", self.select_action).setChecked(True)

    def _drawing_layer(self):
        if not self.active_layer or not self.active_layer.visible:
            raise ValueError(self.t("Selecione uma camada visível para desenhar."))
        return self.active_layer

    def _polarity(self):
        return Polarity.DARK if self.polarity_input.currentIndex() == 0 else Polarity.CLEAR

    def _line_created(self, start, end):
        try:
            layer = self._drawing_layer()
            with self.busy.operation("Atualizando geometria…"):
                obj = create_line(layer, start, end, self.drawing_width_mm, self._polarity())
                self.history.push(AddObjects(layer, [obj], "Criar linha"))
        except ValueError as exc:
            self.show_error("Geometria não criada", exc)

    def _shape_requested(self, kind, points, clockwise=False):
        try:
            layer = self._drawing_layer()
            values = None
            if kind == "dimension":
                dialog = DimensionDialog(self)
                if not dialog.exec():
                    return
                values = dialog.values()
            with self.busy.operation(
                "Gerando cota…" if kind == "dimension" else "Atualizando geometria…"
            ):
                if kind == "dimension":
                    objects = create_dimension(layer, *points, **values, polarity=self._polarity())
                else:
                    objects = create_shape(
                        layer,
                        kind,
                        points,
                        self.drawing_width_mm,
                        self._polarity(),
                        clockwise,
                        filled=self.filled_input.isChecked(),
                    )
                self.commit_created(layer, objects, "Criar " + kind)
        except ValueError as exc:
            self.show_error(
                "Cota não criada" if kind == "dimension" else "Geometria não criada", exc
            )

    def commit_created(self, layer, objects, label):
        # Prepare paths before mutating the document. Invalid font/raster
        # polygons fail atomically rather than leaving a half-applied command.
        self._validate_objects(objects, layer)
        self.history.push(AddObjects(layer, objects, label))

    def _text_requested(self, position):
        try:
            layer = self._drawing_layer()
            dialog = TextDialog(position, self)
            if dialog.exec():
                with self.busy.operation("Gerando texto…"):
                    self.remember_text(dialog.values())
                    objects = text_objects(layer, TextEntity(**dialog.values()), self._polarity())
                    self.commit_created(layer, objects, "Criar texto vetorial")
        except ValueError as exc:
            self.show_error("Texto não criado", exc)

    def import_graphic(self):
        try:
            layer = self._drawing_layer()
            path, _ = QFileDialog.getOpenFileName(
                self,
                self.t("Importar gráfico P&B…"),
                self.last_directory,
                "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp);;All (*)",
            )
            if not path:
                return
            from pathlib import Path

            self.remember_directory(Path(path).parent)
            image = QImage(path)
            if image.isNull():
                raise ValueError("Unable to read the image.")
            dialog = RasterDialog(image, self)
            if dialog.exec():
                with self.busy.operation("Importando gráfico…"):
                    mask, position, width = dialog.values()
                    objects = raster_objects(layer, mask, position, width, self._polarity())
                    if dialog.mouse_placement.isChecked():
                        anchor = point_on_grid(
                            position.x + width / 2,
                            position.y + width * mask.shape[0] / mask.shape[1] / 2,
                            layer_quantum(layer),
                        )
                        self.canvas._cursor = self.canvas.mapToScene(
                            self.canvas.viewport().mapFromGlobal(QCursor.pos())
                        )
                        self._begin_edit(
                            {
                                "kind": "graphic",
                                "label": "Importar gráfico",
                                "layer": layer,
                                "objects": objects,
                                "anchor": anchor,
                            }
                        )
                    else:
                        self.canvas.set_mode("select")
                        self.commit_created(layer, objects, "Importar gráfico")
                self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        except (ValueError, OSError) as exc:
            self.show_error("Gráfico não importado", exc)
