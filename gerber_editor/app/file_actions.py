"""Document file lifecycle, explicit overwrites and reversible closing."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from gerber_editor.app.batch_save import BatchSaveActions
from gerber_editor.app.importer import ImportJob, is_auxiliary_file, looks_like_gerber
from gerber_editor.commands.edit_commands import AddLayer, CloseLayers, CompositeCommand
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.layer_order import ordered_back_to_front
from gerber_editor.gerber.errors import GerberError
from gerber_editor.gerber.writer import SaveMode
from gerber_editor.tools.demo import demo_layer
from gerber_editor.validation.checks import validate_layer

log = logging.getLogger(__name__)


class FileActions(BatchSaveActions):
    def _file_drop_paths(self, event):
        if (
            self._save_all_running
            or self._save_all_preparing
            or not event.possibleActions() & Qt.DropAction.CopyAction
        ):
            return []
        # Content recognition stays in the existing importer, including extensionless files.
        return list(
            dict.fromkeys(
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile() and url.toLocalFile()
            )
        )

    def dragEnterEvent(self, event):
        if self._file_drop_paths(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        paths = []
        for path in self._file_drop_paths(event):
            try:
                if path.is_file():
                    paths.append(path)
            except OSError:
                continue
        if paths:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.open_paths_async(paths)
        else:
            event.ignore()

    def remember_directory(self, path):
        self.last_directory = str(Path(path).resolve())
        self.remember(last_directory=self.last_directory)

    def open_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.t("Abrir arquivos Gerber / Excellon"),
            self.last_directory,
            self.t("Gerber / Excellon com ou sem extensão (*)"),
        )
        self.open_paths_async(paths)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.t("Abrir pasta de Gerbers"), self.last_directory
        )
        if folder:
            self.remember_directory(folder)
            try:
                paths = [
                    path
                    for path in sorted(Path(folder).iterdir())
                    if path.is_file() and looks_like_gerber(path)
                ]
                self.open_paths_async(paths)
                if not paths:
                    QMessageBox.information(
                        self,
                        self.t("Pasta"),
                        self.t(
                            "Nenhum cabeçalho Gerber FS/MO ou Excellon M48 encontrado nesta pasta."
                        ),
                    )
            except OSError as exc:
                self.show_error("Pasta não carregada", exc)

    def open_paths_async(self, paths):
        paths = list(paths)
        if self._save_all_running or self._save_all_preparing:
            return
        if paths:
            self.remember_directory(Path(paths[-1]).parent)
            self.import_progress.add_files(len(paths))
            self.save_all_action.setEnabled(False)
        for path in paths:
            path = Path(path)
            self._job_counter += 1
            job = ImportJob(self._job_counter, path)
            self._import_jobs[job.job_id] = job
            self._import_progress_jobs.add(job.job_id)
            self._job_busy[job.job_id] = self.busy.begin("Carregando…")
            job.signals.finished.connect(self._import_finished, Qt.ConnectionType.QueuedConnection)
            self._import_queue.append(job.job_id)
        self.close_all_action.setEnabled(bool(self.layers or self._import_jobs))
        self._start_next_import()

    def _start_next_import(self):
        if self._import_active is not None or self._applying_import:
            return
        while self._import_queue:
            key = self._import_queue.popleft()
            if key in self._import_jobs:
                self._import_active = key
                self.import_pool.start(self._import_jobs[key])
                return
        if not self._import_jobs:
            self.import_progress.finish()
            self.save_all_action.setEnabled(bool(self.layers) and not self._save_all_running)
            errors, self._import_errors = self._import_errors, []
            skipped, self._import_skipped = self._import_skipped, []
            if skipped:
                self.statusBar().showMessage(
                    self.t("Arquivo auxiliar do KiCad ignorado: {names}", names=", ".join(skipped)),
                    15000,
                )
            if errors:
                self.show_error("Arquivo não carregado", "\n\n".join(errors))

    @Slot(object)
    def _import_finished(self, result):
        self._applying_import = True
        token = self._job_busy.pop(result.job_id, None)
        try:
            if result.job_id in self._cancelled_imports:
                self._cancelled_imports.discard(result.job_id)
                return
            if result.error:
                self._import_errors.append(result.path.name + "\n" + result.error)
            elif result.skipped:
                self._import_skipped.append(result.path.name)
                log.info("Skipped auxiliary file: %s", result.path)
            else:
                self._import_prepared.append((result.layer, result.renderer))
                self.statusBar().showMessage(
                    self.t(
                        "Preparado: {name} · {count} objetos",
                        name=result.layer.name,
                        count=len(result.layer.objects),
                    ),
                    15000,
                )
        finally:
            try:
                if len(self._import_jobs) == 1 and not self._import_queue:
                    self._commit_import_layers()
            except Exception as exc:
                log.exception("Applying imported layers failed")
                self._import_errors.append(str(exc))
            self._import_jobs.pop(result.job_id, None)
            if result.job_id in self._import_progress_jobs:
                self._import_progress_jobs.discard(result.job_id)
                self.import_progress.advance(result.path.name)
            self._import_active = None
            self._applying_import = False
            if token is not None:
                self.busy.end(token)
            self.close_all_action.setEnabled(bool(self.layers or self._import_jobs))
            QTimer.singleShot(0, self._start_next_import)

    def _commit_import_layers(self):
        prepared, self._import_prepared = self._import_prepared, []
        if not prepared:
            return
        if not self.layers:
            by_id = {layer.id: (layer, renderer) for layer, renderer in prepared}
            prepared = [
                by_id[layer.id] for layer in ordered_back_to_front([layer for layer, _ in prepared])
            ]
        with self.busy.operation("Montando camadas…"):
            commands = []
            for layer, renderer in prepared:
                layer.opacity = 1.0
                self.canvas.renderer.adopt(renderer)
                if layer.path:
                    self.original_paths[layer.id] = layer.path.resolve()
                commands.append(AddLayer(self.layers, layer))
            self.canvas.set_mode("select")
            self.active_layer = prepared[-1][0]
            self.history.push(CompositeCommand(commands, "Abrir arquivos"))
            self.canvas.fit_all()
        self.statusBar().showMessage(
            self.t("{count} arquivo(s) carregado(s)", count=len(prepared)), 15000
        )

    def add_layer(self, layer):
        layer.opacity = 1.0
        with self.busy.operation("Atualizando geometria…"):
            self.canvas.renderer.paths(layer)
            self.canvas.set_mode("select")
            if layer.path and layer.id not in self.original_paths:
                self.original_paths[layer.id] = layer.path.resolve()
            self.active_layer = layer
            self.history.push(AddLayer(self.layers, layer))
            self.canvas.fit_all()

    def open_path(self, path):
        try:
            if is_auxiliary_file(Path(path)):
                self.statusBar().showMessage(
                    self.t("Arquivo auxiliar do KiCad ignorado: {names}", names=Path(path).name),
                    15000,
                )
                return None
            with self.busy.operation("Carregando…"):
                self.remember_directory(Path(path).parent)
                layer = self.parser.parse_file(path)
                validate_layer(layer)
                self.add_layer(layer)
            self.statusBar().showMessage(
                self.t(
                    "Aberto: {name} · {count} objetos", name=layer.name, count=len(layer.objects)
                ),
                10000,
            )
            return layer
        except (OSError, GerberError) as exc:
            log.exception("Open failed: %s", path)
            self.show_error("Arquivo não carregado", exc)
            return None

    def load_demo(self):
        self.add_layer(demo_layer())

    def new_layer(self):
        name, ok = QInputDialog.getText(
            self, self.t("Nova camada"), self.t("Nome"), text="New_F_Silkscreen.gbr"
        )
        if ok and name.strip():
            self.add_layer(GerberLayer(name.strip(), function="F.Silk"))

    def default_save_mode(self, layer):
        if layer.source and any(
            obj.id in layer.source.original_objects and obj != layer.source.original_objects[obj.id]
            for obj in layer.objects
        ):
            return SaveMode.NORMALIZED
        return self.save_modes.get(layer.id, SaveMode.PRESERVATION)

    def save_current(self, checked=False):
        return self.save_layer_current(self.active_layer) if self.active_layer else False

    def save_layer_current(self, layer):
        if self._save_all_running or self._save_all_preparing:
            return False
        if layer.path is None:
            return self.save_as(layer=layer)
        target = layer.path.resolve()
        if not layer.modified and target.is_file():
            return True
        if target == self.original_paths.get(layer.id) and target not in self.approved_overwrites:
            answer = QMessageBox.question(
                self,
                self.t("Sobrescrever arquivo ORIGINAL?"),
                self.t("Salvar as alterações no arquivo original?\n{path}", path=target),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            self.approved_overwrites.add(target)
        return self.save_to(layer, target, self.default_save_mode(layer), overwrite=target.exists())

    def save_as(self, checked=False, *, layer=None):
        if self._save_all_running or self._save_all_preparing:
            return False
        layer = layer or self.active_layer
        if layer is None:
            return False
        destination = self._choose_save_destination(layer)
        if destination is None:
            return False
        target, mode = destination
        return self.save_to(layer, target, mode, overwrite=target.exists())

    def _choose_save_destination(self, layer, *, confirm_overwrite=True):
        label, ok = QInputDialog.getItem(
            self,
            self.t("Modo de salvamento"),
            self.t("Exportar a camada: {name}", name=layer.name),
            [
                self.t("Preservation · preservar comandos originais"),
                self.t("Normalized · reemitir geometria lógica"),
            ],
            1 if self.default_save_mode(layer) == SaveMode.NORMALIZED else 0,
            False,
        )
        if not ok:
            return None
        mode = (
            SaveMode.PRESERVATION
            if label == self.t("Preservation · preservar comandos originais")
            else SaveMode.NORMALIZED
        )
        base = Path(self.last_directory) / layer.name
        suffix = ".drl" if layer.file_format == "excellon" else ".gbr"
        default = base.with_name(base.stem + "_edited" + suffix)
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.t("Salvar cópia: {name}", name=layer.name),
            str(default),
            "Excellon (*.drl *.xln);;Gerber (*.gbr);;All (*)"
            if layer.file_format == "excellon"
            else "Gerber (*.gbr);;Excellon (*.drl *.xln);;All (*)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not path:
            return None
        target = Path(path).resolve()
        if target.exists() and confirm_overwrite:
            title = (
                "Sobrescrever arquivo ORIGINAL?"
                if target == self.original_paths.get(layer.id)
                else "Substituir arquivo existente?"
            )
            answer = QMessageBox.question(
                self,
                self.t(title),
                self.t("O arquivo já existe:\n{path}\n\nConfirmar substituição?", path=target),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None
            self.approved_overwrites.add(target)
        return target, mode

    def _record_saved_layer(self, layer, target, mode):
        layer.path = Path(target).resolve()
        if layer.path.suffix.lower() in (".gbr", ".ger", ".gerber"):
            layer.file_format = "gerber"
        elif layer.path.suffix.lower() in (".drl", ".xln"):
            layer.file_format = "excellon"
        layer.name = layer.path.name
        layer.saved_signature = layer.signature()
        self.save_modes[layer.id] = mode
        self.remember_directory(layer.path.parent)

    def save_to(self, layer, target, mode, *, overwrite=False):
        """Save a validated file and make it the layer's current Save destination."""
        try:
            with self.busy.operation("Salvando…"):
                report = self.writer.save(layer, target, mode, overwrite=overwrite)
                self._record_saved_layer(layer, target, mode)
                self.refresh()
            self.statusBar().showMessage(
                self.t(
                    "Salvo e validado: {name} · {count} objetos",
                    name=layer.name,
                    count=report.object_count,
                ),
                20000,
            )
            return True
        except (OSError, GerberError) as exc:
            log.exception("Export failed")
            self.show_error("Arquivo não salvo", exc)
            return False

    def _confirm_close(self, layers):
        dirty = [layer for layer in layers if layer.modified]
        if not dirty:
            return True
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.t("Alterações não salvas"))
        dialog.setText(self.t("Salvar alterações antes de fechar?"))
        dialog.setInformativeText("\n".join(layer.name for layer in dirty))
        save = dialog.addButton(self.t("Salvar"), QMessageBox.ButtonRole.AcceptRole)
        discard = dialog.addButton(self.t("Descartar"), QMessageBox.ButtonRole.DestructiveRole)
        cancel = dialog.addButton(self.t("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton() == save:
            return all(self.save_layer_current(layer) for layer in dirty)
        return dialog.clickedButton() == discard

    def close_layer(self, layer_id):
        if self._save_all_running or self._save_all_preparing:
            return False
        layer = next((value for value in self.layers if value.id == layer_id), None)
        if layer and self._confirm_close([layer]):
            self.canvas.set_mode("select")
            self.history.push(CloseLayers(self.layers, [layer]))
            return True
        return False

    def close_active(self, checked=False):
        return self.close_layer(self.active_layer.id) if self.active_layer else False

    def cancel_imports(self):
        self._import_progress_jobs.clear()
        self.import_progress.cancel()
        for key in list(self._import_jobs):
            self._cancelled_imports.add(key)
            if key != self._import_active:
                self._import_jobs.pop(key, None)
                self._cancelled_imports.discard(key)
                self.busy.end(self._job_busy.pop(key))
        self._import_queue.clear()
        self._import_prepared.clear()

    def close_all(self, checked=False):
        if self._save_all_running or self._save_all_preparing:
            return False
        if self._confirm_close(self.layers):
            self.cancel_imports()
            self.canvas.set_mode("select")
            if self.layers:
                self.history.push(CloseLayers(self.layers, list(self.layers)))
            return True
        return False

    def validate_active(self):
        if self.active_layer:
            try:
                with self.busy.operation("Validando…"):
                    self.writer.serialize(self.active_layer, SaveMode.NORMALIZED)
                QMessageBox.information(
                    self,
                    self.t("Validação"),
                    self.t("Camada válida; reabertura e geometria conferidas."),
                )
            except GerberError as exc:
                self.show_error("Falha de validação", exc)
