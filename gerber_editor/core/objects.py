"""Fabrication objects and apertures, independent of the UI and source syntax."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from functools import cached_property
from uuid import uuid4

from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.core.primitives import Bounds, Flash, Geometry, Region, curve_bounds
from gerber_editor.core.text_entity import TextEntity

Attributes = tuple[tuple[str, tuple[str, ...]], ...]


class Polarity(str, Enum):
    DARK = "D"
    CLEAR = "C"


@dataclass(frozen=True)
class Aperture:
    code: int
    shape: str
    parameters: tuple[Decimal, ...]
    attributes: Attributes = ()
    macro: tuple[MacroPrimitive, ...] = ()

    @property
    def width(self) -> Decimal:
        if self.macro:
            bounds = self.local_bounds
            return Decimal(str(bounds.right - bounds.left))
        return self.parameters[0]

    @property
    def height(self) -> Decimal:
        if self.macro:
            bounds = self.local_bounds
            return Decimal(str(bounds.top - bounds.bottom))
        return self.parameters[1] if self.shape in ("R", "O") else self.width

    @cached_property
    def local_bounds(self) -> Bounds:
        if self.macro:
            from gerber_editor.core.macro_bounds import macro_bounds

            return macro_bounds(self.macro)
        return Bounds(
            -float(self.width) / 2,
            -float(self.height) / 2,
            float(self.width) / 2,
            float(self.height) / 2,
        )

    def signature(self) -> tuple:
        return self.shape, self.macro or self.parameters, self.attributes


@dataclass(frozen=True)
class GerberObject:
    geometry: Geometry
    aperture: Aperture | None
    polarity: Polarity = Polarity.DARK
    attributes: Attributes = ()
    id: str = field(default_factory=lambda: uuid4().hex)
    source_tokens: tuple[int, ...] = ()
    origin: str = "created"
    visible: bool = True
    text_entity: TextEntity | None = None
    # Session selection metadata: never changes fabrication equality/export.
    group_id: str | None = field(default=None, compare=False)

    @property
    def kind(self) -> str:
        return type(self.geometry).__name__

    @cached_property
    def bounds(self) -> Bounds:
        g = self.geometry
        if isinstance(g, Flash):
            x, y = float(g.position.x), float(g.position.y)
            b = Bounds(x, y, x, y)
            if self.aperture is not None:
                a = self.aperture.local_bounds
                return Bounds(x + a.left, y + a.bottom, x + a.right, y + a.top)
        elif isinstance(g, Region):
            curves = [curve for contour in g.contours for curve in contour]
            b = curve_bounds(curves[0])
            for curve in curves[1:]:
                b = b.union(curve_bounds(curve))
            return b
        else:
            b = curve_bounds(g)
        if self.aperture is not None:
            b = b.expanded(float(self.aperture.width) / 2, float(self.aperture.height) / 2)
        return b
