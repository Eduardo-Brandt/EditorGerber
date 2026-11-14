"""3D geometry reuse, dependency invalidation and vectorized mesh correctness."""

import threading
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from time import monotonic

import numpy as np
import pytest
from PySide6.QtTest import QTest
from shapely import constrained_delaunay_triangles
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Polygon, box

from gerber_editor.app.main_window import MainWindow
from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Flash, Line, Point
from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.geometry.transforms import translate_geometry
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.graphics import renderer as renderer_module
from gerber_editor.graphics.renderer import LayerRenderer
from gerber_editor.tools.shapes import create_shape, rectangle_region
from gerber_editor.viewer3d import mesh as mesh_module
from gerber_editor.viewer3d import window as window_module
from gerber_editor.viewer3d.mesh import build_board, polygons, prepare_board, substrate, surface
from gerber_editor.viewer3d.window import Viewer3DWindow


def pcb():
    edge = GerberLayer("outline", function="Edge.Cuts")
    edge.objects = create_shape(edge, "rectangle", [Point.of(0, 0), Point.of(20, 10)], D("0.1"))
    copper = GerberLayer("copper", function="F.Cu")
    copper.objects = [
        GerberObject(Line(Point.of(2, 5), Point.of(18, 5)), Aperture(10, "C", (D(1),)))
    ]
    mask = GerberLayer("mask", function="F.Mask")
    mask.objects = [GerberObject(Flash(Point.of(2, 5)), Aperture(10, "C", (D(2),)))]
    silk = GerberLayer("silk", function="F.Silk")
    silk.objects = [GerberObject(rectangle_region(Point.of(3, 8), Point.of(6, 9)), None)]
    drill = GerberParser().parse_file(Path(__file__).resolve().parents[1] / "fixtures/drill.gbr")
    return [edge, copper, mask, silk, drill]


def move(layer):
    obj = layer.objects[0]
    layer.objects[0] = replace(obj, geometry=translate_geometry(obj.geometry, D("0.1"), D("0.1")))


def wait_until(qapp, predicate):
    deadline = monotonic() + 10
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt operation timed out"
    qapp.processEvents()


@pytest.fixture
def viewer(qapp, monkeypatch):
    editor = MainWindow()
    for layer in pcb():
        editor.add_layer(layer)
    window = Viewer3DWindow(editor)
    editor._viewer3d = window
    monkeypatch.setattr(window, "isVisible", lambda: True)
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    yield editor, window
    wait_until(qapp, lambda: window._job is None)
    for layer in editor.layers:
        layer.saved_signature = layer.signature()
    editor.close()


@pytest.mark.parametrize(
    "geometry",
    [
        GeometryCollection(),
        box(-3, -2, 7, 8),
        Polygon([(0, 0), (20, 0), (20, 10), (0, 10)], [[(3, 3), (3, 6), (7, 6), (7, 3)]]),
        MultiPolygon([box(-20, -10, -5, -2), box(3, 4, 9, 10)]),
        GeometryCollection([box(-3, -4, 3, 4), LineString([(20, 20), (25, 20)])]),
    ],
)
def test_bulk_triangle_vertices_match_scalar_reference(geometry):
    center = (2.371, -1.257)
    xy = np.asarray(
        [
            list(triangle.exterior.coords)[:3]
            for triangle in polygons(constrained_delaunay_triangles(geometry))
        ],
        dtype=np.float32,
    ).reshape(-1, 2)
    expected = np.zeros((len(xy), 6), dtype=np.float32)
    expected[:, :2] = xy - np.asarray(center)
    expected[:, 2], expected[:, 5] = 0.8, 1
    np.testing.assert_array_equal(surface(geometry, 0.8, 1, center), expected)


def test_substrate_triangulates_once_and_keeps_hole_wall_normals(monkeypatch):
    geometry = box(0, 0, 20, 10).difference(box(3, 3, 7, 6))
    calls = []

    def counted(value):
        calls.append(1)
        return constrained_delaunay_triangles(value)

    monkeypatch.setattr(mesh_module, "constrained_delaunay_triangles", counted)
    vertices = substrate(geometry, 1.6, (0, 0))
    assert len(calls) == 1
    top, bottom = vertices[vertices[:, 5] == 1], vertices[vertices[:, 5] == -1]
    np.testing.assert_array_equal(top[:, :2], bottom[:, :2])
    np.testing.assert_array_equal(top[:, 2], -bottom[:, 2])
    interior = vertices[
        (vertices[:, 0] == 3) & (vertices[:, 1] > 3) & (vertices[:, 1] <= 6) & (vertices[:, 5] == 0)
    ]
    assert np.any(interior[:, 3] > 0)  # Into the void from its left wall.
    assert np.all(np.isfinite(vertices))


