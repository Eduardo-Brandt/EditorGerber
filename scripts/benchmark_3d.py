"""Compare archived and current 3D generation on read-only Gerbers.

python -m scripts.benchmark_3d FILE... --baseline BACKUP.zip --output output/v09/performance
The common 2D GEOS cache is prepared outside the measured 3D phases.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from gerber_editor.geometry.boolean import compose_layer, object_geometry
from gerber_editor.geometry.tiling import MIN_TILED_OBJECTS, TiledComposition
from gerber_editor.geometry.transforms import translate_geometry
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.viewer3d.mesh import build_board, prepare_board


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.baseline) as archive:
        module_path = args.output / "baseline_mesh.py"
        module_path.write_bytes(archive.read("gerber_editor/viewer3d/mesh.py"))
    spec = importlib.util.spec_from_file_location("baseline_mesh", module_path)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in args.files}
    report = {
        "method": "No profiler; common warm 2D GEOS cache; same process, files and detail",
        "files": [],
        "timings_seconds": {},
    }

    def timed(name, function):
        started = perf_counter()
        value = function()
        report["timings_seconds"][name] = perf_counter() - started
        (args.output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(name, round(report["timings_seconds"][name], 3), "s", flush=True)
        return value

    layers = timed("parse", lambda: [GerberParser().parse_file(path) for path in args.files])
    report["files"] = [
        {"name": layer.name, "role": layer.function, "objects": len(layer.objects)}
        for layer in layers
    ]
    print(json.dumps(report["files"]), flush=True)
    objects = timed(
        "common_primitive_cache",
        lambda: {obj.id: (obj, object_geometry(obj)) for layer in layers for obj in layer.objects},
    )
    tiled = {}

    def compose_2d():
        result = {}
        for layer in layers:
            geometries = {obj.id: objects[obj.id][1] for obj in layer.objects}
            if len(layer.objects) >= MIN_TILED_OBJECTS:
                composition = TiledComposition(layer.objects, geometries, tiled.get(layer.id))
                tiled[layer.id] = composition
                value = tuple(tile.geometry for tile in composition.tiles.values())
            else:
                value = compose_layer(layer.objects, geometries)
            result[layer.id] = layer.signature(), value
        return result

    snapshots = timed("common_2d_composition", compose_2d)
    # Bounds are cached on the immutable objects for both implementations.
    timed("common_bounds", lambda: [layer.bounds for layer in layers])
    old_prepared = timed("before_prepare", lambda: baseline.prepare_board(layers, objects))
    old_mesh = timed("before_mesh_normal", lambda: baseline.build_board(old_prepared))
    prepared = timed("after_prepare", lambda: prepare_board(layers, objects, None, snapshots))
    mesh = timed("after_mesh_normal", lambda: build_board(prepared))

    def compare(left, right):
        result = []
        assert len(left.parts) == len(right.parts)
        for a, b in zip(left.parts, right.parts, strict=True):
            assert a.key == b.key and a.material == b.material
            difference = a.geometry.symmetric_difference(b.geometry).area
            # Cell clipping may insert collinear boundary vertices. The display
            # simplifier may choose a different point within its 0.025 mm limit.
            assert difference <= max(1e-7, a.geometry.length * 0.05)
            result.append(
                {
                    "part": a.name,
                    "difference_area_mm2": difference,
                }
            )
        return result

    report["raw_layer_difference_area_mm2"] = {
        a.name: a.geometry.symmetric_difference(b.geometry).area
        for a, b in zip(old_prepared.layers, prepared.layers, strict=True)
    }
    assert all(value < 1e-7 for value in report["raw_layer_difference_area_mm2"].values())
    report["initial_geometry_comparison"] = compare(old_mesh, mesh)
    report["triangles"] = {"before": old_mesh.triangles, "after": mesh.triangles}
    prepared_again = timed(
        "after_no_change_prepare",
        lambda: prepare_board(layers, objects, prepared._cache, snapshots),
    )
    same_mesh = timed(
        "after_no_change_mesh", lambda: build_board(prepared_again, previous=mesh._cache)
    )
    report["no_change_reuses_all_parts"] = all(
        a is b for a, b in zip(mesh.parts, same_mesh.parts, strict=True)
    )
    assert report["no_change_reuses_all_parts"]

    editable = next((layer for layer in layers if layer.function.endswith(".Silk")), layers[0])
    # Move an object well inside the bounds so this models a local PCB edit.
    chosen = len(editable.objects) // 2
    original = editable.objects[chosen]
    moved = replace(
        original, geometry=translate_geometry(original.geometry, Decimal("0.1"), Decimal("0.1"))
    )
    editable.objects[chosen] = moved
    objects[moved.id] = moved, object_geometry(moved)
    snapshots = timed("common_2d_after_edit", compose_2d)
    old_updated = timed("before_update", lambda: baseline.build_board(layers, cache=objects))

    def update():
        changed = prepare_board(layers, objects, prepared._cache, snapshots)
        return build_board(changed, previous=mesh._cache)

    updated = timed("after_update", update)
    report["edit"] = {"layer": editable.name, "object_index": chosen, "translation_mm": [0.1, 0.1]}
    report["updated_geometry_comparison"] = compare(old_updated, updated)
    report["updated_reused_parts"] = [
        part.name for part in updated.parts if any(part is before for before in mesh.parts)
    ]
    report["sources_unchanged"] = all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
        for path, digest in hashes.items()
    )
    assert report["sources_unchanged"]
    times = report["timings_seconds"]
    report["initial_speedup"] = (times["before_prepare"] + times["before_mesh_normal"]) / (
        times["after_prepare"] + times["after_mesh_normal"]
    )
    report["update_speedup"] = times["before_update"] / times["after_update"]
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
