"""Frozen entry point; package verification exits without opening error dialogs."""

import multiprocessing
import sys


def entry():
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-package":
        from scripts.verify_packaged import main

        return main(sys.argv[2:])
    from gerber_editor.main import main

    return main()


if __name__ == "__main__":
    raise SystemExit(entry())
