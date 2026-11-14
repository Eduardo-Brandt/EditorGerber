"""Read-only, separate-process comparison of installed and archived 2D code.

Run from the project root using ``python -m scripts.benchmark_2d FILE
--output output/v06/current_olc``. Add ``--implementation
output/v06/baseline_052`` to measure the archived source with the same runner.
"""

import argparse
import ctypes
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path
from time import perf_counter


def memory_mib():
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_working_set",
                "working_set",
                "peak_paged",
                "paged",
                "peak_nonpaged",
                "nonpaged",
                "pagefile",
                "peak_pagefile",
                "private",
            )
        ]

    data = Counters()
    data.cb = ctypes.sizeof(data)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(data), data.cb):
        raise ctypes.WinError()
    return {name: getattr(data, name) / 1024**2 for name in ("working_set", "private")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--implementation", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--edits", action="store_true", help="Also time three single-object edits")
    args = parser.parse_args()
    sys.path.insert(0, str(args.implementation.resolve()))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication, QGraphicsItem

    from gerber_editor.gerber.parser import GerberParser
    from gerber_editor.graphics.canvas import Canvas
    from gerber_editor.validation.checks import validate_layer

    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    source = args.file.read_bytes()
    report = {
        "implementation": str(args.implementation.resolve()),
        "file": str(args.file.resolve()),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "code_sha256": {
            name: hashlib.sha256((args.implementation / name).read_bytes()).hexdigest()
            for name in (
                "gerber_editor/graphics/canvas.py",
                "gerber_editor/graphics/graphics_items.py",
                "gerber_editor/graphics/renderer.py",
                "gerber_editor/geometry/boolean.py",
                "gerber_editor/geometry/tiling.py",
                "gerber_editor/graphics/tiled_items.py",
                "gerber_editor/graphics/snapping.py",
            )
            if (args.implementation / name).is_file()
        },
        "method": "Qt offscreen raster 1200x800; medians of 7 frames; no profiler",
        "memory_initial_mib": memory_mib(),
    }

    def measure(function):
        start = perf_counter()
        result = function()
        return result, perf_counter() - start

    def frame():
        return canvas.viewport().grab().toImage()

    def sequence(action, values):
        samples = []
        for value in values:

            def render(value=value):
                action(value)
                return frame()

            _, elapsed = measure(render)
            samples.append(elapsed)
        return {"median_s": statistics.median(samples), "samples_s": samples}

    start = perf_counter()
    layer, report["parse_s"] = measure(lambda: GerberParser().parse(source, args.file.name))
    _, report["validate_s"] = measure(lambda: validate_layer(layer))
    canvas = Canvas()
    canvas.resize(1200, 800)
    canvas.active_layer_id = layer.id
    _, report["prepare_s"] = measure(lambda: canvas.renderer.paths(layer))
    print(
        json.dumps(
            {"stage": "prepared", "objects": len(layer.objects), "seconds": report["prepare_s"]}
        ),
        flush=True,
    )
    _, report["scene_s"] = measure(lambda: canvas.rebuild([layer]))
    canvas.show()
    app.processEvents()
    canvas.fit_all()
    app.processEvents()
    reference = frame()
    report["opening_s"] = perf_counter() - start
    report["memory_scene_mib"] = memory_mib()
    report["objects"] = len(layer.objects)
    reference.save(str(args.output / "initial.png"))
    center = canvas.mapToScene(canvas.viewport().rect().center())
    transform = canvas.transform()
    report["pan"] = sequence(
        lambda offset: canvas.centerOn(center.x() + offset, center.y()), (0, 2, 4, 6, 4, 2, 0)
    )

    def zoom(factor):
        canvas.setTransform(transform)
        canvas.scale(factor, factor)
        canvas.centerOn(center)

    report["zoom"] = sequence(zoom, (1, 1.1, 1.2, 1.1, 1, 0.9, 1))
    zoom(1)
    frame()
    canvas._cursor = center
    canvas._pan = QPoint(0, 0)
    report["pan_with_cursor_on_board"] = sequence(
        lambda offset: canvas.centerOn(center.x() + offset, center.y()), (0, 2, 4, 6, 4, 2, 0)
    )
    canvas._pan = None
    canvas.centerOn(center)
    canvas._cursor = type(center)()
    frame()
    original_color = layer.color

    def color(value):
        layer.color = value
        canvas.rebuild([layer])

    report["color"] = sequence(color, ("#d590ff", original_color) * 3 + ("#d590ff",))
    frame().save(str(args.output / "color.png"))
    color(original_color)
    canvas.object_items[layer.objects[0].id].setSelected(True)
    frame().save(str(args.output / "selected.png"))
    canvas.clear_selection()
    canvas.set_ghost_negatives(True)
    frame().save(str(args.output / "ghosts.png"))
    canvas.set_ghost_negatives(False)
    # Compare cached and direct painting at the exact same final viewport.
    cached = frame()
    for item in canvas.display_items.values():
        item.setCacheMode(QGraphicsItem.CacheMode.NoCache)
    report["cache_matches_direct"] = cached == frame()
    for item in canvas.display_items.values():
        item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
    frame()
    if args.edits:
        from decimal import Decimal

        from gerber_editor.core.primitives import Line
        from gerber_editor.geometry.rigid import RigidTransform
        from gerber_editor.tools.shapes import layer_quantum

        index = next(
            index
            for index, obj in enumerate(layer.objects)
            if isinstance(obj.geometry, Line)
            and obj.bounds.right - obj.bounds.left < 5
            and obj.bounds.top - obj.bounds.bottom < 5
        )
        original = layer.objects[index]
        moved = RigidTransform(dx=Decimal(1), dy=Decimal("0.5")).object(
            original, layer_quantum(layer)
        )

        def edit(value):
            layer.objects[index] = moved if value else original
            canvas.rebuild([layer])

        report["single_object_edit"] = sequence(edit, (True, False, True))
        frame().save(str(args.output / "edited.png"))
        compositions = getattr(canvas.renderer, "_compositions", {})
        if layer.id in compositions:
            report["edited_tiles"] = len(compositions[layer.id].changed_keys)
            report["total_tiles"] = len(compositions[layer.id].tiles)
        print(
            json.dumps({"stage": "edited", "median_s": report["single_object_edit"]["median_s"]}),
            flush=True,
        )
    report["memory_final_mib"] = memory_mib()
    report["source_unchanged"] = source == args.file.read_bytes()
    assert report["source_unchanged"]
    report["mixed_cycle_s"] = (
        report["opening_s"]
        + 20 * report["pan"]["median_s"]
        + 10 * report["zoom"]["median_s"]
        + 5 * report["color"]["median_s"]
    )
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    canvas.close()


if __name__ == "__main__":
    main()
