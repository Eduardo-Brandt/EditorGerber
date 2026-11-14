"""Preflight destinations, then save sequentially without blocking Qt painting."""

from collections import deque

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from gerber_editor.app.saver import SaveJob, SaveRequest


class BatchSaveActions:
    def save_all(self, checked=False):
        if self._save_all_running or self._save_all_preparing or self._import_jobs:
            return False
        pending = [
            layer
            for layer in self.layers
            if layer.path is None or layer.modified or not layer.path.is_file()
        ]
        if not pending:
            self.statusBar().showMessage(self.t("Todos os arquivos já estão salvos."), 10000)
            return True
        self._save_all_preparing = True
        token = self.busy.begin("Preparando salvamento…")
        try:
            requests, destinations = [], set()
            for layer in pending:
                if layer.path is None:
                    destination = self._choose_save_destination(layer, confirm_overwrite=False)
                    if destination is None:
                        return False
                    target, mode = destination
                else:
                    target, mode = layer.path.resolve(), self.default_save_mode(layer)
                if target in destinations:
                    self.show_error(
                        "Arquivo não salvo",
                        self.t(
                            "Duas camadas usam o mesmo destino. Use Salvar como para separá-las:\n{path}",
                            path=target,
                        ),
                    )
                    return False
                destinations.add(target)
                requests.append(SaveRequest(layer, target, mode, target.exists()))
            if not self._confirm_save_all(requests):
                return False
            self.approved_overwrites.update(r.target for r in requests if r.overwrite)
            self._save_requests = deque(requests)
            self._save_all_count = len(requests)
            self._save_all_done = 0
            self._save_all_running = True
            self._save_busy = token
            self.save_progress.add_files(len(requests))
            self.save_all_action.setEnabled(False)
            self.close_all_action.setEnabled(False)
            self._start_next_save()
            return True
        finally:
            self._save_all_preparing = False
            if not self._save_all_running:
                self.busy.end(token)

    def _confirm_save_all(self, requests):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(self.t("Salvar todos os arquivos"))
        dialog.setText(self.t("O salvamento pode demorar. Deseja continuar?"))
        existing = sum(r.overwrite for r in requests)
        dialog.setInformativeText(
            self.t(
                "Serão salvos e validados {count} arquivo(s). {existing} arquivo(s) existente(s) serão substituídos, incluindo originais quando forem o destino atual.\nA barra inferior avança a cada arquivo salvo. Arquivos sem alterações serão mantidos.",
                count=len(requests),
                existing=existing,
            )
        )
        dialog.setDetailedText("\n".join(str(r.target) for r in requests))
        save = dialog.addButton(
            self.t("Salvar todos os arquivos"), QMessageBox.ButtonRole.AcceptRole
        )
        cancel = dialog.addButton(self.t("Cancelar"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        return dialog.clickedButton() == save

    def _start_next_save(self):
        if not self._save_requests:
            self._finish_save_all()
            return
        request = self._save_requests.popleft()
        self.busy.operations[self._save_busy] = "Salvando…"
        self.busy.refresh()
        self.statusBar().showMessage(self.t("Salvando: {name}", name=request.target.name))
        self._save_job = SaveJob(request)
        self._save_job.signals.finished.connect(
            self._save_finished, Qt.ConnectionType.QueuedConnection
        )
        self.save_pool.start(self._save_job)

    @Slot(object)
    def _save_finished(self, result):
        self._save_job = None
        request = result.request
        if result.error:
            self._save_requests.clear()
            self._finish_save_all(
                error=self.t(
                    "{done} de {total} arquivo(s) salvo(s). O lote foi interrompido; os demais arquivos não foram salvos.\n\n{path}\n{error}",
                    done=self._save_all_done,
                    total=self._save_all_count,
                    path=request.target,
                    error=result.error,
                )
            )
            return
        self._record_saved_layer(request.layer, request.target, request.mode)
        self._save_all_done += 1
        self.save_progress.advance(request.target.name)
        QTimer.singleShot(0, self._start_next_save)

    def _finish_save_all(self, *, error=""):
        self._save_all_running = False
        self.save_progress.finish()
        self.busy.end(self._save_busy)
        self._save_busy = None
        self.refresh()
        if error:
            self.show_error("Arquivo não salvo", error)
        else:
            self.statusBar().showMessage(
                self.t("{count} arquivo(s) salvo(s) e validado(s).", count=self._save_all_done),
                20000,
            )
