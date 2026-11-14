"""Interpret Gerber cut-ins without repairing arbitrary intersecting contours."""

from collections import Counter

from shapely.geometry import LineString, MultiPoint, Polygon

from gerber_editor.core.primitives import Line
from gerber_editor.gerber.errors import GerberError


def cutin_polygon(contour, sample):
    """Ucamco 4.10.3: paired, opposite, axis-aligned lines connect hole rings.

    Decimal endpoints identify bridges exactly. All remaining rings and bridge
    interiors must pass validation; a bow-tie is never silently made valid.
    Original curves are retained in the document and in both export modes.
    """
    error = "Região inválida/auto-intersectante; nenhum reparo aplicado."
    edges = Counter((c.start, c.end) for c in contour if isinstance(c, Line) and c.start != c.end)
    bridges = set()
    directions = set()
    for (start, end), count in edges.items():
        if (end, start) not in edges:
            continue
        if count != 1 or edges[end, start] != 1:
            raise GerberError(error)
        if start.x == end.x:
            directions.add("vertical")
        elif start.y == end.y:
            directions.add("horizontal")
        else:
            raise GerberError(error)
        bridges.add((start, end))
    if not bridges or len(directions) != 1:
        raise GerberError(error)
    outgoing, incoming = {}, set()
    for curve in contour:
        if isinstance(curve, Line) and (
            curve.start == curve.end or (curve.start, curve.end) in bridges
        ):
            continue
        if curve.start in outgoing or curve.end in incoming:
            raise GerberError(error)
        outgoing[curve.start] = curve
        incoming.add(curve.end)
    if set(outgoing) != incoming:
        raise GerberError(error)
    rings = []
    while outgoing:
        start = next(iter(outgoing))
        current, points = start, []
        while current in outgoing:
            curve = outgoing.pop(current)
            part = sample(curve)
            points.extend(part if not points else part[1:])
            current = curve.end
        if current != start or len(points) < 4:
            raise GerberError(error)
        ring = Polygon(points)
        if not ring.is_valid or ring.area <= 0:
            raise GerberError(error)
        rings.append(ring)
    rings.sort(key=lambda ring: ring.area, reverse=True)
    if len(rings) < 2:
        raise GerberError(error)
    polygon = Polygon(rings[0].exterior, [ring.exterior for ring in rings[1:]])
    if not polygon.is_valid or polygon.area <= 0:
        raise GerberError(error)
    remaining = set(bridges)
    lines = []
    while remaining:
        start, end = remaining.pop()
        remaining.remove((end, start))
        endpoints = [(float(p.x), float(p.y)) for p in (start, end)]
        bridge = LineString(endpoints)
        if not polygon.covers(bridge) or not bridge.intersection(polygon.boundary).equals(
            MultiPoint(endpoints)
        ):
            raise GerberError(error)
        if any(bridge.intersection(other).length > 0 for other in lines):
            raise GerberError(error)
        lines.append(bridge)
    return polygon
