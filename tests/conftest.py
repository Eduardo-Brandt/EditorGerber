import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv("EDITR_GERBER_SETTINGS", str(tmp_path / "preferences.json"))
    monkeypatch.setenv("EDITOR_GERBER_SETTINGS", str(tmp_path / "preferences.json"))


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    from gerber_editor.tools.vector_text import ensure_offscreen_font

    ensure_offscreen_font()
    yield app
