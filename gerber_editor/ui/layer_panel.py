"""Layer list; changes are delegated to document commands."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gerber_editor.app.i18n import Locale


class LayerPanel(QWidget):
    activeChanged = Signal(object)
    propertyRequested = Signal(object, str, object)
    closeRequested = Signal(str)
    moveRequested = Signal(str, int)

    def __init__(self, locale=None):
        super().__init__()
        self.locale = locale or Locale()
        self.layers = []
        self._active_id = None
        self._active_timer = QTimer(self)
        self._active_timer.setSingleShot(True)
        self._active_timer.timeout.connect(self._emit_active)
        self._visibility_changes = {}
        self._visibility_timer = QTimer(self)
        self._visibility_timer.setSingleShot(True)
        self._visibility_timer.timeout.connect(self._emit_visibility)
        self.tree = QTreeWidget()
        self.tree.setObjectName("layerTree")
        self.tree.setHeaderLabels([self.locale("Camada"), self.locale("Função"), "%", ""])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 145)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 45)
        self.tree.setColumnWidth(3, 26)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        self.tree.currentItemChanged.connect(self._active)
        self.tree.itemChanged.connect(self._changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        hint = self.locale.bind(QLabel(), "Camada ativa: clique no nome para editar.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        order_hint = self.locale.bind(QLabel(), "A primeira camada da lista aparece à frente.")
        order_hint.setWordWrap(True)
        layout.addWidget(order_hint)
        layout.addWidget(self.tree)
        order_row = QHBoxLayout()
        order_row.addWidget(self.locale.bind(QLabel(), "Ordem das camadas"))
        order_row.addStretch()
        self.up_button = QToolButton()
        self.up_button.setObjectName("moveLayerUp")
        self.up_button.setArrowType(Qt.ArrowType.UpArrow)
        self.locale.bind(self.up_button, "Subir camada", "setToolTip")
        self.up_button.clicked.connect(lambda: self._request_move(-1))
        self.down_button = QToolButton()
        self.down_button.setObjectName("moveLayerDown")
        self.down_button.setArrowType(Qt.ArrowType.DownArrow)
        self.locale.bind(self.down_button, "Descer camada", "setToolTip")
        self.down_button.clicked.connect(lambda: self._request_move(1))
        order_row.addWidget(self.up_button)
        order_row.addWidget(self.down_button)
        layout.addLayout(order_row)
        row = QHBoxLayout()
        for title, callback in [
            ("Cor…", self._color),
            ("Opacidade…", self._opacity),
            ("Função…", self._function),
        ]:
            button = self.locale.bind(QPushButton(), title)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self._update_move_buttons()

    def refresh(self, layers, active_id):
        self.layers = layers
        self._active_timer.stop()
        self.tree.blockSignals(True)
        existing = {
            item.data(0, Qt.ItemDataRole.UserRole): item
            for index in range(self.tree.topLevelItemCount())
            if (item := self.tree.topLevelItem(index)) is not None
        }
        if list(existing) != [layer.id for layer in reversed(layers)]:
            self.tree.clear()
            existing = {}
        for layer in reversed(layers):
            item = existing.get(layer.id) or QTreeWidgetItem()
            for column, text in enumerate(
                (
                    layer.name + (" *" if layer.modified else ""),
                    layer.function,
                    str(round(layer.opacity * 100)),
                    "",
                )
            ):
                item.setText(column, text)
            item.setData(0, Qt.ItemDataRole.UserRole, layer.id)
            item.setCheckState(
                0, Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked
            )
            item.setToolTip(0, str(layer.path or self.locale("Camada sem arquivo")))
            swatch = QPixmap(14, 14)
            swatch.fill(QColor(layer.color))
            item.setIcon(0, QIcon(swatch))
            if layer.id not in existing:
                self.tree.addTopLevelItem(item)
                close = QToolButton()
                close.setText("×")
                close.setAutoRaise(True)
                close.clicked.connect(
                    lambda checked=False, key=layer.id: QTimer.singleShot(
                        0, lambda: self.closeRequested.emit(key)
                    )
                )
                self.tree.setItemWidget(item, 3, close)
            self.tree.itemWidget(item, 3).setToolTip(self.locale("Fechar camada"))
            if layer.id == active_id:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        self._update_move_buttons()

    def retranslate(self):
        self.tree.setHeaderLabels([self.locale("Camada"), self.locale("Função"), "%", ""])

    def options_menu(self, layer, include_close=False):
        menu = QMenu(self)
        for title, callback in [
            ("Cor…", self._color),
            ("Opacidade…", self._opacity),
            ("Função…", self._function),
        ]:
            menu.addAction(
                self.locale(title), lambda chosen=False, cb=callback, value=layer: cb(value)
            )
        if include_close:
            menu.addSeparator()
            menu.addAction(self.locale("Fechar camada"), lambda: self.closeRequested.emit(layer.id))
        return menu

    def _double_clicked(self, item, column):
        layer = next(
            (value for value in self.layers if value.id == item.data(0, Qt.ItemDataRole.UserRole)),
            None,
        )
        if layer:
            self.options_menu(layer).exec(QCursor.pos())

    def _context_menu(self, position):
        item = self.tree.itemAt(position)
        if item:
            layer = next(
                (
                    value
                    for value in self.layers
                    if value.id == item.data(0, Qt.ItemDataRole.UserRole)
                ),
                None,
            )
            if layer:
                self.options_menu(layer, True).exec(self.tree.viewport().mapToGlobal(position))

    def current_layer(self):
        item = self.tree.currentItem()
        if item:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            return next((layer for layer in self.layers if layer.id == key), None)
        return None

    def _active(self, current, previous):
        self._active_id = current.data(0, Qt.ItemDataRole.UserRole) if current else None
        # Never rebuild the tree inside QTreeWidget's current-item event stack.
        self._active_timer.start(0)
        self._update_move_buttons()

    def _update_move_buttons(self):
        current = self.tree.currentItem()
        index = self.tree.indexOfTopLevelItem(current) if current is not None else -1
        self.up_button.setEnabled(index > 0)
        self.down_button.setEnabled(0 <= index < self.tree.topLevelItemCount() - 1)

    def _request_move(self, direction):
        layer = self.current_layer()
        if layer is not None:
            # Dispatch after the originating Qt input event has returned.
            QTimer.singleShot(0, lambda: self.moveRequested.emit(layer.id, direction))

    def _emit_active(self):
        layer = next((layer for layer in self.layers if layer.id == self._active_id), None)
        if layer:
            self.activeChanged.emit(layer)

    def _changed(self, item, column):
        if column == 0:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            layer = next((layer for layer in self.layers if layer.id == key), None)
            value = item.checkState(0) == Qt.CheckState.Checked
            if layer:
                # Keep the last checkbox value even if toggled twice before dispatch.
                self._visibility_changes[key] = value
                self._visibility_timer.start(0)

    def _emit_visibility(self):
        changes, self._visibility_changes = self._visibility_changes, {}
        for key, value in changes.items():
            layer = next((layer for layer in self.layers if layer.id == key), None)
            if layer and layer.visible != value:
                self.propertyRequested.emit(layer, "visible", value)

    def _color(self, layer=None):
        layer = layer or self.current_layer()
        if layer:
            color = QColorDialog.getColor(QColor(layer.color), self, self.locale("Cor da camada"))
            if color.isValid():
                self.propertyRequested.emit(layer, "color", color.name())

    def _opacity(self, layer=None):
        layer = layer or self.current_layer()
        if layer:
            value, ok = QInputDialog.getInt(
                self,
                self.locale("Opacidade"),
                self.locale("Opacidade (%)"),
                round(layer.opacity * 100),
                0,
                100,
            )
            if ok:
                self.propertyRequested.emit(layer, "opacity", value / 100)

    def _function(self, layer=None):
        layer = layer or self.current_layer()
        if layer:
            options = [
                "F.Cu",
                "B.Cu",
                "In1.Cu",
                "In2.Cu",
                "F.Silk",
                "B.Silk",
                "F.Mask",
                "B.Mask",
                "F.Paste",
                "B.Paste",
                "Edge.Cuts",
                "Route.Cuts",
                "Drill",
                "Drill.PTH",
                "Drill.NPTH",
                "Drill drawing",
                "Mechanical",
                "V-Cut",
            ]
            value, ok = QInputDialog.getItem(
                self,
                self.locale("Função da camada"),
                self.locale("Função visual (Gerber permanece intacto)"),
                options,
                max(0, options.index(layer.function) if layer.function in options else 0),
                True,
            )
            if ok and value:
                self.propertyRequested.emit(layer, "function", value)
