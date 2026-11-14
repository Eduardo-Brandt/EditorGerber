"""Initial visual theme; no global mutable settings."""

from PySide6.QtGui import QColor, QPalette


def apply_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#243249"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#edf1f6"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#243249"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ededed"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#243249"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2c70b8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    for role, color in (
        (QPalette.ColorRole.Base, "#e2e2e2"),
        (QPalette.ColorRole.Button, "#e2e2e2"),
        (QPalette.ColorRole.Text, "#6b6b6b"),
        (QPalette.ColorRole.ButtonText, "#777777"),
        (QPalette.ColorRole.WindowText, "#777777"),
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet("""
        QMainWindow { font-family: 'Segoe UI'; font-size: 9pt; }
        QDockWidget::title { padding: 3px 5px; background: #d7d7d7; }
        QToolBar { spacing: 1px; padding: 2px; border-bottom: 1px solid #d0d0d0; }
        QToolButton { padding: 3px; border-radius: 1px; }
        QToolButton:hover { background: #dce8f7; }
        QToolButton:checked { background: #c6dcf5; }
        QTreeWidget, QTableWidget { border: 1px solid #d6d6d6; }
        QTabWidget::pane { border: 1px solid #d1d1d1; }
        QLineEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled,
        QTextEdit:disabled, QPlainTextEdit:disabled,
        QLineEdit:read-only, QAbstractSpinBox:read-only,
        .QTextEdit:read-only, .QPlainTextEdit:read-only {
            background-color: #e2e2e2;
            color: #6b6b6b;
            selection-background-color: #2c70b8;
            selection-color: #ffffff;
        }
        QTableWidget[readOnlyValues="true"] {
            background-color: #e2e2e2;
            alternate-background-color: #d9d9d9;
            color: #525b67;
        }
        QStatusBar { background: #efefef; }
    """)
