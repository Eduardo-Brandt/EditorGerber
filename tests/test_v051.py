"""Regression checks for processing feedback, deferred 3D refresh and tree lifetime."""

import json
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from time import monotonic

import pytest
import shiboken6
from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.primitives import Line, Point
from gerber_editor.tools.demo import demo_layer
from gerber_editor.viewer3d import window as viewer_module
from gerber_editor.viewer3d.mesh import build_board
from gerber_editor.viewer3d.window import Viewer3DWindow


def wait_until(qapp, predicate, timeout=5):
    deadline = monotonic() + timeout
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt operation did not finish"


def finish(window):
    for layer in window.layers:
        layer.saved_signature = layer.signature()
    window.close()


@pytest.fixture
def viewer(qapp, monkeypatch):
    editor = MainWindow()
    editor.add_layer(demo_layer())
    window = Viewer3DWindow(editor)
    editor._viewer3d = window
    focused = {"value": False}
    # Exercise real queued events and mesh workers without requiring offscreen OpenGL.
    monkeypatch.setattr(window, "isVisible", lambda: True)
    monkeypatch.setattr(window, "isActiveWindow", lambda: focused["value"])
    yield editor, window, focused
    wait_until(qapp, lambda: window._job is None)
    finish(editor)


def activate(window, focused):
    focused["value"] = True
    QApplication.sendEvent(window, QEvent(QEvent.Type.WindowActivate))


def edit_board(editor):
    layer = editor.layers[0]
    layer.objects.append(
        replace(
            layer.objects[0],
            id=f"added_{len(layer.objects)}",
            geometry=Line(Point.of(-2, -3), Point.of(-1, -3)),
        )
    )
    editor.refresh()


def test_processing_card_rotates_in_center_and_tracks_window_resize(qapp):
    editor = MainWindow()
    editor.show()
    first = editor.busy.begin("Carregando…")
    QTest.qWait(50)
    overlay = editor.busy.overlay
    before = overlay.hourglass.angle
    QTest.qWait(100)
    assert overlay.isVisible() and overlay.hourglass.angle != before
    for width, height in ((900, 650), (1500, 950)):
        editor.resize(width, height)
        qapp.processEvents()
        expected = editor.canvas.mapTo(editor, editor.canvas.rect().center())
        assert (overlay.geometry().center() - expected).manhattanLength() <= 2
    second = editor.busy.begin("Salvando…")
    editor.busy.end(first)
    assert overlay.isVisible() and overlay.label.text() == "Salvando…"
    editor.busy.end(second)
    assert not overlay.isVisible() and not editor.busy.timer.isActive()
    editor.close()


def test_drawing_pending_status_does_not_cover_the_drawing(qapp):
    editor = MainWindow()
    editor.busy.pending(True, "Escolha o próximo ponto")
    assert editor.busy.active and editor.busy.overlay.isHidden()
    with pytest.raises(ValueError), editor.busy.operation("Validando…"):
        raise ValueError("invalid")
    assert not editor.busy.operations and editor.busy.overlay.isHidden()
    editor.busy.pending(False)
    editor.close()


def test_3d_updates_once_on_return_and_preserves_camera(viewer, qapp, monkeypatch):
    editor, window, focused = viewer
    builds = []

    def counted(*args):
        builds.append(args[0])
        return build_board(*args)

    monkeypatch.setattr(viewer_module, "build_board", counted)
    activate(window, focused)
    wait_until(qapp, lambda: window.viewport.mesh is not None)
    first_mesh = window.viewport.mesh
    window.viewport.yaw, window.viewport.distance, window.viewport.pan_x = 12, 85, 4
    focused["value"] = False
    for _ in range(3):
        edit_board(editor)
    QTest.qWait(80)
    assert len(builds) == 1 and window.viewport.mesh is first_mesh
    for _ in range(5):
        activate(window, focused)
    wait_until(qapp, lambda: not window._dirty and window._job is None)
    assert len(builds) == 2 and window.viewport.mesh is not first_mesh
    assert (window.viewport.yaw, window.viewport.distance, window.viewport.pan_x) == (12, 85, 4)
    activate(window, focused)
    QTest.qWait(50)
    assert len(builds) == 2  # No edit: activation does not recompute geometry.


def test_old_worker_result_cannot_replace_edited_pcb(viewer, qapp, monkeypatch):
    editor, window, focused = viewer
    started, release = threading.Event(), threading.Event()
    calls = []

    def paused(*args):
        calls.append(1)
        if len(calls) == 1:
            started.set()
            assert release.wait(5)
        return build_board(*args)

    monkeypatch.setattr(viewer_module, "build_board", paused)
    try:
        activate(window, focused)
        wait_until(qapp, started.is_set)
        assert window.busy.operations
        focused["value"] = False
        edit_board(editor)
        release.set()
        wait_until(qapp, lambda: window._job is None)
        assert window.viewport.mesh is None and window._dirty and not window.busy.operations
        activate(window, focused)
        wait_until(qapp, lambda: window.viewport.mesh is not None)
        assert len(calls) == 2 and window._mesh_revision == window._revision
    finally:
        release.set()


