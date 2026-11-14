"""Localized CAD chrome with stable, persistent action identifiers."""

import math
from decimal import Decimal

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QLabel,
    QToolBar,
    QWidget,
)

from gerber_editor.core.units import vector_text
from gerber_editor.ui.file_progress import FileProgress
from gerber_editor.ui.icons import icon
from gerber_editor.ui.tool_palette import ToolPalette


class WorkspaceChrome:
    def __init__(self, window):
        self.window = window
        self.actions = {}
        self.cursor = (0.0, 0.0)
        self.measurement = None

    def action(self, key, title, callback, shortcut="", checkable=False, glyph=None):
        w = self.window
        action = QAction(w)
        action.setObjectName(key)
        action.setProperty("sourceText", title)
        action.setProperty("defaultShortcut", shortcut)
        action.setCheckable(checkable)
        w.locale.bind(action, title)
        action.setShortcut(QKeySequence(w.preferences.data["shortcuts"].get(key, shortcut)))
        if glyph:
            action.setIcon(icon(glyph))
        action.triggered.connect(callback)
        self.actions[key] = action
        return action

    def menu(self, title, parent=None):
        parent = parent or self.window.menuBar()
        menu = parent.addMenu("")
        self.window.locale.bind(menu, title, "setTitle")
        return menu

    def label(self, text):
        return self.window.locale.bind(QLabel(), text)

    def build(self):
        self.menus()
        self.toolbars()
        self.status()
        self.refresh_tooltips()

    def menus(self):
        w = self.window
        file = self.menu("&Arquivo")
        w.open_action = self.action(
            "file.open", "Abrir Gerber…", w.open_dialog, "Ctrl+O", glyph="open"
        )
        w.folder_action = self.action("file.folder", "Abrir pasta de Gerbers…", w.open_folder)
        w.save_action = self.action("file.save", "Salvar", w.save_current, "Ctrl+S", glyph="save")
        w.save_as_action = self.action(
            "file.save_as", "Salvar como…", w.save_as, "Ctrl+Shift+S", glyph="save_as"
        )
        w.save_all_action = self.action(
            "file.save_all", "Salvar todos os arquivos", w.save_all, glyph="save_all"
        )
        w.close_action = self.action("file.close", "Fechar arquivo", w.close_active, "Ctrl+W")
        w.close_all_action = self.action(
            "file.close_all",
            "Fechar todos os arquivos",
            w.close_all,
            "Ctrl+Shift+W",
            glyph="close_all",
        )
        file.addActions(
            [
                w.open_action,
                w.folder_action,
                self.action("file.new", "Nova camada…", w.new_layer, "Ctrl+N"),
                w.save_action,
                w.save_as_action,
                w.save_all_action,
                w.close_action,
                w.close_all_action,
            ]
        )
        file.addSeparator()
        file.addAction(self.action("file.demo", "Abrir demonstração", w.load_demo))
        file.addAction(self.action("file.exit", "Sair", w.close, "Alt+F4"))
        edit = self.menu("&Editar")
        w.undo_action = self.action("edit.undo", "Desfazer", w.undo_edit, "Ctrl+Z", glyph="undo")
        w.redo_action = self.action("edit.redo", "Refazer", w.redo_edit, "Ctrl+Y", glyph="redo")
        w.delete_action = self.action(
            "edit.delete", "Excluir seleção", w.delete_selection, "Delete", glyph="delete"
        )
        w.move_action = self.action("edit.move", "Mover pelo cursor", w.start_move, "M")
        w.copy_action = self.action("edit.copy", "Copiar", w.copy_clipboard, "Ctrl+C")
        w.paste_action = self.action("edit.paste", "Colar pelo cursor", w.paste_clipboard, "Ctrl+V")
        w.cut_action = self.action("edit.cut", "Recortar", w.cut_clipboard, "Ctrl+X")
        w.duplicate_action = self.action(
            "edit.duplicate", "Duplicar pelo cursor", w.start_duplicate, "Ctrl+D"
        )
        w.mirror_action = self.action("edit.mirror", "Cópia espelhada…", w.mirror_copy)
        w.array_action = self.action("edit.array", "Matriz de cópias…", w.copy_array)
        w.group_action = self.action("edit.group", "Agrupar objetos", w.group_selection, "Ctrl+G")
        w.ungroup_action = self.action(
            "edit.ungroup", "Desagrupar objetos", w.ungroup_selection, "Ctrl+Shift+G"
        )
        edit.addActions(
            [
                w.undo_action,
                w.redo_action,
                w.delete_action,
                w.move_action,
                w.copy_action,
                w.cut_action,
                w.paste_action,
                w.duplicate_action,
                w.mirror_action,
                w.array_action,
                w.group_action,
                w.ungroup_action,
                self.action(
                    "edit.offset", "Mover por deslocamento…", lambda: w.translate_selection(False)
                ),
                self.action("edit.select_all", "Selecionar todos", w.canvas.select_all, "Ctrl+A"),
                self.action(
                    "edit.clear_selection",
                    "Limpar seleção",
                    w.canvas.clear_selection,
                ),
            ]
        )
        self.edit_actions = edit.actions()
        for action in self.edit_actions:
            action.setIcon(icon(action.objectName().removeprefix("edit.")))
        view = self.menu("&Visualizar")
        w.fit_action = self.action(
            "view.fit", "Enquadrar camadas", w.canvas.fit_all, "Home", glyph="fit"
        )
        w.zoom_in_action = self.action(
            "view.zoom_in", "Aproximar", lambda: w.canvas.zoom_by(1.4), "F1", glyph="zoom_in"
        )
        w.zoom_out_action = self.action(
            "view.zoom_out", "Afastar", lambda: w.canvas.zoom_by(1 / 1.4), "F2", glyph="zoom_out"
        )
        w.grid_action = self.action("view.grid", "Grade", w._toggle_grid, "G", True, "grid")
        w.grid_action.setChecked(w.canvas.grid_visible)
        w.axes_action = self.action(
            "view.axes", "Eixos de origem", w._toggle_axes, checkable=True, glyph="axes"
        )
        w.axes_action.setChecked(w.canvas.axes_visible)
        w.snap_action = self.action(
            "view.snap", "Snap à grade", w._toggle_snap, checkable=True, glyph="snap"
        )
        w.snap_action.setChecked(w.canvas.snap_grid)
        w.snap_points_action = self.action(
            "view.snap_points",
            "Snap a extremidades e pontos",
            w._toggle_snap_points,
            "Ctrl+Shift+P",
            True,
            "snap_points",
        )
        w.snap_points_action.setChecked(w.canvas.snap_points)
        w.full_cursor_action = self.action(
            "view.full_cursor",
            "Cursor de tela inteira",
            w._toggle_full_cursor,
            "Ctrl+Shift+X",
            True,
            "crosshair",
        )
        w.full_cursor_action.setChecked(w.canvas.full_cursor)
        w.polar_action = self.action(
            "view.polar", "Coordenadas polares", w._toggle_polar, checkable=True, glyph="polar"
        )
        w.polar_action.setChecked(w.canvas.polar)
        w.ghost_action = self.action(
            "view.ghost",
            "Negativos em cor fantasma",
            w._toggle_ghost,
            checkable=True,
            glyph="negative",
        )
        w.ghost_action.setChecked(w.canvas.ghost_negatives)
        view.addActions(
            [
                w.fit_action,
                self.action("view.fit_selection", "Enquadrar seleção", w.canvas.fit_selection),
                w.zoom_in_action,
                w.zoom_out_action,
                w.grid_action,
                w.axes_action,
                w.full_cursor_action,
                w.polar_action,
                w.ghost_action,
            ]
        )
        w.properties_action = self.action(
            "edit.properties", "Propriedades da seleção", w.show_properties, "E"
        )
        view.addAction(w.properties_action)
        w.viewer3d_action = self.action(
            "view.3d", "Visualizador 3D", w.show_3d, "Alt+3", glyph="3d"
        )
        view.addAction(w.viewer3d_action)
        tools = self.menu("&Ferramentas")
        w.mode_group = QActionGroup(w)
        for name, title, key, glyph in [
            ("select", "Selecionar", "", "select"),
            ("measure", "Medir distância", "Shift+A", "measure"),
            ("line", "Desenhar linha", "Ctrl+Shift+L", "line"),
            ("arc", "Desenhar arco", "Ctrl+Shift+A", "arc"),
            ("circle", "Desenhar círculo", "Ctrl+Shift+C", "circle"),
            ("rectangle", "Desenhar retângulo", "", "rectangle"),
            ("square", "Desenhar quadrado", "", "square"),
            ("text", "Inserir texto vetorial", "Ctrl+Shift+T", "text"),
            ("dimension", "Inserir cota", "Ctrl+Shift+H", "dimension"),
            ("fiducial", "Inserir fiducial", "", "fiducial"),
        ]:
            action = self.action(
                "tool." + name,
                title,
                lambda checked=False, mode=name: w.set_tool(mode),
                key,
                True,
                glyph,
            )
            setattr(w, name + "_action", action)
            w.mode_group.addAction(action)
            tools.addAction(action)
        w.select_action.setChecked(True)
        w.import_graphic_action = self.action(
            "tool.import_graphic",
            "Importar gráfico P&B…",
            w.import_graphic,
            "Ctrl+Shift+F",
            glyph="image",
        )
        tools.addActions(
            [
                w.import_graphic_action,
                w.snap_action,
                w.snap_points_action,
                self.action("tool.validate", "Validar camada ativa", w.validate_active),
                self.action(
                    "tool.cutouts",
                    "Recortes e rasgos da seleção…",
                    w.cutouts_from_selection,
                    glyph="cutout",
                ),
                self.action("tool.routing_layer", "Nova camada de recortes", w.new_routing_layer),
            ]
        )
        ortho = self.menu("Ortho com Shift", tools)
        self.ortho_group = QActionGroup(w)
        for angle in (45, 90):
            action = self.action(
                "ortho." + str(angle),
                f"{angle}°",
                lambda checked=False, value=angle: w.set_ortho(value),
                checkable=True,
            )
            action.setChecked(w.canvas.ortho_angle == angle)
            self.ortho_group.addAction(action)
            ortho.addAction(action)
        arc_cw = self.action(
            "tool.arc_clockwise",
            "Arcos no sentido horário",
            lambda checked: setattr(w.canvas, "arc_clockwise", checked),
            checkable=True,
        )
        tools.addAction(arc_cw)
        preferences = self.menu("&Preferências")
        preferences.addAction(
            self.action("preferences.background", "Cor do canvas…", w._background_color)
        )
        preferences.addAction(
            self.action("preferences.grid", "Configurar grade…", w.configure_grid)
        )
        preferences.addAction(
            self.action(
                "preferences.shortcuts", "Teclas de atalho…", w.configure_shortcuts, "Ctrl+F1"
            )
        )
        w.expanded_tools_action = self.action(
            "preferences.expanded_tools",
            "Mostrar todas as ferramentas à esquerda",
            w._toggle_expanded_tools,
            checkable=True,
        )
        w.expanded_tools_action.setChecked(w.preferences.data["expanded_tools"])
        preferences.addAction(w.expanded_tools_action)
        language = self.menu("Idioma", preferences)
        self.language_group = QActionGroup(w)
        for key, name in w.locale.languages.items():
            action = QAction(name, w)
            action.setData(key)
            action.setCheckable(True)
            action.setChecked(key == w.locale.language)
            action.triggered.connect(lambda checked=False, lang=key: w.set_language(lang))
            self.language_group.addAction(action)
            language.addAction(action)
        help = self.menu("&Ajuda")
        help.addAction(self.action("help.usage", "Como usar", w.show_help))
        help.addAction(self.action("help.about", "Sobre", w.about))
        help.addAction(self.action("help.splash", "Tela de apresentação", w.show_splash))
        help.addAction(self.action("help.support", "Suporte / doar ao criador", w.show_support))
        help.addAction(self.action("help.report_problem", "Relatar problemas", w.report_problem))
        self.action("grid.next", "Próxima grade", lambda: w.cycle_grid(1), "N")
        self.action("grid.previous", "Grade anterior", lambda: w.cycle_grid(-1), "Shift+N")
        w.addActions([self.actions["grid.next"], self.actions["grid.previous"]])

    def toolbar(self, title, area=Qt.ToolBarArea.TopToolBarArea):
        toolbar = QToolBar(self.window)
        self.window.locale.bind(toolbar, title, "setWindowTitle")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.window.addToolBar(area, toolbar)
        return toolbar

    def toolbars(self):
        w = self.window
        toolbar = self.toolbar("Arquivos e visualização")
        toolbar.addActions(
            [w.open_action, w.save_action, w.save_as_action, w.save_all_action, w.close_all_action]
        )
        toolbar.addSeparator()
        toolbar.addActions(self.edit_actions)
        toolbar.addSeparator()
        toolbar.addActions([w.zoom_in_action, w.zoom_out_action, w.fit_action])
        toolbar.addAction(w.viewer3d_action)
        toolbar.addSeparator()
        toolbar.addWidget(self.label("Camada:"))
        w.layer_combo = QComboBox()
        w.layer_combo.setObjectName("activeLayerCombo")
        w.layer_combo.setMinimumWidth(230)
        w.layer_combo.currentIndexChanged.connect(self.activate_layer)
        toolbar.addWidget(w.layer_combo)
        w.layer_info = QLabel()
        toolbar.addWidget(w.layer_info)
        w.addToolBarBreak()
        drawing = self.toolbar("Parâmetros de edição")
        drawing.addWidget(self.label("Espessura:"))
        w.width_input = QDoubleSpinBox()
        w.width_input.setDecimals(6)
        w.width_input.setRange(0.000001, 100000)
        w.width_input.setValue(float(w.display_unit.from_mm(0.2)))
        w.width_input.setSuffix(" " + w.display_unit.value)
        drawing.addWidget(w.width_input)
        drawing.addWidget(self.label("Polaridade:"))
        w.polarity_input = QComboBox()
        drawing.addWidget(w.polarity_input)
        w.filled_input = w.locale.bind(QCheckBox(), "Preenchido")
        w.filled_input.setToolTip(
            w.t("Preencher círculos, setores de arco, quadrados e retângulos")
        )
        drawing.addWidget(w.filled_input)
        drawing.addWidget(self.label("Grade:"))
        w.grid_combo = QComboBox()
        w.grid_combo.setEditable(True)
        w.grid_combo.setMinimumWidth(125)
        w.grid_combo.currentIndexChanged.connect(self._grid_selected)
        w.grid_combo.lineEdit().editingFinished.connect(w.custom_grid)
        drawing.addWidget(w.grid_combo)
        self.fill_grids()
        drawing.addAction(self.actions["preferences.grid"])
        drawing.addAction(w.snap_action)
        drawing.addAction(w.snap_points_action)
        w.active_only_checkbox = w.locale.bind(QCheckBox(), "Selecionar apenas camada ativa")
        w.active_only_checkbox.setChecked(True)
        w.active_only_checkbox.toggled.connect(w._selection_scope)
        drawing.addWidget(w.active_only_checkbox)
        left = self.toolbar("Ferramentas CAD", Qt.ToolBarArea.LeftToolBarArea)
        self.left_toolbar = left
        left.addActions([w.select_action, w.measure_action])
        left.addSeparator()
        left.addActions(
            [
                w.grid_action,
                w.axes_action,
                w.snap_action,
                w.full_cursor_action,
                w.polar_action,
                w.ghost_action,
            ]
        )
        left.addSeparator()
        self.units_group = QActionGroup(w)
        self.unit_actions = {}
        for unit in ("in", "mil", "mm"):
            action = self.action(
                "units." + unit,
                unit,
                lambda checked=False, value=unit: w.set_units(value),
                checkable=True,
                glyph=unit,
            )
            action.setChecked(unit == w.display_unit.value)
            self.unit_actions[unit] = action
            self.units_group.addAction(action)
            left.addAction(action)
        left.addSeparator()
        left.addActions(
            [
                w.line_action,
                w.arc_action,
                w.circle_action,
                w.rectangle_action,
                w.square_action,
                w.text_action,
                w.dimension_action,
                w.fiducial_action,
                w.import_graphic_action,
            ]
        )
        self.tool_palette = ToolPalette(left.actions())
        self.tool_dock = QDockWidget(w)
        self.tool_dock.setObjectName("expandedToolsDock")
        w.locale.bind(self.tool_dock, "Ferramentas CAD", "setWindowTitle")
        self.tool_dock.setTitleBarWidget(QWidget())
        self.tool_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.tool_dock.setWidget(self.tool_palette)
        w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tool_dock)
        self.apply_tool_layout(w.preferences.data["expanded_tools"])
        self.retranslate_controls()

    def apply_tool_layout(self, expanded):
        self.left_toolbar.setVisible(not expanded)
        self.tool_dock.setVisible(expanded)

    def retranslate_controls(self):
        w = self.window
        index = w.polarity_input.currentIndex()
        w.polarity_input.blockSignals(True)
        w.polarity_input.clear()
        w.polarity_input.addItems([w.t("Dark · adicionar"), w.t("Clear · subtrair")])
        w.polarity_input.setCurrentIndex(max(0, index))
        w.polarity_input.blockSignals(False)
        self.refresh_tooltips()

    def refresh_tooltips(self):
        for action in self.actions.values():
            action.setToolTip(
                action.text().replace("&", "")
                + (
                    " (" + action.shortcut().toString() + ")"
                    if not action.shortcut().isEmpty()
                    else ""
                )
            )

    def fill_grids(self):
        w = self.window
        w.grid_combo.blockSignals(True)
        w.grid_combo.clear()
        grids = list(w.preferences.data["grids_mm"])
        current = str(w.canvas.grid_mm)
        if not any(Decimal(value) == w.canvas.grid_mm for value in grids):
            grids.append(current)
        for value in grids:
            label = (
                format(w.display_unit.from_mm(Decimal(value)), ".10g") + " " + w.display_unit.value
            )
            w.grid_combo.addItem(label, value)
            if Decimal(value) == w.canvas.grid_mm:
                w.grid_combo.setCurrentIndex(w.grid_combo.count() - 1)
        w.grid_combo.blockSignals(False)

    def _grid_selected(self, index):
        if index >= 0 and self.window.grid_combo.itemData(index) is not None:
            self.window._grid_changed(Decimal(self.window.grid_combo.itemData(index)))

    def status(self):
        w = self.window
        w.coordinates, w.count_label, w.zoom_label = QLabel(), QLabel(), QLabel("Z 1.00")
        w.statusBar().addPermanentWidget(w.zoom_label)
        w.statusBar().addPermanentWidget(w.coordinates)
        w.statusBar().addPermanentWidget(w.count_label)
        w.import_progress = FileProgress(w.locale, "Abrindo", w)
        w.import_progress.setObjectName("importFileProgress")
        w.save_progress = FileProgress(w.locale, "Salvando", w)
        w.save_progress.setObjectName("saveFileProgress")
        w.statusBar().addPermanentWidget(w.import_progress)
        w.statusBar().addPermanentWidget(w.save_progress)
        w.statusBar().addPermanentWidget(w.busy)
        w.canvas.coordinatesChanged.connect(self.coordinates)
        w.canvas.zoomChanged.connect(lambda zoom: w.zoom_label.setText(f"Z {zoom / 12:.2f}"))
        self.coordinates(0, 0)
        w.statusBar().showMessage(
            w.t("Ctrl+O abre arquivos, inclusive sem extensão. Home enquadra.")
        )

    @property
    def units(self):
        return self.window.display_unit.value

    def coordinates(self, x, y):
        self.cursor = (x, y)
        w = self.window
        if w.canvas.polar:
            value = f"R {w.display_unit.from_mm(math.hypot(x, y)):.4f}  θ {math.degrees(math.atan2(y, x)):.2f}°"
        else:
            value = f"X {w.display_unit.from_mm(x):.4f}  Y {w.display_unit.from_mm(y):.4f}"
        w.coordinates.setText(value + " " + w.display_unit.value)

    def set_units(self, unit):
        self.window.set_units(unit)

    def show_measurement(self, dx, dy, distance):
        self.measurement = (dx, dy, distance)
        self.window.statusBar().showMessage(
            vector_text(dx, dy, self.window.display_unit, self.window.canvas.polar).replace(
                "\n", "   "
            )
        )

    def activate_layer(self, index):
        key = self.window.layer_combo.itemData(index)
        layer = next((layer for layer in self.window.layers if layer.id == key), None)
        self.window._active_changed(layer)

    def refresh(self):
        w = self.window
        w.layer_combo.blockSignals(True)
        w.layer_combo.clear()
        for layer in reversed(w.layers):
            w.layer_combo.addItem(layer.name + (" *" if layer.modified else ""), layer.id)
            if layer is w.active_layer:
                w.layer_combo.setCurrentIndex(w.layer_combo.count() - 1)
        w.layer_combo.blockSignals(False)
        w.layer_info.setText(
            " "
            + w.t(
                "{function} · {count} objetos",
                function=w.active_layer.function,
                count=len(w.active_layer.objects),
            )
            if w.active_layer
            else w.t("Nenhuma camada carregada")
        )
