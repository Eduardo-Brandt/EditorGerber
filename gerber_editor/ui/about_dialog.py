"""Creator credits and a clickable publisher website."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from gerber_editor.app.metadata import (
    APP_NAME,
    CREATED,
    CREATOR,
    LOCATION,
    SUPPORT_MESSAGE,
    VERSION,
    WEBSITE,
    WEBSITE_URL,
)


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        t = parent.t
        self.setWindowTitle(t("Sobre") + " " + APP_NAME)
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        title = QLabel(
            f"<h2>{APP_NAME}</h2>{t('Versão')} {VERSION}<p><b>{t('SOFTWARE LIVRE')}</b> · GPLv3</p>"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        details = QLabel(
            f"<p><b>{t('Criador')}:</b> {CREATOR}<br>{LOCATION}</p>"
            f"<p>{t('Criação')}: {CREATED}</p>"
            f'<p><a href="{WEBSITE_URL}">{WEBSITE}</a></p>'
        )
        details.setOpenExternalLinks(True)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(details)
        support = QLabel(f'<a href="support">{t(SUPPORT_MESSAGE)}</a>')
        support.setObjectName("supportInvitation")
        support.setWordWrap(True)
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support.linkActivated.connect(lambda _: self._support(parent))
        layout.addWidget(support)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText(t("Fechar"))
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _support(self, parent):
        from gerber_editor.ui.support_dialog import SupportDialog

        SupportDialog(parent).exec()