def test_return_during_export_defers_build_until_export_finishes(viewer, qapp):
    editor, window, focused = viewer
    window._export_job = object()
    edit_board(editor)
    activate(window, focused)
    QTest.qWait(50)
    assert window._job is None and window._dirty
    window._export_finished("PCB.wrl", "")
    wait_until(qapp, lambda: window.viewport.mesh is not None)
    assert not window._dirty


def test_activation_waits_until_editor_finishes_mutation(viewer, qapp):
    editor, window, focused = viewer
    token = editor.busy.begin("Atualizando geometria…")
    activate(window, focused)
    QTest.qWait(100)
    assert window._job is None
    edit_board(editor)
    editor.busy.end(token)
    wait_until(qapp, lambda: window.viewport.mesh is not None)
    assert window._mesh_revision == window._revision


def test_mesh_failure_clears_indicator_and_can_retry_on_next_entry(viewer, qapp, monkeypatch):
    _, window, focused = viewer

    def fail(*args):
        raise ValueError("failed mesh")

    monkeypatch.setattr(viewer_module, "build_board", fail)
    activate(window, focused)
    wait_until(qapp, lambda: bool(window.last_error))
    assert not window.busy.operations and window.busy.overlay.isHidden()
    assert window._dirty and window._job is None
    monkeypatch.setattr(viewer_module, "build_board", build_board)
    activate(window, focused)
    wait_until(qapp, lambda: window.viewport.mesh is not None)
    assert not window.last_error


def test_closing_all_layers_clears_3d_on_next_entry(viewer, qapp):
    editor, window, focused = viewer
    activate(window, focused)
    wait_until(qapp, lambda: window.viewport.mesh is not None)
    focused["value"] = False
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    editor.close_all()
    assert window.viewport.mesh is not None
    activate(window, focused)
    wait_until(qapp, lambda: window.viewport.mesh is None)
    assert not window._dirty and not any(a.isEnabled() for a in window.export_actions)


def test_layer_items_survive_activation_visibility_and_undo(qapp):
    editor = MainWindow()
    editor.add_layer(demo_layer())
    editor.add_layer(demo_layer())
    tree = editor.layer_panel.tree
    first, second = tree.topLevelItem(0), tree.topLevelItem(1)
    layer = editor.layers[0]
    for _ in range(15):
        tree.setCurrentItem(second)
        qapp.processEvents()
        assert editor.active_layer is layer
        second.setCheckState(0, Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert not layer.visible
        editor.undo_edit()
        assert layer.visible
        tree.setCurrentItem(first)
        qapp.processEvents()
        assert shiboken6.isValid(first) and shiboken6.isValid(second)
        assert first is tree.topLevelItem(0) and second is tree.topLevelItem(1)
    finish(editor)


def test_rapid_checkbox_toggles_keep_last_requested_value(qapp):
    editor = MainWindow()
    editor.add_layer(demo_layer())
    item = editor.layer_panel.tree.topLevelItem(0)
    item.setCheckState(0, Qt.CheckState.Unchecked)
    item.setCheckState(0, Qt.CheckState.Checked)
    qapp.processEvents()
    assert editor.layers[0].visible and item.checkState(0) == Qt.CheckState.Checked
    finish(editor)


def test_persistent_logs_capture_python_qt_and_worker_exceptions(tmp_path):
    code = """
import faulthandler, json, sys, threading
from pathlib import Path
from PySide6.QtCore import qWarning
from gerber_editor.app.diagnostics import Diagnostics
previous = sys.excepthook
d = Diagnostics(Path(sys.argv[1]))
try:
    raise RuntimeError('regression exception')
except RuntimeError:
    sys.excepthook(*sys.exc_info())
qWarning('regression Qt warning')
def fail():
    raise RuntimeError('regression worker exception')
t = threading.Thread(target=fail)
t.start()
t.join()
faulthandler.dump_traceback(file=d.fault_file)
d.close()
assert sys.excepthook is previous
print(json.dumps({'log': str(d.log_path), 'fault': str(d.fault_path)}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    paths = json.loads(result.stdout)
    log = Path(paths["log"]).read_text(encoding="utf-8")
    assert all(
        text in log
        for text in (
            "regression exception",
            "regression Qt warning",
            "regression worker exception",
            "Application event loop finished",
        )
    )
    assert "Current thread" in Path(paths["fault"]).read_text(encoding="utf-8")
