"""Compare paired benchmark reports, their rendered images and source hashes."""

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("optimized", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-channel-error", type=int, default=0)
    parser.add_argument("--max-mean-error", type=float, default=0)
    args = parser.parse_args()
    from PySide6.QtGui import QImage

    before = json.loads((args.baseline / "report.json").read_text(encoding="utf-8"))
    after = json.loads((args.optimized / "report.json").read_text(encoding="utf-8"))
    assert before["source_sha256"] == after["source_sha256"]
    assert before["source_unchanged"] and after["source_unchanged"]
    result = {"file": after["file"], "source_sha256": after["source_sha256"], "timings": {}}
    pairs = {
        name: (before[name], after[name]) for name in ("opening_s", "scene_s", "mixed_cycle_s")
    }
    pairs.update(
        {
            name: (before[name]["median_s"], after[name]["median_s"])
            for name in ("pan", "zoom", "color")
        }
    )
    for name in ("single_object_edit", "pan_with_cursor_on_board"):
        if name in before and name in after:
            pairs[name] = before[name]["median_s"], after[name]["median_s"]
    common_opening = max(before["opening_s"], after["opening_s"])
    pairs["mixed_cycle_common_opening_s"] = tuple(
        report["mixed_cycle_s"] - report["opening_s"] + common_opening for report in (before, after)
    )
    result["scenario"] = {
        "description": "One opening + 20 pan frames + 10 zoom frames + 5 color changes",
        "is_end_to_end_interactive_measurement": False,
        "common_opening_s": common_opening,
        "note": "Common opening isolates navigation gains from opening-time changes and variation",
    }
    for name, (old, new) in pairs.items():
        result["timings"][name] = {
            "before_s": old,
            "after_s": new,
            "factor": old / new,
            "faster_percent": 100 * (old / new - 1),
            "time_reduction_percent": 100 * (1 - new / old),
        }
    result["images_identical"] = {}
    result["image_errors"] = {}
    image_names = ["initial", "color", "selected", "ghosts"]
    if (args.baseline / "edited.png").exists() and (args.optimized / "edited.png").exists():
        image_names.append("edited")
    for name in image_names:
        original = QImage(str(args.baseline / f"{name}.png"))
        optimized = QImage(str(args.optimized / f"{name}.png"))
        assert not original.isNull() and not optimized.isNull()
        result["images_identical"][name] = original == optimized
        a = np.frombuffer(original.constBits(), dtype=np.uint8).astype(int)
        b = np.frombuffer(optimized.constBits(), dtype=np.uint8).astype(int)
        error = np.abs(a - b)
        result["image_errors"][name] = {
            "max_channel": int(error.max()),
            "mean_channel": float(error.mean()),
        }
    if before["memory_scene_mib"] and after["memory_scene_mib"]:
        old = before["memory_scene_mib"]["working_set"]
        new = after["memory_scene_mib"]["working_set"]
        result["resident_scene_memory"] = {
            "before_mib": old,
            "after_mib": new,
            "reduction_percent": 100 * (1 - new / old),
            "note": "Process snapshots; affected by allocator and OS, not exact ownership accounting",
        }
    result["cache_matches_direct"] = after["cache_matches_direct"]
    assert all(
        error["max_channel"] <= args.max_channel_error
        and error["mean_channel"] <= args.max_mean_error
        for error in result["image_errors"].values()
    ), result["image_errors"]
    assert result["cache_matches_direct"]
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
