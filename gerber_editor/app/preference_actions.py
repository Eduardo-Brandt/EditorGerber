"""Persistent presentation settings; none of these alter fabrication geometry."""

import re
from decimal import Decimal, InvalidOperation

from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import QColorDialog

from gerber_editor.core.units import Unit
from gerber_editor.ui.preferences_dialogs import GridDialog, ShortcutsDialog


class PreferenceActions:
    def _toggle_expanded_tools(self, checked):
        self.chrome.apply_tool_layout(checked)
        self.remember(expanded_tools=checked)

    def remember(self, **values):
        try:
            self.preferences.set(**values)
        except (OSError, ValueError) as exc:
            self.show_error("Configurações não salvas", exc)

    def set_units(self, unit):
        self.display_unit = Unit(unit)
        self.canvas.units = self.display_unit
        self.properties.unit = self.display_unit
        self.width_input.blockSignals(True)
        self.width_input.setSuffix(" " + self.display_unit.value)
        self.width_input.setValue(float(self.display_unit.from_mm(self.drawing_width_mm)))
        self.width_input.blockSignals(False)
        for key, action in self.chrome.unit_actions.items():
            action.setChecked(key == self.display_unit.value)
        self.chrome.fill_grids()
        self.chrome.coordinates(*self.chrome.cursor)
        if self.chrome.measurement:
            self.chrome.show_measurement(*self.chrome.measurement)
        self._selection_changed()
        self.canvas.viewport().update()
        if self._viewer3d:
            self._viewer3d.set_units(self.display_unit)
        self.remember(units=self.display_unit.value)

    def _width_changed(self, value):
        self.drawing_width_mm = self.display_unit.to_mm(value)

    def set_language(self, language):
        from gerber_editor.app.i18n import install_qt_locale

        install_qt_locale(language)
        with self.busy.operation("Atualizando interface…"):
            self.locale.set_language(language)
            self.chrome.retranslate_controls()
            self.layer_panel.retranslate()
            self.refresh()
            if self._viewer3d:
                self._viewer3d.retranslate()
            if self._help_dialog:
                self._help_dialog.retranslate()
        for action in self.chrome.language_group.actions():
            action.setChecked(action.data() == language)
        self.remember(language=language)

    def configure_shortcuts(self):
        dialog = ShortcutsDialog(self.chrome.actions, self)
        if dialog.exec():
            values = dialog.values()
            for key, value in values.items():
                self.chrome.actions[key].setShortcut(QKeySequence(value))
            self.chrome.refresh_tooltips()
            if self._help_dialog:
                self._help_dialog.retranslate()
            self.remember(shortcuts=values)

    def configure_grid(self):
        dialog = GridDialog(self.preferences.data["grids_mm"], self)
        if dialog.exec():
            values = dialog.values()
            if not any(Decimal(value) == self.canvas.grid_mm for value in values):
                self.canvas.grid_mm = Decimal(values[0])
            self.remember(grids_mm=values, grid_mm=str(self.canvas.grid_mm))
            self.chrome.fill_grids()
            self.canvas.viewport().update()

    def cycle_grid(self, direction):
        index = self.grid_combo.currentIndex()
        if self.grid_combo.count():
            self.grid_combo.setCurrentIndex((index + direction) % self.grid_combo.count())

    def custom_grid(self):
        text = self.grid_combo.currentText().strip()
        for index in range(self.grid_combo.count()):
            if text == self.grid_combo.itemText(index):
                return
        try:
            match = re.fullmatch(r"([+\-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))\s*(mm|in|mil)?", text)
            if not match:
                raise ValueError("Invalid grid spacing")
            value = Unit(match[2] or self.display_unit.value).to_mm(
                Decimal(match[1].replace(",", "."))
            )
            if not value.is_finite() or not Decimal("0.000001") <= value <= 100000:
                raise ValueError("Invalid grid spacing")
            grids = self.preferences.data["grids_mm"]
            if not any(Decimal(v) == value for v in grids):
                grids = [*grids, str(value)]
            self.remember(grids_mm=grids, grid_mm=str(value))
            self.canvas.grid_mm = value
            self.chrome.fill_grids()
            self.canvas.viewport().update()
        except (ValueError, InvalidOperation):
            self.show_error(
                "Espaçamento inválido", self.t("Informe um valor positivo para a grade.")
            )
            self.chrome.fill_grids()

    def _grid_changed(self, value):
        value = Decimal(str(value))
        self.canvas.grid_mm = value
        self.canvas.viewport().update()
        self.remember(grid_mm=str(value))

    def _toggle_grid(self, checked):
        self.canvas.grid_visible = checked
        self.canvas.viewport().update()
        self.remember(grid_visible=checked)

    def _toggle_axes(self, checked):
        self.canvas.axes_visible = checked
        self.canvas.viewport().update()

    def _toggle_snap(self, checked):
        self.canvas.snap_grid = checked
        self.remember(snap_grid=checked)

    def _toggle_full_cursor(self, checked):
        self.canvas.full_cursor = checked
        self.canvas.viewport().update()
        self.remember(full_cursor=checked)

    def _toggle_polar(self, checked):
        self.canvas.polar = checked
        self.chrome.coordinates(*self.chrome.cursor)
        if self.chrome.measurement:
            self.chrome.show_measurement(*self.chrome.measurement)
        self.canvas.viewport().update()
        self.remember(polar=checked)

    def _toggle_ghost(self, checked):
        self.canvas.set_ghost_negatives(checked)
        self.remember(ghost_negatives=checked)

    def _toggle_snap_points(self, checked):
        self.canvas.snap_points = checked
        self.remember(snap_points=checked)
        self.canvas.viewport().update()

    def set_ortho(self, angle):
        self.canvas.ortho_angle = angle
        self.remember(ortho_angle=angle)
        self.canvas.viewport().update()

    def _selection_scope(self, checked):
        self.canvas.active_only = checked
        self.canvas.clear_selection()

    def _background_color(self):
        color = QColorDialog.getColor(
            self.canvas.backgroundBrush().color(), self, self.t("Fundo do canvas")
        )
        if color.isValid():
            self.canvas.setBackgroundBrush(QColor(color))
            self.remember(background=color.name())
