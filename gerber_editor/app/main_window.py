"""Desktop document controller with separate file, drawing and preference modules."""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gerber_editor.app.drawing_actions import DrawingActions
from gerber_editor.app.edit_actions import EditActions
from gerber_editor.app.fabrication_actions import FabricationActions
from gerber_editor.app.file_actions import FileActions
from gerber_editor.app.i18n import Locale, install_qt_locale
from gerber_editor.app.metadata import APP_NAME, REPORT_PROBLEM_URL, VERSION
from gerber_editor.app.preference_actions import PreferenceActions
from gerber_editor.app.preferences import Preferences
from gerber_editor.commands.edit_commands import (
    AddObjects,
    CompositeCommand,
    DeleteObjects,
    LayerProperty,
    ReorderLayers,
    ReplaceObjects,
)
from gerber_editor.commands.undo_stack import UndoStack
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.project import Project
from gerber_editor.core.units import Unit
from gerber_editor.geometry.rigid import RigidTransform
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.gerber.writer import GerberWriter
from gerber_editor.graphics.canvas import Canvas
from gerber_editor.tools.shapes import layer_quantum
from gerber_editor.ui.about_dialog import AboutDialog
from gerber_editor.ui.busy import BusyIndicator
from gerber_editor.ui.chrome import WorkspaceChrome
from gerber_editor.ui.layer_panel import LayerPanel
from gerber_editor.ui.property_panel import PropertyPanel
from gerber_editor.ui.translation_dialog import TranslationDialog


