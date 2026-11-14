"""Extensible text catalogs; action identifiers and shortcuts are never translated."""

from __future__ import annotations

import json
import weakref
from pathlib import Path


def install_qt_locale(language):
    """Localize standard Qt buttons and file dialogs with the bundled catalog."""
    from PySide6.QtCore import QLibraryInfo, QTranslator
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    previous = getattr(app, "_editr_translator", None)
    if previous:
        app.removeTranslator(previous)
    app._editr_translator = None
    if language != "en":
        translator = QTranslator(app)
        root = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load("qtbase_" + language, root):
            app.installTranslator(translator)
            app._editr_translator = translator


class Locale:
    languages = {"pt_BR": "Português (Brasil)", "en": "English"}

    def __init__(self, language="pt_BR"):
        self.bindings = []
        self.catalog = {}
        self.set_language(language)

    def set_language(self, language):
        if language not in self.languages:
            raise ValueError("Unsupported language")
        self.language = language
        path = Path(__file__).resolve().parents[1] / "locales" / f"{language}.json"
        self.catalog = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        active = []
        for reference, method, source in self.bindings:
            widget = reference()
            if widget is not None:
                try:
                    getattr(widget, method)(self(source))
                    active.append((reference, method, source))
                except RuntimeError:
                    pass  # Qt has already destroyed a closed dialog.
        self.bindings = active

    def __call__(self, source: str, **values) -> str:
        return (
            self.catalog.get(source, source).format(**values)
            if values
            else self.catalog.get(source, source)
        )

    def bind(self, widget, source, method="setText"):
        self.bindings.append((weakref.ref(widget), method, source))
        getattr(widget, method)(self(source))
        return widget

    def error(self, message: str) -> str:
        for source, target in sorted(self.catalog.items(), key=lambda pair: -len(pair[0])):
            if len(source) > 12 and "{" not in source:
                message = message.replace(source, target)
        return message