def test_2d_snapshot_reuses_polarity_composition_and_rejects_stale_sources(qapp, monkeypatch):
    monkeypatch.setattr(renderer_module, "MIN_TILED_OBJECTS", 8)
    layer = GerberLayer("copper", function="F.Cu")
    layer.objects = [GerberObject(rectangle_region(Point.of(-10, -10), Point.of(50, 30)), None)]
    for index in range(25):
        layer.objects.append(
            GerberObject(
                Flash(Point.of(index * 2, 10)),
                Aperture(10, "C", (D(5),)),
                Polarity.DARK if index % 3 == 0 else Polarity.CLEAR,
            )
        )
    renderer = LayerRenderer()
    renderer.paths(layer)
    snapshots = renderer.geometry_snapshot([layer])
    expected = compose_layer(layer.objects, {obj.id: object_geometry(obj) for obj in layer.objects})
    original = mesh_module.compose_layer
    calls = []

    def compose(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(mesh_module, "compose_layer", compose)
    prepared = prepare_board([layer], renderer._objects, compositions=snapshots)
    assert not calls
    assert prepared.layers[0].geometry.symmetric_difference(expected).area < 1e-8
    move(layer)
    changed = prepare_board([layer], renderer._objects, prepared._cache, snapshots)
    assert len(calls) == 1  # An old 2D snapshot must never replace a newer edit.
    expected = original(layer.objects, {obj.id: object_geometry(obj) for obj in layer.objects})
    assert changed.layers[0].geometry.symmetric_difference(expected).area < 1e-8
    renderer.prune([])
    assert not renderer.geometry_snapshot([layer])
    assert not renderer._flat_geometries and not renderer._compositions


def test_adopting_a_replaced_layer_clears_the_other_composition_mode(qapp, monkeypatch):
    monkeypatch.setattr(renderer_module, "MIN_TILED_OBJECTS", 2)
    layer = pcb()[1]
    renderer = LayerRenderer()
    original = layer.objects[0]
    for count in (2, 1, 3):
        layer.objects = [
            replace(
                original,
                id=f"{index}",
                geometry=translate_geometry(original.geometry, D(index), D(0)),
            )
            for index in range(count)
        ]
        worker = LayerRenderer()
        worker.paths(layer)
        renderer.adopt(worker)
        prepared = prepare_board([layer], compositions=renderer.geometry_snapshot([layer]))
        expected = compose_layer(
            layer.objects, {obj.id: object_geometry(obj) for obj in layer.objects}
        )
        assert prepared.layers[0].geometry.symmetric_difference(expected).area < 1e-8
        assert (layer.id in renderer._compositions) == (count >= 2)
        assert (layer.id in renderer._flat_geometries) == (count < 2)


@pytest.mark.parametrize("edited_role", ["F.Silk", "F.Cu", "Drill.PTH", "Edge.Cuts", "F.Mask"])
def test_incremental_edit_reuses_only_parts_with_unchanged_dependencies(edited_role):
    layers = pcb()
    prepared = prepare_board(layers)
    mesh = build_board(prepared)
    edited = next(layer for layer in layers if layer.function == edited_role)
    move(edited)
    updated_geometry = prepare_board(layers, previous=prepared._cache)
    updated = build_board(updated_geometry, previous=mesh._cache)
    fresh = build_board(layers)
    assert updated.outline.equals(fresh.outline)
    assert len(updated.parts) == len(fresh.parts)
    for actual, expected in zip(updated.parts, fresh.parts, strict=True):
        assert actual.key == expected.key and actual.material == expected.material
        assert actual.geometry.equals(expected.geometry)
        np.testing.assert_array_equal(actual.vertices, expected.vertices)
    if edited_role in ("F.Silk", "F.Cu", "F.Mask"):
        assert updated.parts[0] is mesh.parts[0]  # Physical board did not change.
    else:
        assert updated.parts[0] is not mesh.parts[0]
    if edited_role == "F.Silk":
        assert all(
            part is before
            for part, before in zip(updated.parts, mesh.parts, strict=True)
            if part.key != edited.id
        )
    if edited_role == "F.Cu":
        mask_id = next(layer.id for layer in layers if layer.function == "F.Mask")
        assert all(
            part is not before
            for part, before in zip(updated.parts, mesh.parts, strict=True)
            if part.key == mask_id
        )


def test_presentation_refresh_keeps_3d_and_explicit_update_reuses_all_mesh_parts(
    viewer, qapp, monkeypatch
):
    editor, window = viewer
    window.rebuild()
    wait_until(qapp, lambda: not window._dirty)
    mesh, revision = window.viewport.mesh, window._revision
    for layer in editor.layers:
        layer.color, layer.opacity = "#abcdef", 0.4
        layer.saved_signature = layer.signature()
    editor.layers.reverse()
    editor.refresh()
    editor.set_language("en")
    assert window._revision == revision and not window._dirty
    assert window.viewport.mesh is mesh

    def unexpected(*args):
        pytest.fail("Unchanged PCB retriangulated during explicit update")

    monkeypatch.setattr(mesh_module, "surface", unexpected)
    window.reload_action.trigger()
    wait_until(qapp, lambda: not window._dirty)
    assert all(any(part is old for old in mesh.parts) for part in window.viewport.mesh.parts)


def test_old_worker_cannot_publish_preparation_or_partial_mesh_caches(viewer, qapp, monkeypatch):
    editor, window = viewer
    started, release = threading.Event(), threading.Event()
    original = window_module.build_board

    def paused(*args):
        started.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(window_module, "build_board", paused)
    try:
        window.rebuild()
        wait_until(qapp, started.is_set)
        move(next(layer for layer in editor.layers if layer.function == "Drill.PTH"))
        editor.refresh()
        monkeypatch.setattr(window, "isActiveWindow", lambda: False)
        release.set()
        wait_until(qapp, lambda: window._job is None)
        assert (
            window._geometry is None and not window._preparation_cache and not window._build_cache
        )
        assert window.viewport.mesh is None
        monkeypatch.setattr(window, "isActiveWindow", lambda: True)
        window.request_refresh()
        wait_until(qapp, lambda: not window._dirty)
        assert window._mesh_revision == window._revision
    finally:
        release.set()