class MainWindow(
    FileActions, DrawingActions, EditActions, FabricationActions, PreferenceActions, QMainWindow
):
    def __init__(self, settings_path: Path | None = None, language=None):
        super().__init__()
        self.setAcceptDrops(True)
        from gerber_editor.ui.branding import application_icon

        self.setWindowIcon(application_icon())
        self.preferences = Preferences(settings_path)
        self.locale = Locale(language or self.preferences.data["language"])
        install_qt_locale(self.locale.language)
        self.t = self.locale
        self.display_unit = Unit(self.preferences.data["units"])
        self.drawing_width_mm = Decimal("0.2")
        self._pending_edit = None
        self._viewer3d = None
        self._help_dialog = None
        self.resize(1440, 900)
        self.project = Project()
        self.active_layer: GerberLayer | None = None
        self.parser, self.writer = GerberParser(), GerberWriter()
        self.original_paths, self.save_modes = {}, {}
        self.approved_overwrites = set()
        self.history = UndoStack(self.refresh)
        self.import_pool = QThreadPool(self)
        self.import_pool.setMaxThreadCount(1)
        self._import_jobs, self._job_busy = {}, {}
        self._import_progress_jobs = set()
        self._cancelled_imports = set()
        self._import_queue = deque()
        self._import_active = None
        self._import_errors = []
        self._import_skipped = []
        self._import_prepared = []
        self._applying_import = False
        self._job_counter = 0
        self.save_pool = QThreadPool(self)
        self.save_pool.setMaxThreadCount(1)
        self._save_all_running = self._save_all_preparing = False
        self._save_job = self._save_busy = None
        directory = self.preferences.data["last_directory"]
        self.last_directory = (
            directory if directory and Path(directory).is_dir() else str(Path.cwd())
        )
        self.busy = BusyIndicator(self.locale, self)
        self.canvas = Canvas()
        # Let the editor open files dropped over the drawing, instead of the scene.
        self.canvas.setAcceptDrops(False)
        self.canvas.processing_pulse = self.busy.pulse
        self.canvas.renderer.processing_pulse = self.busy.pulse
        self.canvas.units = self.display_unit
        self.canvas.grid_mm = Decimal(self.preferences.data["grid_mm"])
        for key in (
            "full_cursor",
            "polar",
            "ghost_negatives",
            "grid_visible",
            "snap_grid",
            "snap_points",
            "ortho_angle",
        ):
            setattr(self.canvas, key, self.preferences.data[key])
        background = QColor(self.preferences.data["background"])
        self.canvas.setBackgroundBrush(background if background.isValid() else QColor("black"))
        self.setCentralWidget(self.canvas)
        self.layer_panel = LayerPanel(self.locale)
        self.properties = PropertyPanel(self.locale)
        self.properties.unit = self.display_unit
        self.manager_tabs = QTabWidget()
        self.manager_tabs.setObjectName("layerManagerTabs")
        self.manager_tabs.addTab(self.layer_panel, self.t("Camadas"))
        self.items_panel = QWidget()
        self.manager_tabs.addTab(self.items_panel, self.t("Itens"))
        self.manager_tabs.addTab(self.properties, self.t("Propriedades"))
        self.layer_dock = QDockWidget(self)
        self.locale.bind(self.layer_dock, "Gestor das camadas", "setWindowTitle")
        self.layer_dock.setObjectName("layerManagerDock")
        self.layer_dock.setWidget(self.manager_tabs)
        self.layer_dock.setMinimumWidth(310)
        self.layer_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)
        self.resizeDocks([self.layer_dock], [330], Qt.Orientation.Horizontal)
        self.layer_panel.activeChanged.connect(self._active_changed)
        self.layer_panel.propertyRequested.connect(self._layer_property)
        self.layer_panel.closeRequested.connect(self.close_layer)
        self.layer_panel.moveRequested.connect(self._move_layer)
        self.canvas.selectionUpdated.connect(self._selection_changed)
        self.canvas.lineCreated.connect(self._line_created)
        self.canvas.shapeRequested.connect(self._shape_requested)
        self.canvas.textRequested.connect(self._text_requested)
        self.canvas.fiducialRequested.connect(self.insert_fiducial)
        self.canvas.operationPending.connect(self.busy.pending)
        self.canvas.placementCommitted.connect(self._commit_placement)
        self.canvas.placementCancelled.connect(self._cancel_edit)
        self.canvas.pointPicked.connect(self._point_picked)
        self.canvas.dragStarted.connect(lambda anchor: self.start_move(anchor=anchor))
        self.properties.editRequested.connect(self.edit_properties)
        self.canvas.editRequested.connect(self.edit_properties)
        self.chrome = WorkspaceChrome(self)
        self.chrome.build()
        self.width_input.valueChanged.connect(self._width_changed)
        self._build_items_panel()
        self.canvas.modeChanged.connect(self._mode_changed)
        self.canvas.measurementChanged.connect(self.chrome.show_measurement)
        self.canvas.distanceMeasured.connect(self.chrome.show_measurement)
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().dataChanged.connect(self._clipboard_changed)
        self.refresh()

    def _clipboard_changed(self):
        from PySide6.QtWidgets import QApplication

        from gerber_editor.tools.clipboard import MIME_TYPE

        mime = QApplication.clipboard().mimeData()
        self.paste_action.setEnabled(bool(self.active_layer and mime and mime.hasFormat(MIME_TYPE)))

    @property
    def layers(self):
        return self.project.board.layers

    def refresh(self):
        if self.active_layer not in self.layers:
            self.active_layer = self.layers[-1] if self.layers else None
        self.canvas.active_layer_id = self.active_layer.id if self.active_layer else None
        self.canvas.quantum_mm = (
            layer_quantum(self.active_layer) if self.active_layer else Decimal("0.000001")
        )
        self.canvas.rebuild(self.layers)
        self.layer_panel.refresh(self.layers, self.canvas.active_layer_id)
        self.chrome.refresh()
        self.undo_action.setEnabled(self.history.can_undo)
        self.redo_action.setEnabled(self.history.can_redo)
        for action in (self.save_action, self.save_as_action, self.close_action):
            action.setEnabled(self.active_layer is not None)
        self.close_all_action.setEnabled(bool(self.layers or self._import_jobs))
        self.save_all_action.setEnabled(
            bool(self.layers) and not self._import_jobs and not self._save_all_running
        )
        if self._save_all_running:
            self.close_all_action.setEnabled(False)
        self.count_label.setText(
            self.t(
                "{layers} camada(s) · {objects} objetos",
                layers=len(self.layers),
                objects=sum(len(layer.objects) for layer in self.layers),
            )
        )
        modified = any(layer.modified for layer in self.layers)
        file_name = self.active_layer.name + " — " if self.active_layer else ""
        self.setWindowTitle(f"{file_name}{APP_NAME} {VERSION}{' *' if modified else ''}")
        for index, title in enumerate(("Camadas", "Itens", "Propriedades")):
            self.manager_tabs.setTabText(index, self.t(title))
        self._selection_changed()
        self._clipboard_changed()
        if self._viewer3d:
            self._viewer3d.mark_dirty()

    def _active_changed(self, layer):
        self.canvas.set_mode("select")
        self.active_layer = layer
        self.canvas.active_layer_id = layer.id if layer else None
        self.canvas.set_active_layer(self.canvas.active_layer_id)
        self.canvas.quantum_mm = layer_quantum(layer) if layer else Decimal("0.000001")
        self.canvas.clear_selection()
        self.save_action.setEnabled(layer is not None)
        self.save_as_action.setEnabled(layer is not None)
        self.close_action.setEnabled(layer is not None)
        self.layer_panel.refresh(self.layers, self.canvas.active_layer_id)
        self.chrome.refresh()

    def show_error(self, title, error):
        QMessageBox.warning(self, self.t(title), self.locale.error(str(error)))

    def _layer_property(self, layer, name, value):
        with self.busy.operation("Atualizando geometria…"):
            self.history.push(LayerProperty(layer, name, value))

    def _move_layer(self, layer_id, direction):
        index = next((i for i, layer in enumerate(self.layers) if layer.id == layer_id), None)
        if index is None or direction not in (-1, 1):
            return
        # Buttons use list/display direction; the model stores back-to-front.
        target = index - direction
        if not 0 <= target < len(self.layers):
            return
        ordered = list(self.layers)
        ordered.insert(target, ordered.pop(index))
        self.canvas.set_mode("select")
        self.history.push(ReorderLayers(self.layers, ordered))

    def _selection_changed(self):
        items = self.canvas.selected_objects()
        self.properties.show_objects(items)
        if hasattr(self, "delete_action"):
            for action in (
                self.delete_action,
                self.move_action,
                self.copy_action,
                self.cut_action,
                self.duplicate_action,
                self.mirror_action,
                self.array_action,
            ):
                action.setEnabled(bool(items))
        if hasattr(self, "group_action"):
            groups = {item.obj.group_id for item in items}
            already_grouped = len(groups) == 1 and None not in groups
            self.group_action.setEnabled(
                len(items) > 1
                and len({item.layer.id for item in items}) == 1
                and not already_grouped
            )
            self.ungroup_action.setEnabled(any(item.obj.group_id for item in items))

    def delete_selection(self):
        targets = [
            (layer, {obj.id for obj in objects}) for layer, objects in self.selected_in_order()
        ]
        targets = [(layer, ids) for layer, ids in targets if ids]
        if targets:
            with self.busy.operation("Atualizando geometria…"):
                self.history.push(DeleteObjects(targets))
            self.statusBar().showMessage(
                self.t(
                    "{count} objetos excluídos · Ctrl+Z desfaz",
                    count=sum(len(ids) for _, ids in targets),
                ),
                7000,
            )

    def undo_edit(self):
        self.canvas.set_mode("select")
        with self.busy.operation("Atualizando geometria…"):
            self.history.undo()

    def redo_edit(self):
        self.canvas.set_mode("select")
        with self.busy.operation("Atualizando geometria…"):
            self.history.redo()

    def translate_selection(self, copy=False):
        if self.canvas.selected_objects():
            dialog = TranslationDialog(copy, self)
            if dialog.exec():
                self.translate_selected(*dialog.values(), copy=copy)

    def translate_selected(self, dx: Decimal, dy: Decimal, *, copy=False):
        selected = self.canvas.selected_objects()
        if not selected or (dx == 0 and dy == 0 and not copy):
            return
        with self.busy.operation("Atualizando geometria…"):
            changes = []
            for layer in self.layers:
                replacements = {}
                groups = {}
                for item in selected:
                    if item.layer is layer:
                        obj = RigidTransform(dx=dx, dy=dy).object(
                            item.obj, layer_quantum(layer), clone=copy, group_ids=groups
                        )
                        replacements[item.obj.id] = obj
                if replacements:
                    changes.append((layer, replacements))
            if copy:
                commands = [
                    AddObjects(
                        layer,
                        [values[obj.id] for obj in layer.objects if obj.id in values],
                        "Copiar objetos",
                    )
                    for layer, values in changes
                ]
                self.history.push(CompositeCommand(commands, "Copiar objetos"))
            else:
                self.history.push(ReplaceObjects(changes))

    def show_properties(self):
        self.manager_tabs.setCurrentWidget(self.properties)

    def _build_items_panel(self):
        layout = QVBoxLayout(self.items_panel)
        for action in (
            self.grid_action,
            self.axes_action,
            self.snap_action,
            self.snap_points_action,
            self.full_cursor_action,
            self.polar_action,
            self.ghost_action,
        ):
            checkbox = self.locale.bind(QCheckBox(), action.property("sourceText"))
            checkbox.setChecked(action.isChecked())
            checkbox.toggled.connect(
                lambda checked, a=action: a.trigger() if checked != a.isChecked() else None
            )
            action.toggled.connect(checkbox.setChecked)
            layout.addWidget(checkbox)
        hint = self.locale.bind(
            QLabel(), "As opções de visualização não alteram os dados exportados."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def show_help(self, checked=False, *, section="start"):
        from gerber_editor.ui.help_dialog import HelpDialog

        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self)
        self._help_dialog.open_section(section)

    def report_problem(self, checked=False):
        if not QDesktopServices.openUrl(QUrl(REPORT_PROBLEM_URL)):
            self.show_error(
                "Relatar problemas",
                self.t(
                    "Não foi possível abrir o navegador. Acesse:\n{url}", url=REPORT_PROBLEM_URL
                ),
            )

    def help_text(self):
        from PySide6.QtGui import QTextDocument

        from gerber_editor.ui.help_dialog import help_html

        document = QTextDocument()
        document.setHtml(help_html(self))
        return document.toPlainText()

    def about(self):
        AboutDialog(self).exec()

    def show_support(self):
        from gerber_editor.ui.support_dialog import SupportDialog

        SupportDialog(self).exec()

    def show_splash(self):
        from gerber_editor.ui.splash import SplashScreen

        self._help_splash = SplashScreen(self.locale, dismiss_on_click=True)
        self._help_splash.supportRequested.connect(self.show_support)
        self._help_splash.show()

    def show_3d(self):
        if not self.layers:
            self.statusBar().showMessage(
                self.t("Abra as camadas da PCB para visualizar em 3D."), 6000
            )
            return
        from gerber_editor.viewer3d.window import Viewer3DWindow

        if self._viewer3d is None:
            self._viewer3d = Viewer3DWindow(self)
        if self._viewer3d.isVisible():
            self._viewer3d.show()
        else:
            self._viewer3d.showMaximized()
        self._viewer3d.raise_()
        self._viewer3d.activateWindow()
        self._viewer3d.request_refresh()

    def closeEvent(self, event):
        if self._save_all_running or self._save_all_preparing:
            event.ignore()
            return
        if not self._confirm_close(self.layers):
            event.ignore()
            return
        self.cancel_imports()
        if self._viewer3d:
            self._viewer3d.close()
        if self._help_dialog:
            self._help_dialog.close()
        self.canvas.set_mode("select")
        event.accept()
