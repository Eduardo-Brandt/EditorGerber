"""Reusable 3D detail and selected-layer foreground regressions."""

import threading
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import GerberObject
from gerber_editor.core.primitives import Point
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.graphics.graphics_items import ObjectItem
from gerber_editor.tools.demo import demo_layer
from gerber_editor.tools.shapes import rectangle_region
from gerber_editor.viewer3d import mesh as mesh_module
from gerber_editor.viewer3d import window as viewer_module
from gerber_editor.viewer3d.mesh import build_board, prepare_board
from gerber_editor.viewer3d.window import Viewer3DWindow


def wait_until(qapp, predicate):
    deadline = monotonic() + 10
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt operation timed out"
    qapp.processEvents()


@pytest.fixture
def viewer(qapp, monkeypatch):
    editor = MainWindow()
    editor.add_layer(demo_layer())
    window = Viewer3DWindow(editor)
    editor._viewer3d = window
    monkeypatch.setattr(window, "isVisible", lambda: True)
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    yield editor, window
    wait_until(qapp, lambda: window._job is None)
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    editor.close()


def test_prepared_details_keep_holes_and_match_full_build_without_composition(monkeypatch):
    copper = GerberLayer("F.Cu.gbr", function="F.Cu")
    copper.objects = [GerberObject(rectangle_region(Point.of(0, 0), Point.of(20, 10)), None)]
    drill = GerberParser().parse_file(Path(__file__).resolve().parents[1] / "fixtures/drill.gbr")
    layers = [copper, drill]
    expected = {tol: build_board(layers, tolerance=tol) for tol in (0.01, 0.025, 0.1)}
    prepared = prepare_board(layers)

    def unexpected(*args, **kwargs):
        pytest.fail("Changing detail recomposed source Gerbers")

    for name in ("compose_layer", "object_geometry", "outline_geometry", "drill_geometry"):
        monkeypatch.setattr(mesh_module, name, unexpected)
    for tolerance, original in expected.items():
        mesh = build_board(prepared, tolerance=tolerance)
        assert mesh.outline.equals(original.outline)
        assert not mesh.outline.covers(mesh_module.box(4.99, 4.99, 5.01, 5.01))
        assert mesh.triangles == original.triangles
        for actual, previous in zip(mesh.parts, original.parts, strict=True):
            assert actual.geometry.equals(previous.geometry)
            np.testing.assert_array_equal(actual.vertices, previous.vertices)


def test_detail_switch_reuses_preparation_and_cached_meshes(viewer, qapp, monkeypatch):
    _, window = viewer
    preparations, builds = [], []

    def prepare(*args):
        preparations.append(1)
        return prepare_board(*args)

    def build(*args):
        builds.append(args[-1])
        return build_board(*args)

    monkeypatch.setattr(viewer_module, "prepare_board", prepare)
    monkeypatch.setattr(viewer_module, "build_board", build)
    window.rebuild()
    wait_until(qapp, lambda: not window._dirty)
    normal = window.viewport.mesh
    window.viewport.yaw, window.viewport.distance, window.viewport.pan_x = 17, 94, 3
    window.viewport.hidden.add(normal.parts[-1].key)
    for index in (0, 2, 1):
        window.detail.setCurrentIndex(index)
        wait_until(qapp, lambda: not window._dirty)
    assert preparations == [1] and len(builds) == 3
    assert window.viewport.mesh is normal and window._job is None
    assert (window.viewport.yaw, window.viewport.distance, window.viewport.pan_x) == (17, 94, 3)
    assert normal.parts[-1].key in window.viewport.hidden
    assert window.tree.topLevelItem(window.tree.topLevelItemCount() - 1).checkState(0) == (
        Qt.CheckState.Unchecked
    )
    window.thickness.editingFinished.emit()  # Unchanged value must not trigger a build.
    qapp.processEvents()
    assert len(builds) == 3
    window.thickness.set_mm(Decimal("2.4"))
    window.thickness.editingFinished.emit()
    wait_until(qapp, lambda: not window._dirty)
    assert len(preparations) == 1 and len(builds) == 4
    assert window.viewport.mesh.size[2] == 2.4


