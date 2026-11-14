"""Exact aperture-macro primitives, independent of the parser and renderer."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MacroPrimitive:
    code: int
    values: tuple[Decimal, ...]

    def length_indexes(self) -> range | tuple[int, ...]:
        if self.code == 1:
            return (1, 2, 3)
        if self.code == 4:
            return range(2, len(self.values) - 1)
        if self.code == 5:
            return (2, 3, 4)
        if self.code == 20:
            return range(1, 6)
        return range(1, 5)  # Center/lower-left line: 21 / 22.

    def in_units(self, scale: Decimal) -> tuple[Decimal, ...]:
        lengths = self.length_indexes()
        return tuple(v / scale if i in lengths else v for i, v in enumerate(self.values))
