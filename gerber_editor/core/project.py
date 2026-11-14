"""Project and board containers. Persistence is planned for phase 4."""

from dataclasses import dataclass, field

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.stackup import BoardStackup


@dataclass
class Board:
    layers: list[GerberLayer] = field(default_factory=list)
    stackup: BoardStackup = field(default_factory=BoardStackup)
    outline_layer_id: str | None = None


@dataclass
class Project:
    name: str = "Sem título"
    board: Board = field(default_factory=Board)
