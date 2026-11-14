"""Independent Gerbonara + QtSvg checks. Optional QA backend, never a runtime dependency."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    root = workspace / "output" / "v03"
    sys.path.insert(0, str(workspace / "output" / "qa_backend"))
    import numpy as np
    from gerbonara import GerberFile
    from gerbonara.utils import MM
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    def oracle_parse(data):
        # Gerbonara does not recognize the legacy G1/G2/G3 aliases present in
        # CAMMaster files. Pad only command spelling, never numeric geometry.
        tokens = re.split(r"([*%])", data)
        for index, token in enumerate(tokens):
            if not token.lstrip().startswith("G04"):
                tokens[index] = re.sub(r"G([123])(?=[A-Z]|$)", r"G0\1", token)
        return GerberFile.from_string("".join(tokens))

    def render_isolated(gerber):
        """Use Gerbonara geometry with local aperture transparency.

        Gerbonara 1.6.3's raw to_svg() paints exposure-off macro primitives
        directly in the page background color. Gerber defines these as local
        aperture holes, so composite each independent object image in isolation.
        The independent parser, macro evaluator and SVG primitive renderer are
        used without any geometry from this editor.
        """
        bounds = gerber.bounding_box(MM)
        plane = np.full((700, 1000), 255.0)
        for obj in gerber.objects:
            isolated = copy.copy(gerber)
            positive = copy.copy(obj)
            positive.polarity_dark = True
            isolated.objects = [positive]
            svg = str(isolated.to_svg(force_bounds=bounds, fg="white", bg="black"))
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            assert renderer.isValid()
            image = QImage(1000, 700, QImage.Format.Format_RGB32)
            image.fill(0xFF000000)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            rows = np.frombuffer(image.bits(), dtype=np.uint8).reshape(700, image.bytesPerLine())
            alpha = rows[:, :4000].reshape(700, 1000, 4)[:, :, 0] / 255.0
            if obj.polarity_dark:
                plane *= 1.0 - alpha
            else:
                plane += (255.0 - plane) * alpha
        rgb = np.repeat(np.rint(plane).astype(np.uint8)[:, :, None], 3, axis=2)
        return QImage(rgb.data, 1000, 700, 3000, QImage.Format.Format_RGB888).copy()

    results = {}
    for name in (
        "font_counter",
        "font_on_background",
        "showcase_preservation",
        "showcase_normalized",
    ):
        data = (root / (name + ".gbr")).read_text(encoding="latin-1")
        gerber = oracle_parse(data)
        bitmap = render_isolated(gerber)
        bitmap.save(str(root / (name + "_independent.png")))
        if name == "font_counter":
            assert bitmap.pixelColor(500, 350).lightness() > 240, (
                "Font O counter was filled by export"
            )
        if name == "font_on_background":
            assert bitmap.pixelColor(500, 350).lightness() < 10, (
                "Font counter erased existing geometry"
            )
        results[name] = {
            "objects": len(gerber.objects),
            "bounds_mm": gerber.bounding_box(MM),
            "isolated_svg_render": "passed",
        }
    if args.real:
        original = oracle_parse(args.real.read_text(encoding="latin-1"))
        for mode in ("preservation", "normalized"):
            path = root / f"srlc_v03_{mode}.gbr"
            generated = oracle_parse(path.read_text(encoding="latin-1"))
            assert len(generated.objects) > len(original.objects)
            same = all(
                type(a) is type(b)
                and a.polarity_dark == b.polarity_dark
                and list(a.to_primitives(MM)) == list(b.to_primitives(MM))
                for a, b in zip(
                    original.objects, generated.objects[: len(original.objects)], strict=True
                )
            )
            if not same:
                for index, (a, b) in enumerate(
                    zip(original.objects, generated.objects, strict=False)
                ):
                    if list(a.to_primitives(MM)) != list(b.to_primitives(MM)):
                        raise AssertionError(
                            f"{mode}: independent geometry differs at object {index}"
                        )
                raise AssertionError(f"{mode}: independent object types or polarities differ")
            results["srlc_" + mode] = {
                "original_objects": len(original.objects),
                "exported_objects": len(generated.objects),
                "original_objects_unchanged": same,
            }
    (root / "independent_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
