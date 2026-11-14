"""Analytic conservative macro bounds; rotations are display-only floats."""

import math

from gerber_editor.core.primitives import Bounds


def macro_bounds(primitives) -> Bounds:
    bounds = None
    for primitive in primitives:
        p = [float(value) for value in primitive.values]
        if primitive.code == 1:
            cx, cy, radius = p[2], p[3], p[1] / 2
            points = [(cx, cy)]
            expand = radius
        elif primitive.code == 4:
            points = list(zip(p[2:-1:2], p[3:-1:2], strict=True))
            expand = 0
        elif primitive.code == 5:
            points = [(p[2], p[3])]
            expand = p[4] / 2
        elif primitive.code == 20:
            # A square cap bound also contains any orientation of the butt ends.
            points = [(p[2], p[3]), (p[4], p[5])]
            expand = p[1] / 2
        else:
            cx, cy = p[3], p[4]
            if primitive.code == 22:
                cx, cy = cx + p[1] / 2, cy + p[2] / 2
            points = [(cx + dx * p[1] / 2, cy + dy * p[2] / 2) for dx in (-1, 1) for dy in (-1, 1)]
            expand = 0
        angle = math.radians(p[-1])
        c, s = math.cos(angle), math.sin(angle)
        points = [(x * c - y * s, x * s + y * c) for x, y in points]
        b = Bounds(
            min(x for x, _ in points),
            min(y for _, y in points),
            max(x for x, _ in points),
            max(y for _, y in points),
        ).expanded(expand)
        bounds = b if bounds is None else bounds.union(b)
    return bounds
