"""Exact logical geometry. Floats are used only by display helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

D = Decimal


@dataclass(frozen=True)
class Point:
    x: Decimal
    y: Decimal

    @classmethod
    def of(cls, x: str | int, y: str | int) -> Point:
        return cls(D(x), D(y))


@dataclass(frozen=True)
class Line:
    start: Point
    end: Point


@dataclass(frozen=True)
class Arc:
    start: Point
    end: Point
    center: Point
    clockwise: bool

    @property
    def radius(self) -> Decimal:
        return ((self.start.x - self.center.x) ** 2 + (self.start.y - self.center.y) ** 2).sqrt()

    def angles(self) -> tuple[float, float]:
        a = math.atan2(float(self.start.y - self.center.y), float(self.start.x - self.center.x))
        b = math.atan2(float(self.end.y - self.center.y), float(self.end.x - self.center.x))
        sweep = (a - b) % math.tau if self.clockwise else (b - a) % math.tau
        if self.start == self.end:
            sweep = math.tau
        return a, -sweep if self.clockwise else sweep


@dataclass(frozen=True)
class Flash:
    position: Point


@dataclass(frozen=True)
class Region:
    contours: tuple[tuple[Line | Arc, ...], ...]


Geometry = Line | Arc | Flash | Region


@dataclass(frozen=True)
class Bounds:
    left: float
    bottom: float
    right: float
    top: float

    def union(self, other: Bounds) -> Bounds:
        return Bounds(
            min(self.left, other.left),
            min(self.bottom, other.bottom),
            max(self.right, other.right),
            max(self.top, other.top),
        )

    def expanded(self, x: float, y: float | None = None) -> Bounds:
        y = x if y is None else y
        return Bounds(self.left - x, self.bottom - y, self.right + x, self.top + y)


def curve_bounds(curve: Line | Arc) -> Bounds:
    points = [
        (float(curve.start.x), float(curve.start.y)),
        (float(curve.end.x), float(curve.end.y)),
    ]
    if isinstance(curve, Arc):
        start, sweep = curve.angles()
        radius = float(curve.radius)
        for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            distance = ((angle - start) if sweep > 0 else (start - angle)) % math.tau
            if distance <= abs(sweep) + 1e-12:
                points.append(
                    (
                        float(curve.center.x) + radius * math.cos(angle),
                        float(curve.center.y) + radius * math.sin(angle),
                    )
                )
    return Bounds(
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )
