"""External file drops must reach the editor over its canvas and layer manager."""

from pathlib import Path
from time import monotonic, sleep

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from gerber_editor.app.main_window import MainWindow

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/basic.gbr"
COPY = Qt.DropAction.CopyAction
MOVE = Qt.DropAction.MoveAction


def wait_for_import(qapp, window):
    deadline = monotonic() + 10
    while window._import_jobs and monotonic() < deadline:
        qapp.processEvents()
        sleep(0.01)
    qapp.processEvents()
    assert not window._import_jobs


@pytest.fixture
def editor(qapp):
    window = MainWindow()
    errors = []
    window.show_error = lambda title, error: errors.append((title, str(error)))
    window.show()
    qapp.processEvents()
    yield window, errors
    wait_for_import(qapp, window)
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()
    qapp.processEvents()


def mime_for(*paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def drop_files(qapp, target, mime, actions=COPY | MOVE):
    button, modifiers = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    enter = QDragEnterEvent(QPoint(10, 10), actions, mime, button, modifiers)
    qapp.sendEvent(target, enter)
    move = QDragMoveEvent(QPoint(20, 20), actions, mime, button, modifiers)
    qapp.sendEvent(target, move)
    drop = QDropEvent(QPointF(20, 20), actions, mime, button, modifiers)
    qapp.sendEvent(target, drop)
    return enter, move, drop


@pytest.mark.parametrize("surface", ["window", "canvas", "layers"])
def test_file_drop_adds_gerber_and_excellon_with_progress(editor, qapp, tmp_path, surface):
    window, errors = editor
    existing = window.open_path(FIXTURE)
    gerber = tmp_path / "Placa revisão ç sem extensão"
    gerber.write_bytes(FIXTURE.read_bytes())
    drill = tmp_path / "Placa-PTH.xln"
    drill.write_text("M48\nMETRIC\nT1C1.0\n%\nG90\nT1\nX5.0Y4.0\nM30\n", encoding="ascii")
    originals = {path: path.read_bytes() for path in (gerber, drill)}
    target = {
        "window": window,
        "canvas": window.canvas.viewport(),
        "layers": window.layer_panel.tree.viewport(),
    }[surface]
    events = drop_files(qapp, target, mime_for(gerber, drill, gerber))
    assert all(event.isAccepted() and event.dropAction() == COPY for event in events)
    assert window.import_progress.isVisible()
    assert len(window._import_jobs) == 2
    wait_for_import(qapp, window)
    assert not errors
    assert existing in window.layers and len(window.layers) == 3
    imported = {layer.path: layer for layer in window.layers}
    assert gerber in imported and drill in imported
    assert imported[drill].objects
    assert not window.import_progress.active
    assert window.import_progress.value() == window.import_progress.maximum() == 2
    assert Path(window.last_directory) == tmp_path
    assert all(path.read_bytes() == original for path, original in originals.items())


@pytest.mark.parametrize("payload", ["text", "remote", "directory", "missing", "move_only"])
def test_unsupported_drops_do_not_open_anything(editor, qapp, tmp_path, payload):
    window, errors = editor
    mime = QMimeData()
    actions = COPY | MOVE
    if payload == "text":
        mime.setText(str(FIXTURE))
    elif payload == "remote":
        mime.setUrls([QUrl("https://example.com/board.gbr")])
    elif payload == "directory":
        mime = mime_for(tmp_path)
    elif payload == "missing":
        mime = mime_for(tmp_path / "missing.gbr")
    else:
        mime = mime_for(FIXTURE)
        actions = MOVE
    _, _, drop = drop_files(qapp, window, mime, actions)
    assert not drop.isAccepted()
    assert not window._import_jobs and not window.layers and not errors


@pytest.mark.parametrize("flag", ["_save_all_running", "_save_all_preparing"])
def test_file_drop_is_rejected_while_saving(editor, qapp, flag):
    window, errors = editor
    setattr(window, flag, True)
    try:
        enter, _, drop = drop_files(qapp, window, mime_for(FIXTURE))
        assert not enter.isAccepted() and not drop.isAccepted()
        assert not window._import_jobs and not window.layers and not errors
    finally:
        setattr(window, flag, False)


def test_invalid_gerber_uses_existing_batch_error_handling(editor, qapp, tmp_path):
    window, errors = editor
    invalid = tmp_path / "invalid.gbr"
    invalid.write_text("Not a Gerber", encoding="ascii")
    _, _, drop = drop_files(qapp, window.canvas.viewport(), mime_for(FIXTURE, invalid))
    assert drop.isAccepted()
    wait_for_import(qapp, window)
    assert len(window.layers) == 1 and window.layers[0].path == FIXTURE
    assert len(errors) == 1 and invalid.name in errors[0][1]
    assert not window.import_progress.active and not window.busy.operations
