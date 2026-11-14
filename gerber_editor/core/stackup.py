"""Manufacturing data shared with a future 3D backend; no mesh dependency."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class BoardMaterial:
    name: str = "FR4"
    color: str = "#397b54"
    relative_permittivity: Decimal = Decimal("4.5")


@dataclass(frozen=True)
class LayerStack:
    layer_id: str
    role: str
    thickness_mm: Decimal
    z_mm: Decimal


@dataclass
class BoardStackup:
    thickness_mm: Decimal = Decimal("1.6")
    substrate: BoardMaterial = field(default_factory=BoardMaterial)
    layers: list[LayerStack] = field(default_factory=list)
