"""Startup, navigation and safe multi-file loading regressions for 0.5.2."""

from pathlib import Path
from time import monotonic

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QLabel, QPushButton, QVBoxLayout

from gerber_editor.app.i18n import Locale
from gerber_editor.app.importer import ImportJob, is_auxiliary_file
from gerber_editor.app.main_window import MainWindow
from gerber_editor.app.metadata import SUPPORT_MESSAGE, WEBSITE_URL
from gerber_editor.app.preferences import Preferences
from gerber_editor.ui.about_dialog import AboutDialog
from gerber_editor.ui.splash import SplashScreen
from gerber_editor.viewer3d import menus
from gerber_editor.viewer3d.window import Viewer3DWindow

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "basic.gbr"


def wait_until(qapp, predicate, timeout=10):
    deadline = monotonic() + timeout
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt operation timed out"
    qapp.processEvents()


def finish(window, qapp):
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    qapp.processEvents()
    window.close()


def test_startup_cannot_be_dismissed_before_four_seconds(qapp, monkeypatch):
    # Keep this timing regression independent of the user's configured duration.
    monkeypatch.setattr(SplashScreen, "MINIMUM_SECONDS", 4.0)
    editor = MainWindow()
    editor.show()
    qapp.processEvents()
    splash = SplashScreen(Locale())
    splash.show()
    qapp.processEvents()
    started = monotonic()
    hidden_at = []
    splash.supportRequested.connect(lambda: hidden_at.append(monotonic() - started))
    splash.finish(editor)
    QTest.keyClick(splash, Qt.Key.Key_Escape)
    QTest.mouseClick(splash, Qt.MouseButton.LeftButton, pos=splash.rect().center())
    splash.close()
    assert splash.isVisible()
    QTest.mouseClick(splash, Qt.MouseButton.LeftButton, pos=splash.support_rect.center().toPoint())
    QTest.qWait(200)
    assert splash.isVisible() and not hidden_at
    wait_until(qapp, lambda: bool(hidden_at), timeout=5)
    assert hidden_at[0] >= 3.95 and not splash.isVisible()
    editor.close()


def test_splash_links_use_project_url_and_open_support(qapp, monkeypatch):
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: urls.append(url.toString()))
    splash = SplashScreen(Locale(), dismiss_on_click=True)
    splash.show()
    qapp.processEvents()
    assert not splash.link_rect.intersects(splash.support_rect)
    QTest.mouseClick(splash, Qt.MouseButton.LeftButton, pos=splash.link_rect.center().toPoint())
    assert urls == ["https://brandttecnologia.com.br/EditorGerber"]
    signal = QSignalSpy(splash.supportRequested)
    QTest.mouseClick(splash, Qt.MouseButton.LeftButton, pos=splash.support_rect.center().toPoint())
    wait_until(qapp, lambda: signal.count() == 1)
    assert not splash.isVisible()


def test_about_invitation_opens_support_dialog(qapp, monkeypatch):
    editor = MainWindow()
    opened = []
    from gerber_editor.ui.support_dialog import SupportDialog

    monkeypatch.setattr(SupportDialog, "exec", lambda dialog: opened.append(dialog.parentWidget()))
    dialog = AboutDialog(editor)
    invitation = dialog.findChild(QLabel, "supportInvitation")
    assert SUPPORT_MESSAGE in invitation.text()
    assert WEBSITE_URL in " ".join(label.text() for label in dialog.findChildren(QLabel))
    invitation.linkActivated.emit("support")
    assert opened == [editor]
    editor.close()


def test_tool_palette_wraps_and_every_button_stays_accessible(qapp):
    editor = MainWindow()
    editor.show()
    palette = editor.chrome.tool_palette
    for width, height in ((1366, 738), (950, 500), (1200, 900)):
        editor.resize(width, height)
        qapp.processEvents()
        assert all(
            button.isVisible() and palette.rect().contains(button.geometry())
            for button in palette.buttons
        )
        assert len(palette.buttons) == len(
            [a for a in editor.chrome.left_toolbar.actions() if not a.isSeparator()]
        )
    editor.expanded_tools_action.trigger()
    assert editor.chrome.tool_dock.isHidden() and editor.chrome.left_toolbar.isVisible()
    assert not Preferences(editor.preferences.path).data["expanded_tools"]
    editor.expanded_tools_action.trigger()
    editor.close()


