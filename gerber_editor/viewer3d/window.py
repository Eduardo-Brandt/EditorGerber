"""Independent 3D window with materials, camera controls and worker-built meshes."""

import copy
import logging
from collections import OrderedDict

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QProgressBar,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from gerber_editor.app.metadata import APP_NAME, VERSION
from gerber_editor.core.layer import canonical_function
from gerber_editor.ui.busy import BusyIndicator
from gerber_editor.ui.dialog_helpers import spin
from gerber_editor.ui.icons import icon
from gerber_editor.viewer3d.export_actions import ExportActions
from gerber_editor.viewer3d.exporters import step_available
from gerber_editor.viewer3d.menus import ViewerMenus
from gerber_editor.viewer3d.mesh import build_board, prepare_board
from gerber_editor.viewer3d.viewport import BoardViewport


class MeshSignals(QObject):
    finished = Signal(object, str)
    progress = Signal(int, str)


class MeshJob(QRunnable):
    def __init__(
        self,
        layers,
        thickness,
        cache,
        tolerance,
        geometry=None,
        preparation_cache=None,
        mesh_cache=None,
        compositions=None,
    ):
        super().__init__()
        self.layers, self.thickness, self.cache = layers, thickness, cache
        self.tolerance = tolerance
        self.geometry = geometry
        self.preparation_cache = preparation_cache
        self.mesh_cache = mesh_cache
        self.compositions = compositions
        self.signals = MeshSignals()

    def run(self):
        try:
            if self.geometry is None:
                self.geometry = prepare_board(
                    self.layers,
                    self.cache,
                    self.preparation_cache,
                    self.compositions,
                    self.signals.progress.emit,
                )
            self.signals.finished.emit(
                build_board(
                    self.geometry,
                    self.thickness,
                    None,
                    self.tolerance,
                    self.mesh_cache,
                    self.signals.progress.emit,
                ),
                "",
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("3D mesh generation failed")
            self.signals.finished.emit(None, str(exc))


class Viewer3DWindow(ViewerMenus, ExportActions, QMainWindow):
    MESH_CACHE_BYTES = 128 * 1024 * 1024

    def __init__(self, editor):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowIcon(editor.windowIcon())
        self.editor, self.locale = editor, editor.locale
        self.t = self.locale
        self._revision = 0
        self._mesh_revision = -1
        self._job_revision = None
        self._job_settings = None
        self._mesh_settings = None
        self._geometry = None
        self._document_state = self._document_signature()
        self._preparation_cache = {}
        self._build_cache = {}
        self._mesh_cache = OrderedDict()
        self._dirty = True
        self._closing = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_if_dirty)
        t = self.locale
        self.setWindowTitle(f"{APP_NAME} {VERSION} — {t('Visualizador 3D')}")
        self.resize(1200, 780)
        self.viewport = BoardViewport()
        self.setCentralWidget(self.viewport)
        self.viewport.failure.connect(self._gl_failure)
        self._export_job = None
        file_menu = self.menuBar().addMenu("")
        self.locale.bind(file_menu, "&Arquivo", "setTitle")
        self.export_actions = []
        for label, callback in (
            ("Exportar imagem JPG", self.export_jpg),
            ("Exportar STEP com cores", lambda: self.export_model("step")),
            ("Exportar WRL com cores", lambda: self.export_model("wrl")),
        ):
            action = QAction(self)
            self.locale.bind(action, label)
            action.triggered.connect(callback)
            action.setEnabled(False)
            file_menu.addAction(action)
            self.export_actions.append(action)
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self.reload_action = QAction(icon("3d"), t("Atualizar PCB"), self)
        self.locale.bind(self.reload_action, "Atualizar PCB")
        self.reload_action.triggered.connect(self._force_rebuild)
        toolbar.addAction(self.reload_action)
        self.view_actions = []
        for label, view in (
            ("Superior", "top"),
            ("Inferior", "bottom"),
            ("Isométrica", "iso"),
            ("Frente", "front"),
            ("Direita", "right"),
        ):
            action = QAction(t(label), self)
            self.locale.bind(action, label)
            action.triggered.connect(
                lambda checked=False, name=view: self.viewport.standard_view(name)
            )
            toolbar.addAction(action)
            self.view_actions.append(action)
        fit = QAction(icon("fit"), t("Enquadrar camadas"), self)
        self.locale.bind(fit, "Enquadrar camadas")
        fit.triggered.connect(self.viewport.fit_all)
        toolbar.addAction(fit)
        self.fit_action = fit
        flip = QAction(self)
        self.locale.bind(flip, "Inverter placa")
        flip.setShortcut("F")
        flip.triggered.connect(lambda: self.viewport.flip_board())
        toolbar.addAction(flip)
        self.flip_action = flip
        realistic = QCheckBox()
        self.locale.bind(realistic, "Realista")
        realistic.setChecked(True)
        realistic.toggled.connect(self._realistic)
        toolbar.addWidget(realistic)
        self.realistic_checkbox = realistic
        perspective = QCheckBox(t("Perspectiva"))
        self.locale.bind(perspective, "Perspectiva")
        perspective.setChecked(True)
        perspective.toggled.connect(self._perspective)
        toolbar.addWidget(perspective)
        self.perspective_checkbox = perspective
        toolbar.addSeparator()
        toolbar.addWidget(self.locale.bind(QLabel(), "Espessura PCB"))
        unit = editor.display_unit
        self.thickness = spin(
            unit.from_mm(1.6), float(unit.from_mm(0.1)), float(unit.from_mm(20)), unit
        )
        toolbar.addWidget(self.thickness)
        self.thickness.editingFinished.connect(self._settings_changed)
        toolbar.addWidget(self.locale.bind(QLabel(), "Detalhe 3D"))
        self.detail = QComboBox()
        for label, tolerance in (("Fino", 0.01), ("Normal", 0.025), ("Rápido", 0.1)):
            self.detail.addItem(t(label), tolerance)
        self.detail.setCurrentIndex(1)
        self.detail.currentIndexChanged.connect(self._settings_changed)
        toolbar.addWidget(self.detail)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([t("Camadas e materiais")])
        self.tree.itemChanged.connect(self._visibility)
        dock = QDockWidget(t("Camadas e materiais"), self)
        self.locale.bind(dock, "Camadas e materiais", "setWindowTitle")
        dock.setWidget(self.tree)
        self.material_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMaximumWidth(260)
        self.progress.setMinimumWidth(180)
        self.progress.setFormat("%p%")
        self.progress.setObjectName("pcb3dProgress")
        self.statusBar().addPermanentWidget(self.progress)
        self.progress.hide()
        self.busy = BusyIndicator(self.locale, self)
        self.statusBar().addPermanentWidget(self.busy)
        self._mesh_busy_token = None
        self._export_busy_token = None
        self.statusBar().showMessage(
            t(
                "Arraste para orbitar; botão central/direito desloca; scroll aproxima; Home enquadra."
            )
        )
        self._job = None
        self._mesh_message = "Gerando PCB 3D…"
        self.last_error = ""
        self.build_menus()

    def retranslate(self):
        self.setWindowTitle(f"{APP_NAME} {VERSION} — {self.locale('Visualizador 3D')}")
        self.tree.setHeaderLabels([self.locale("Camadas e materiais")])
        for action in self.language_group.actions():
            action.setChecked(action.data() == self.locale.language)
        for index, label in enumerate(("Fino", "Normal", "Rápido")):
            self.detail.setItemText(index, self.locale(label))
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.data(0, Qt.ItemDataRole.UserRole) == "substrate":
                item.setText(0, self.locale("Substrato FR4"))
        if self._job:
            self.statusBar().showMessage(self.locale(self._mesh_message))
        elif self.viewport.mesh:
            self._mesh_status(self.viewport.mesh)

    def _perspective(self, checked):
        self.viewport.perspective = checked
        if hasattr(self, "perspective_action"):
            self.perspective_action.setChecked(checked)
        self.viewport.update()

    def _realistic(self, checked):
        self.viewport.realistic = checked
        if hasattr(self, "realistic_action"):
            self.realistic_action.setChecked(checked)
        self.viewport.update()

    def _update_export_actions(self):
        available = (
            self.viewport.mesh is not None
            and not self._dirty
            and not self._job
            and not self._export_job
        )
        for action in self.export_actions:
            action.setEnabled(available)
        self.export_actions[1].setEnabled(available and step_available())
        if not step_available():
            self.export_actions[1].setToolTip(
                self.locale("Suporte STEP não instalado nesta instalação.")
            )

    def set_units(self, unit):
        value = self.thickness.mm
        self.thickness.blockSignals(True)
        self.thickness.setRange(float(unit.from_mm(0.1)), float(unit.from_mm(20)))
        self.thickness.blockSignals(False)
        self.thickness.set_unit(unit)
        self.thickness.set_mm(value)

    def _document_signature(self):
        records = []
        for layer in self.editor.layers:
            if not layer.objects:
                continue
            role = canonical_function(layer.function)
            records.append(
                (
                    layer.id,
                    layer.name,
                    role,
                    layer.visible,
                    layer.attributes,
                    layer.signature(),
                )
            )
        # Stack order, color, opacity and interface language only affect the 2D.
        return tuple(sorted(records, key=lambda record: record[0]))

    def mark_dirty(self, *, force=False):
        state = self._document_signature()
        if not force and state == self._document_state:
            return
        self._document_state = state
        self._revision += 1
        self._dirty = True
        self._geometry = None
        self._mesh_cache.clear()
        self.reload_action.setEnabled(self._job is None and self._export_job is None)
        self._update_export_actions()

    def _settings(self):
        return float(self.thickness.mm), self.detail.currentData()

    def _settings_changed(self):
        # Detail and thickness reuse the composed PCB. Only document edits
        # invalidate that geometry and the meshes derived from it.
        self._dirty = (
            self._mesh_revision != self._revision or self._mesh_settings != self._settings()
        )
        self._update_export_actions()
        self.request_refresh()

    def _force_rebuild(self):
        self.mark_dirty(force=True)
        self.rebuild()

    def request_refresh(self):
        """Coalesce activation events; editing the document never starts a build."""
        if not self._closing and not self._refresh_timer.isActive():
            self._refresh_timer.start(0)

    def _refresh_if_dirty(self):
        if self._closing or not self.isVisible() or not self.isActiveWindow() or not self._dirty:
            return
        # Do not snapshot a document midway through a synchronous GUI edit.
        if self.editor.busy.operations:
            self._refresh_timer.start(80)
            return
        if not self._job and not self._export_job:
            self.rebuild()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.WindowActivate and hasattr(self, "_refresh_timer"):
            self.request_refresh()
        return result

    def showEvent(self, event):
        self._closing = False
        super().showEvent(event)
        self.busy.refresh()
        self.request_refresh()

    def closeEvent(self, event):
        # Closing hides this reusable window; workers retain their signal receivers.
        self._closing = True
        self._refresh_timer.stop()
        self.busy.timer.stop()
        self.busy.overlay.hide()
        super().closeEvent(event)

    def rebuild(self):
        if self._job or self._export_job:
            return
        if not any(layer.objects for layer in self.editor.layers):
            self.viewport.set_mesh(None)
            self.tree.clear()
            self._mesh_revision = self._revision
            self._mesh_settings = self._settings()
            self._preparation_cache = {}
            self._build_cache = {}
            self._dirty = False
            self.last_error = ""
            self._update_export_actions()
            self.statusBar().showMessage(
                self.locale("Abra as camadas da PCB para visualizar em 3D.")
            )
            return
        settings = self._settings()
        if settings in self._mesh_cache:
            mesh = self._mesh_cache[settings]
            self._mesh_cache.move_to_end(settings)
            self._show_mesh(mesh, settings)
            return
        layers = []
        if self._geometry is None:
            for layer in self.editor.layers:
                snapshot = copy.copy(layer)
                snapshot.objects = list(layer.objects)
                layers.append(snapshot)
        self._job_revision = self._revision
        self._job_settings = settings
        self._dirty = True
        self._job = MeshJob(
            layers,
            settings[0],
            dict(self.editor.canvas.renderer._objects) if self._geometry is None else {},
            settings[1],
            self._geometry,
            self._preparation_cache,
            self._build_cache,
            self.editor.canvas.renderer.geometry_snapshot(layers) if self._geometry is None else {},
        )
        self._job.signals.finished.connect(self._ready, Qt.ConnectionType.QueuedConnection)
        self._job.signals.progress.connect(self._mesh_progress, Qt.ConnectionType.QueuedConnection)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.show()
        self._mesh_message = (
            "Atualizando visualização 3D…" if self._geometry is not None else "Gerando PCB 3D…"
        )
        self._mesh_busy_token = self.busy.begin(self._mesh_message)
        self.reload_action.setEnabled(False)
        self._update_export_actions()
        self.statusBar().showMessage(self.locale(self._mesh_message))
        QThreadPool.globalInstance().start(self._job)

    def _mesh_progress(self, value, label):
        if self._job is not None:
            self.progress.setToolTip(self.locale(label))
            self.statusBar().showMessage(self.locale(label))
            self.progress.setValue(max(self.progress.value(), value))

    def _ready(self, mesh, error):
        revision = self._job_revision
        settings = self._job_settings
        geometry = self._job.geometry
        self._job = None
        self._job_revision = None
        self._job_settings = None
        if not error:
            self.progress.setValue(100)
        self.progress.hide()
        self.busy.end(self._mesh_busy_token)
        self._mesh_busy_token = None
        self.reload_action.setEnabled(True)
        self._update_export_actions()
        if revision != self._revision:
            # An older document snapshot must not repopulate any of the caches.
            self.request_refresh()
            return
        self.last_error = error
        if error:
            self.statusBar().showMessage(self.locale.error(error))
            if settings != self._settings():
                self.request_refresh()
            return
        self._geometry = geometry
        self._preparation_cache = geometry._cache
        self._build_cache = mesh._cache
        self._mesh_cache[settings] = mesh
        self._mesh_cache.move_to_end(settings)
        while len(self._mesh_cache) > 3 or (
            len(self._mesh_cache) > 1
            and sum(
                part.vertices.nbytes
                for cached in self._mesh_cache.values()
                for part in cached.parts
            )
            > self.MESH_CACHE_BYTES
        ):
            self._mesh_cache.popitem(last=False)
        if self._closing or settings != self._settings():
            # Keep a completed detail for reuse, but display only current settings.
            self.request_refresh()
            return
        self._show_mesh(mesh, settings)

    def _show_mesh(self, mesh, settings):
        self.viewport.set_mesh(mesh)
        self._build_cache = mesh._cache
        self._mesh_revision = self._revision
        self._mesh_settings = settings
        self._dirty = False
        self.last_error = ""
        self._update_export_actions()
        self.tree.blockSignals(True)
        self.tree.clear()
        seen = set()
        for part in mesh.parts:
            if part.key in seen:
                continue
            seen.add(part.key)
            item = QTreeWidgetItem([self.locale(part.name)])
            item.setData(0, Qt.ItemDataRole.UserRole, part.key)
            item.setCheckState(
                0,
                Qt.CheckState.Unchecked
                if part.key in self.viewport.hidden
                else Qt.CheckState.Checked,
            )
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self._mesh_status(mesh)

    def _mesh_status(self, mesh):
        message = (
            self.locale(
                "Contorno estimado pelos limites. Defina uma camada Edge.Cuts para usar o contorno real."
            )
            if mesh.estimated_outline
            else self.locale("Contorno da camada Edge.Cuts")
        )
        self.statusBar().showMessage(
            message + f" · {mesh.triangles:,} " + self.locale("triângulos")
        )

    def _visibility(self, item, column):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if item.checkState(0) == Qt.CheckState.Checked:
            self.viewport.hidden.discard(key)
        else:
            self.viewport.hidden.add(key)
        self.viewport.update()

    def _gl_failure(self, error):
        self.last_error = error
        self.statusBar().showMessage(error)
