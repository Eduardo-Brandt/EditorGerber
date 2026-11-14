"""Optional Gerbonara comparison of the current source and the 0.4 exports."""

import argparse
import json
import re
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "output" / "qa_backend"))
    from gerbonara import GerberFile
    from gerbonara.utils import MM

    def parse(path):
        tokens = re.split(r"([*%])", path.read_text(encoding="latin-1"))
        for index, token in enumerate(tokens):
            if not token.lstrip().startswith("G04"):
                tokens[index] = re.sub(r"G([123])(?=[A-Z]|$)", r"G0\1", token)
        return GerberFile.from_string("".join(tokens))

    original = parse(args.source)
    report = {}
    for mode in ("preservation", "normalized"):
        exported = parse(root / "output" / "v04" / f"srlc_v04_{mode}.gbr")
        assert len(exported.objects) == len(original.objects) + 3
        for a, b in zip(original.objects, exported.objects[: len(original.objects)], strict=True):
            assert type(a) is type(b) and a.polarity_dark == b.polarity_dark
            assert list(a.to_primitives(MM)) == list(b.to_primitives(MM))
        report[mode] = {
            "original_objects": len(original.objects),
            "exported_objects": len(exported.objects),
            "original_geometry_and_order": "passed",
        }
    (root / "output" / "v04" / "independent_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
