"""View/preferences and the same Help entries as the main editor."""

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QMessageBox

from gerber_editor.ui.about_dialog import AboutDialog
from gerber_editor.ui.dialog_helpers import buttons, spin
from gerber_editor.ui.splash import SplashScreen
from gerber_editor.ui.support_dialog import SupportDialog


class ViewerMenus:
    def _menu_action(self, menu, label, callback, checkable=False):
        action = QAction(self)
        self.locale.bind(action, label)
        action.setCheckable(checkable)
        action.triggered.connect(
            lambda checked=False: callback(checked) if checkable else callback()
        )
        menu.addAction(action)
        return action

    def _menu(self, title, parent=None):
        menu = (parent or self.menuBar()).addMenu("")
        self.locale.bind(menu, title, "setTitle")
        return menu

    def build_menus(self):
        view = self._menu("&Visualizar")
        view.addAction(self.reload_action)
        view.addSeparator()
        view.addActions(self.view_actions)
        view.addAction(self.fit_action)
        view.addAction(self.flip_action)
        view.addSeparator()
        view.addAction(self.material_dock.toggleViewAction())
        preferences = self._menu("&Preferências")
        self.realistic_action = self._menu_action(
            preferences, "Realista", self.realistic_checkbox.setChecked, True
        )
        self.realistic_action.setChecked(self.viewport.realistic)
        self.perspective_action = self._menu_action(
            preferences, "Perspectiva", self.perspective_checkbox.setChecked, True
        )
        self.perspective_action.setChecked(self.viewport.perspective)
        self._menu_action(preferences, "Espessura e detalhe 3D…", self.configure_3d)
        self._menu_action(preferences, "Teclas de atalho…", self.editor.configure_shortcuts)
        language = self._menu("Idioma", preferences)
        self.language_group = QActionGroup(self)
        for key, name in self.locale.languages.items():
            action = QAction(name, self)
            action.setData(key)
            action.setCheckable(True)
            action.setChecked(key == self.locale.language)
            action.triggered.connect(lambda checked=False, lang=key: self.editor.set_language(lang))
            self.language_group.addAction(action)
            language.addAction(action)
        help_menu = self._menu("&Ajuda")
        for label, callback in (
            ("Como usar", self.show_help),
            ("Sobre", self.about),
            ("Tela de apresentação", self.show_splash),
            ("Suporte / doar ao criador", self.show_support),
            ("Relatar problemas", self.editor.report_problem),
        ):
            self._menu_action(help_menu, label, callback)

    def configure_3d(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.locale("Espessura e detalhe 3D…"))
        layout = QFormLayout(dialog)
        unit = self.editor.display_unit
        thickness = spin(
            self.thickness.value(), float(unit.from_mm(0.1)), float(unit.from_mm(20)), unit
        )
        detail = QComboBox()
        for index in range(self.detail.count()):
            detail.addItem(self.detail.itemText(index))
        detail.setCurrentIndex(self.detail.currentIndex())
        layout.addRow(self.locale("Espessura PCB"), thickness)
        layout.addRow(self.locale("Detalhe 3D"), detail)
        layout.addRow(buttons(dialog, self.locale))
        if dialog.exec():
            self.thickness.set_mm(thickness.mm)
            self.detail.blockSignals(True)
            self.detail.setCurrentIndex(detail.currentIndex())
            self.detail.blockSignals(False)
            self._settings_changed()

    def show_help(self):
        self.editor.show_help(section="viewer3d")

    def about(self):
        AboutDialog(self).exec()

    def show_support(self):
        SupportDialog(self).exec()

    def show_splash(self):
        self._help_splash = SplashScreen(self.locale, dismiss_on_click=True)
        self._help_splash.supportRequested.connect(self.show_support)
        self._help_splash.show()

    def show_error(self, title, error):
        QMessageBox.warning(self, self.locale(title), self.locale.error(str(error)))
