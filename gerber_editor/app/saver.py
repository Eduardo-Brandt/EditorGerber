"""Validated atomic writing on a worker; document state stays on the GUI thread."""

from copy import copy
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from gerber_editor.core.layer import GerberLayer
from gerber_editor.gerber.writer import GerberWriter, SaveMode
from gerber_editor.validation.checks import ValidationReport


@dataclass(frozen=True)
class SaveRequest:
    layer: GerberLayer
    target: Path
    mode: SaveMode
    overwrite: bool


@dataclass
class SaveResult:
    request: SaveRequest
    report: ValidationReport | None = None
    error: str = ""


class SaveSignals(QObject):
    finished = Signal(object)


class SaveJob(QRunnable):
    def __init__(self, request):
        super().__init__()
        self.request = request
        self.signals = SaveSignals()
        # Objects and source records are immutable while the input guard is on.
        self.snapshot = copy(request.layer)
        self.snapshot.objects = list(request.layer.objects)
        self.snapshot.apertures = dict(request.layer.apertures)

    def run(self):
        request = self.request
        result = SaveResult(request)
        try:
            result.report = GerberWriter().save(
                self.snapshot, request.target, request.mode, overwrite=request.overwrite
            )
        except Exception as exc:
            result.error = str(exc)
        self.signals.finished.emit(result)
