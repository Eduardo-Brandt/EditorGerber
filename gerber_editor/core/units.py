"""Presentation units. Logical fabrication coordinates always remain in mm."""

import math
from decimal import Decimal
from enum import Enum


class Unit(str, Enum):
    MM = "mm"
    INCH = "in"
    MIL = "mil"

    @property
    def mm(self) -> Decimal:
        return {Unit.MM: Decimal(1), Unit.INCH: Decimal("25.4"), Unit.MIL: Decimal("0.0254")}[self]

    def from_mm(self, value: Decimal | float) -> Decimal:
        return Decimal(str(value)) / self.mm

    def to_mm(self, value: Decimal | float) -> Decimal:
        return Decimal(str(value)) * self.mm


def length_text(value_mm, unit: Unit | str = Unit.MM, decimals: int = 4) -> str:
    unit = Unit(unit)
    return f"{unit.from_mm(value_mm):.{decimals}f} {unit.value}"


def vector_text(dx: float, dy: float, unit: Unit | str, polar: bool = False) -> str:
    distance = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))
    if polar:
        return f"R {length_text(distance, unit)}   θ {angle:.2f}°"
    return (
        f"ΔX {length_text(dx, unit)}   ΔY {length_text(dy, unit)}\n"
        f"D {length_text(distance, unit)}   θ {angle:.2f}°"
    )
