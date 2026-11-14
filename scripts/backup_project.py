"""python -m scripts.backup_project [--replace] [--version X.Y.Z]."""

import argparse
from pathlib import Path

from gerber_editor.app.backup import backup_project
from gerber_editor.app.metadata import VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    print(backup_project(Path(__file__).resolve().parents[1], args.version, replace=args.replace))


if __name__ == "__main__":
    main()
