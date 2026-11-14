"""Prepare Gerber geometry in a worker, keeping the UI responsive on large files."""

import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QObject, QRunnable, Signal

from gerber_editor.core.layer import GerberLayer
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.graphics.renderer import LayerRenderer
from gerber_editor.validation.checks import validate_layer


@dataclass
class ImportResult:
    job_id: int
    path: Path
    layer: GerberLayer | None = None
    renderer: LayerRenderer | None = None
    error: str = ""
    skipped: str = ""


class ImportSignals(QObject):
    finished = Signal(object)


class ImportJob(QRunnable):
    def __init__(self, job_id: int, path: Path):
        super().__init__()
        self.job_id, self.path = job_id, path
        self.signals = ImportSignals()

    def run(self):
        result = ImportResult(self.job_id, self.path)
        started = perf_counter()
        log = logging.getLogger(__name__)
        log.info("Preparing Gerber: %s", self.path)
        try:
            if is_auxiliary_file(self.path):
                result.skipped = "Arquivo auxiliar do KiCad; não é Gerber."
                self.signals.finished.emit(result)
                return
            result.layer = GerberParser().parse_file(self.path)
            validate_layer(result.layer)
            result.renderer = LayerRenderer()
            result.renderer.paths(result.layer)
            log.info(
                "Prepared %s: %s objects in %.3f s",
                self.path.name,
                len(result.layer.objects),
                perf_counter() - started,
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("Import failed: %s", self.path)
            result.layer, result.renderer, result.error = None, None, str(exc)
        self.signals.finished.emit(result)


def looks_like_gerber(path: Path) -> bool:
    """Inspect content, not extension. Auxiliary KiCad cache files are excluded."""
    with path.open("rb") as stream:
        header = stream.read(8192)
    from gerber_editor.gerber.excellon import is_excellon

    return (b"%FS" in header and b"%MO" in header) or is_excellon(header)


def is_auxiliary_file(path: Path) -> bool:
    return path.name.lower() in {"fp-info-cache", "fp-info-chache"} and not looks_like_gerber(path)