def test_last_open_save_and_export_directories_survive_restart(qapp, tmp_path, monkeypatch):
    source_dir, save_dir, export_dir = [tmp_path / name for name in ("source", "save", "export")]
    for folder in (source_dir, save_dir, export_dir):
        folder.mkdir()
    source = source_dir / "pcb"
    source.write_bytes(FIXTURE.read_bytes())
    editor = MainWindow()
    editor.open_path(source)
    editor.remember_directory(save_dir)
    suggested = []
    target = save_dir / "pcb_edited.gbr"
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args: (editor.t("Preservation · preservar comandos originais"), True),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kw: (suggested.append(args[2]) or str(target), ""),
    )
    assert editor.save_as()
    assert Path(suggested[0]).parent == save_dir and target.is_file()
    viewer = Viewer3DWindow(editor)
    viewer.remember_export_path(export_dir / "PCB.jpg")
    viewer.close()
    another = MainWindow(settings_path=editor.preferences.path)
    assert another.last_directory == str(save_dir)
    new_viewer = Viewer3DWindow(another)
    assert Path(new_viewer.export_default_path("PCB.step")).parent == export_dir
    assert Path(new_viewer.export_default_path("PCB.wrl")).parent == export_dir
    assert Path(new_viewer.export_default_path("PCB.jpg")).parent == export_dir
    new_viewer.close()
    another.close()
    finish(editor, qapp)


def test_viewer_has_view_preferences_and_same_help_menu(qapp, monkeypatch):
    editor = MainWindow()
    viewer = Viewer3DWindow(editor)
    menu_list = [action.menu() for action in viewer.menuBar().actions()]
    assert [menu.title() for menu in menu_list] == [
        "&Arquivo",
        "&Visualizar",
        "&Preferências",
        "&Ajuda",
    ]
    help_actions = [a for a in menu_list[-1].actions() if not a.isSeparator()]
    assert [a.text() for a in help_actions] == [
        "Como usar",
        "Sobre",
        "Tela de apresentação",
        "Suporte / doar ao criador",
        "Relatar problemas",
    ]
    opened = []

    class About:
        def __init__(self, parent):
            opened.append(parent)

        def exec(self):
            return 0

    monkeypatch.setattr(menus, "AboutDialog", About)
    help_actions[1].trigger()
    assert opened == [viewer]
    viewer.realistic_action.trigger()
    assert not viewer.viewport.realistic and not viewer.realistic_checkbox.isChecked()
    viewer.perspective_checkbox.setChecked(False)
    assert not viewer.perspective_action.isChecked()
    editor._viewer3d = viewer
    editor.set_language("en")
    assert [menu.title() for menu in menu_list] == ["&File", "&View", "&Preferences", "&Help"]
    assert editor.measure_action.shortcut().toString() == "Shift+A"
    viewer.close()
    editor.close()


def test_busy_discards_clicks_keys_and_close_but_allows_its_modal_dialog(qapp):
    editor = MainWindow()
    editor.show()
    button = QPushButton("count", editor.canvas)
    button.show()
    calls = []
    button.clicked.connect(lambda: calls.append(1))
    token = editor.busy.begin("Carregando…")
    qapp.processEvents()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    QTest.keyClick(button, Qt.Key.Key_Space)
    editor.close()
    assert not calls and editor.isVisible()
    # An error/confirmation belonging to the operation must remain usable.
    modal = QDialog(editor)
    modal.setModal(True)
    layout = QVBoxLayout(modal)
    ok = QPushButton("OK")
    layout.addWidget(ok)
    ok.clicked.connect(modal.accept)
    modal.show()
    qapp.processEvents()
    QTest.mouseClick(
        modal.windowHandle(), Qt.MouseButton.LeftButton, pos=ok.mapTo(modal, ok.rect().center())
    )
    wait_until(qapp, lambda: not modal.isVisible())
    editor.busy.end(token)
    qapp.processEvents()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert calls == [1]
    editor.close()


