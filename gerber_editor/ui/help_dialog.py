"""Offline HTML guide with topic links, search and current keyboard shortcuts."""

import re
from html import escape
from pathlib import Path

from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from gerber_editor.app.metadata import REPORT_PROBLEM_URL, VERSION


def help_html(editor):
    source = Path(__file__).resolve().parents[1] / "assets" / f"help_{editor.locale.language}.html"
    template = source.read_text(encoding="utf-8")

    def substitute(match):
        key = match[1]
        if key == "version":
            return escape(VERSION)
        if key == "report_url":
            return escape(REPORT_PROBLEM_URL, quote=True)
        if key == "shortcuts":
            return "\n".join(
                "<tr><td>"
                + escape(editor.t(action.property("sourceText")))
                + "</td><td><b>"
                + escape(action.shortcut().toString())
                + "</b></td></tr>"
                for action in editor.chrome.actions.values()
                if not action.shortcut().isEmpty()
            )
        action = editor.chrome.actions[key]
        return escape(action.shortcut().toString() or editor.t("Sem atalho"))

    return re.sub(r"\{\{([a-zA-Z0-9_.]+)\}\}", substitute, template)


class HelpDialog(QDialog):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.section = "start"
        self.setObjectName("usageHelpDialog")
        self.setWindowIcon(editor.windowIcon())
        self.resize(900, 700)
        self.setMinimumSize(560, 400)
        t = editor.locale
        t.bind(self, "Ajuda do Editor Gerber", "setWindowTitle")
        self.search = QLineEdit()
        self.search.setObjectName("helpSearch")
        t.bind(self.search, "Buscar na ajuda…", "setPlaceholderText")
        previous, following, contents = QPushButton(), QPushButton(), QPushButton()
        t.bind(previous, "Anterior")
        t.bind(following, "Próximo")
        t.bind(contents, "Índice")
        for button in (previous, following, contents):
            button.setAutoDefault(False)
        previous.clicked.connect(lambda: self.find_text(backward=True))
        following.clicked.connect(lambda: self.find_text())
        contents.clicked.connect(lambda: self.open_section("start"))
        self.search.returnPressed.connect(self.find_text)
        self.message = QLabel()
        self.browser = QTextBrowser()
        self.browser.setObjectName("helpBrowser")
        self.browser.document().setDocumentMargin(24)
        self.browser.setOpenExternalLinks(True)
        self.browser.anchorClicked.connect(self._anchor_clicked)
        bar = QHBoxLayout()
        bar.addWidget(self.search, 1)
        for button in (previous, following, contents):
            bar.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.browser, 1)
        layout.addWidget(self.message)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        t.bind(close.button(QDialogButtonBox.StandardButton.Close), "Fechar")
        close.rejected.connect(self.close)
        layout.addWidget(close)
        shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        shortcut.activated.connect(self.search.setFocus)
        self.retranslate()

    def _anchor_clicked(self, url):
        if url.fragment():
            self.section = url.fragment()

    def retranslate(self):
        self.browser.setHtml(help_html(self.editor))
        self.browser.scrollToAnchor(self.section)
        self.message.clear()

    def open_section(self, section="start"):
        self.section = section
        self.retranslate()
        self.show()
        self.browser.scrollToAnchor(section)
        self.raise_()
        self.activateWindow()
        self.browser.setFocus()

    def find_text(self, backward=False):
        text = self.search.text().strip()
        if not text:
            return
        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        if not self.browser.find(text, flags):
            cursor = self.browser.textCursor()
            cursor.movePosition(
                QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start
            )
            self.browser.setTextCursor(cursor)
            found = self.browser.find(text, flags)
        else:
            found = True
        self.message.setText("" if found else self.editor.t("Texto não encontrado."))
