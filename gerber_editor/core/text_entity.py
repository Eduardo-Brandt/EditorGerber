"""Session-only editable text. Gerber export contains its fabrication geometry."""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import uuid4

from gerber_editor.core.primitives import Point


@dataclass(frozen=True)
class TextEntity:
    text: str
    position: Point
    height: Decimal
    stroke: Decimal
    family: str
    rotation: float = 0.0
    bold: bool = False
    italic: bool = False
    mirror_y: bool = False
    group_id: str = field(default_factory=lambda: uuid4().hex)