def test_input_lock_waits_for_processing_in_both_windows(qapp):
    editor = MainWindow()
    viewer = Viewer3DWindow(editor)
    first = editor.busy.begin("Carregando…")
    second = viewer.busy.begin("Gerando PCB 3D…")
    editor.busy.end(first)
    qapp.processEvents()
    assert editor.busy.input_guard.locked
    viewer.busy.end(second)
    qapp.processEvents()
    assert not editor.busy.input_guard.locked
    viewer.close()
    editor.close()


def test_loading_batch_is_serial_even_when_gui_events_are_reentered(qapp, tmp_path, monkeypatch):
    editor = MainWindow()
    paths = []
    for index in range(5):
        path = tmp_path / f"pcb_{index}"
        path.write_bytes(FIXTURE.read_bytes())
        paths.append(path)
    auxiliary = tmp_path / "fp-info-cache"
    auxiliary.write_text("0\n")
    invalid = tmp_path / "invalid.gbr"
    invalid.write_text("this is not Gerber")
    errors, activity, commits = [], [], []
    monkeypatch.setattr(editor, "show_error", lambda *values: errors.append(values))
    original_run, original_commit = ImportJob.run, editor._commit_import_layers
    original_rebuild = editor.canvas.rebuild
    rebuilds = []

    def rebuild(layers):
        rebuilds.append(1)
        original_rebuild(layers)

    def run(job):
        assert not editor._applying_import
        activity.append(job.path.name)
        original_run(job)

    def commit():
        assert editor._applying_import
        if not commits:
            previous_activity = list(activity)
            QTimer.singleShot(0, lambda: editor.open_paths_async([paths[-1]]))
            qapp.processEvents()  # Deliberate reentry: no next worker may start here.
            assert activity == previous_activity
        commits.extend(layer.name for layer, _ in editor._import_prepared)
        original_commit()

    monkeypatch.setattr(ImportJob, "run", run)
    monkeypatch.setattr(editor, "_commit_import_layers", commit)
    monkeypatch.setattr(editor.canvas, "rebuild", rebuild)
    editor.open_paths_async([*paths[:-1], auxiliary, invalid])
    wait_until(qapp, lambda: not editor._import_jobs)
    assert commits == [p.name for p in paths]
    assert len(rebuilds) == 2  # One scene assembly per batch, including the late request.
    assert (
        len(errors) == 1 and "invalid.gbr" in errors[0][1] and "fp-info-cache" not in errors[0][1]
    )
    assert not editor.busy.operations and not editor.busy.input_guard.locked
    assert auxiliary.read_text() == "0\n"
    assert all(path.read_bytes() == FIXTURE.read_bytes() for path in paths)
    editor.undo_edit()
    assert len(editor.layers) == 4
    editor.undo_edit()
    assert not editor.layers
    editor.redo_edit()
    editor.redo_edit()
    assert len(editor.layers) == 5
    finish(editor, qapp)


def test_auxiliary_name_never_hides_valid_gerber_data(tmp_path):
    path = tmp_path / "fp-info-cache"
    path.write_bytes(FIXTURE.read_bytes())
    assert not is_auxiliary_file(path)


def test_malformed_gerber_failure_does_not_lock_the_next_batch(qapp, tmp_path, monkeypatch):
    editor = MainWindow()
    bad = tmp_path / "bad.gbr"
    bad.write_text("invalid")
    errors = []
    monkeypatch.setattr(editor, "show_error", lambda *args: errors.append(args))
    editor.open_paths_async([bad])
    wait_until(qapp, lambda: not editor._import_jobs)
    assert errors and not editor.busy.input_guard.locked
    editor.open_paths_async([FIXTURE])
    wait_until(qapp, lambda: not editor._import_jobs)
    assert len(editor.layers) == 1 and not editor.busy.input_guard.locked
    finish(editor, qapp)


def test_new_preferences_reject_invalid_types(tmp_path):
    prefs = Preferences(tmp_path / "preferences.json")
    for value in (
        {"expanded_tools": "yes"},
        {"last_directory": 123},
        {"last_export_directory": []},
    ):
        with pytest.raises(ValueError):
            prefs.set(**value)
