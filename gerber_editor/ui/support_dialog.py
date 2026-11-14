"""Optional creator support; copying/QR display never executes a payment."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from gerber_editor.app.metadata import CREATOR, PAYPAL_URL, PIX_KEY, WEBSITE_URL
from gerber_editor.tools.pix import pix_payload, qr_image


class SupportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        t = parent.t
        self.setWindowTitle(t("Suporte / doar ao criador"))
        layout = QVBoxLayout(self)
        title = QLabel("<h2>" + t("SOFTWARE LIVRE") + "</h2>" + CREATOR)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        message = QLabel(
            t(
                "Se desejar apoiar o desenvolvimento, você pode contribuir com qualquer valor via Pix."
            )
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.payload = pix_payload(PIX_KEY, CREATOR, "INDAIAL")
        self.image = qr_image(self.payload)
        qr = QLabel()
        qr.setPixmap(QPixmap.fromImage(self.image))
        qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(qr)
        key = QLineEdit(PIX_KEY)
        key.setReadOnly(True)
        layout.addWidget(key)
        row = QHBoxLayout()
        for label, value in (
            ("Copiar chave Pix", PIX_KEY),
            ("Copiar Pix Copia e Cola", self.payload),
        ):
            button = QPushButton(t(label))
            button.clicked.connect(
                lambda checked=False, text=value: QApplication.clipboard().setText(text)
            )
            row.addWidget(button)
        layout.addLayout(row)
        save = QPushButton(t("Salvar QR Code…"))
        save.clicked.connect(lambda: self._save(parent))
        layout.addWidget(save)
        paypal = QPushButton("PayPal" if PAYPAL_URL else t("PayPal — link em breve"))
        paypal.setEnabled(bool(PAYPAL_URL))
        paypal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PAYPAL_URL)))
        layout.addWidget(paypal)
        site = QLabel(f'<a href="{WEBSITE_URL}">{t("Suporte pelo site")}</a>')
        site.setOpenExternalLinks(True)
        layout.addWidget(site)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText(t("Fechar"))
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def _save(self, parent):
        path, _ = QFileDialog.getSaveFileName(
            self, parent.t("Salvar QR Code…"), "Editor_Gerber_Pix.png", "PNG (*.png)"
        )
        if path and not self.image.save(path, "PNG"):
            parent.show_error("Imagem não salva", "Não foi possível salvar a imagem.")
