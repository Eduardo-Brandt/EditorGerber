"""Grid and shortcut editors use stable action keys, independently of language."""

from decimal import Decimal, InvalidOperation

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QKeySequenceEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gerber_editor.ui.dialog_helpers import buttons, dialog_context


class ShortcutsDialog(QDialog):
    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.locale, _ = dialog_context(parent)
        self.registry = registry
        self.setWindowTitle(self.locale("Teclas de atalho…"))
        self.resize(700, 620)
        self.table = QTableWidget(len(registry), 3)
        self.table.setHorizontalHeaderLabels(
            [self.locale("Ação"), self.locale("Atalho"), self.locale("Padrão")]
        )
        self.table.setColumnWidth(0, 310)
        self.editors = {}
        for row, (key, action) in enumerate(registry.items()):
            self.table.setItem(row, 0, QTableWidgetItem(action.text().replace("&", "")))
            editor = QKeySequenceEdit(action.shortcut())
            self.table.setCellWidget(row, 1, editor)
            self.table.setItem(row, 2, QTableWidgetItem(action.property("defaultShortcut") or ""))
            self.editors[key] = editor
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        reset = QPushButton(self.locale("Restaurar padrões"))
        reset.clicked.connect(self._reset)
        layout.addWidget(reset)
        layout.addWidget(buttons(self, self.locale))

    def _reset(self):
        for key, editor in self.editors.items():
            editor.setKeySequence(
                QKeySequence(self.registry[key].property("defaultShortcut") or "")
            )

    def values(self):
        return {
            key: editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for key, editor in self.editors.items()
        }

    def accept(self):
        seen = {}
        for key, value in self.values().items():
            if value and value in seen:
                QMessageBox.warning(
                    self,
                    self.locale("Atalho duplicado"),
                    self.locale(
                        "Conflito entre {first} e {second}.",
                        first=self.registry[seen[value]].text(),
                        second=self.registry[key].text(),
                    ),
                )
                return
            if value:
                seen[value] = key
        super().accept()


class GridDialog(QDialog):
    def __init__(self, values_mm, parent=None):
        super().__init__(parent)
        self.locale, self.unit = dialog_context(parent)
        self.setWindowTitle(self.locale("Configurar grade…"))
        self.table = QTableWidget(len(values_mm), 1)
        self.table.setHorizontalHeaderLabels(
            [self.locale("Valores de grade") + " (" + self.unit.value + ")"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, value in enumerate(values_mm):
            self.table.setItem(row, 0, QTableWidgetItem(str(self.unit.from_mm(Decimal(value)))))
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton(self.locale("Adicionar"))
        remove = QPushButton(self.locale("Remover"))
        add.clicked.connect(lambda: self.table.insertRow(self.table.rowCount()))
        remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        row.addWidget(add)
        row.addWidget(remove)
        layout.addLayout(row)
        layout.addWidget(buttons(self, self.locale))

    def values(self):
        values = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            value = Decimal(item.text().replace(",", ".").strip()) if item else Decimal(0)
            value = self.unit.to_mm(value)
            if not value.is_finite() or not Decimal("0.000001") <= value <= 100000:
                raise ValueError("Invalid grid spacing")
            values.append(value)
        if not values:
            raise ValueError("Empty grid list")
        return [str(value.normalize()) for value in sorted(set(values))]

    def accept(self):
        try:
            self.values()
        except (ValueError, InvalidOperation):
            QMessageBox.warning(
                self,
                self.locale("Espaçamento inválido"),
                self.locale("Informe um valor positivo para a grade."),
            )
            return
        super().accept()