def test_edits_and_explicit_refresh_invalidate_all_details(viewer, qapp, monkeypatch):
    editor, window = viewer
    preparations = []

    def prepare(*args):
        preparations.append(1)
        return prepare_board(*args)

    monkeypatch.setattr(viewer_module, "prepare_board", prepare)
    window.rebuild()
    wait_until(qapp, lambda: not window._dirty)
    original = window.viewport.mesh
    window.detail.setCurrentIndex(0)
    wait_until(qapp, lambda: not window._dirty)
    layer = editor.layers[0]
    layer.objects.append(replace(layer.objects[0], id="new_object"))
    editor.refresh()
    assert window._geometry is None and not window._mesh_cache
    window.detail.setCurrentIndex(1)
    wait_until(qapp, lambda: not window._dirty)
    assert len(preparations) == 2 and window.viewport.mesh is not original
    window.reload_action.trigger()
    wait_until(qapp, lambda: not window._dirty)
    assert len(preparations) == 3


def test_changing_detail_during_worker_never_displays_outdated_settings(viewer, qapp, monkeypatch):
    _, window = viewer
    window.rebuild()
    wait_until(qapp, lambda: not window._dirty)
    normal = window.viewport.mesh
    started, release = threading.Event(), threading.Event()

    def paused(*args):
        started.set()
        assert release.wait(5)
        return build_board(*args)

    monkeypatch.setattr(viewer_module, "build_board", paused)
    try:
        window.detail.setCurrentIndex(0)
        assert not any(action.isEnabled() for action in window.export_actions)
        wait_until(qapp, started.is_set)
        window.detail.setCurrentIndex(2)
        release.set()
        wait_until(qapp, lambda: not window._dirty and window._job is None)
        assert window.viewport.mesh is not normal
        assert window._mesh_settings[1] == 0.1
        builds = []
        monkeypatch.setattr(viewer_module, "build_board", lambda *args: builds.append(1))
        window.detail.setCurrentIndex(0)  # The completed superseded detail was cached.
        wait_until(qapp, lambda: not window._dirty)
        assert window._mesh_settings[1] == 0.01 and not builds
    finally:
        release.set()


def test_clicking_layer_changes_visible_overlap_and_hit_priority_without_recomposition(
    qapp, monkeypatch
):
    editor = MainWindow()
    for color in ("#ff0000", "#0000ff"):
        layer = GerberLayer(color, color=color, opacity=1)
        layer.objects = [GerberObject(rectangle_region(Point.of(0, 0), Point.of(20, 10)), None)]
        editor.add_layer(layer)
    original = list(editor.layers)
    editor.show()
    editor.canvas.axes_visible = False
    editor.canvas.fit_all()
    qapp.processEvents()
    location = editor.canvas.mapFromScene(QPointF(5, 5))
    assert editor.canvas.viewport().grab().toImage().pixelColor(location).name() == "#0000ff"

    def unexpected(*args):
        pytest.fail("Activating a layer rebuilt its geometry")

    monkeypatch.setattr(editor.canvas.renderer, "paths", unexpected)
    tree = editor.layer_panel.tree
    for row, color in ((1, "#ff0000"), (0, "#0000ff")):
        item = tree.topLevelItem(row)
        QTest.mouseClick(
            tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualItemRect(item).center()
        )
        wait_until(qapp, lambda expected=color: editor.active_layer.color == expected)
        assert editor.canvas.viewport().grab().toImage().pixelColor(location).name() == color
        hits = [value for value in editor.canvas.items(location) if isinstance(value, ObjectItem)]
        assert hits[0].layer is editor.active_layer
        assert editor.layers == original
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    editor.close()
