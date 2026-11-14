"""Routing geometry shared by the PCB model and cutout tools."""

from shapely.geometry import GeometryCollection, LineString
from shapely.ops import polygonize, unary_union

from gerber_editor.core.objects import Polarity
from gerber_editor.core.primitives import Arc, Line
from gerber_editor.geometry.boolean import curve_points, object_geometry


def closed_profiles(objects, *, include_strokes=False):
    paths = [
        LineString(curve_points(obj.geometry))
        for obj in objects
        if isinstance(obj.geometry, (Line, Arc))
        and (include_strokes or dict(obj.attributes).get("EditorGerberCut") != ("Stroke",))
    ]
    return unary_union(list(polygonize(unary_union(paths)))) if paths else GeometryCollection()


def routing_geometry(objects):
    """Closed profiles remove their interior; open strokes remove their width."""
    result = GeometryCollection()
    groups, current = [], []
    previous = None
    for obj in objects:
        if not obj.visible:
            continue
        if previous is not None and previous != obj.polarity:
            groups.append((previous, current))
            current = []
        current.append(obj)
        previous = obj.polarity
    if current:
        groups.append((previous, current))
    for polarity, group in groups:
        profiles = closed_profiles(group)
        shapes = [profiles]
        boundary = profiles.boundary.buffer(0.000002) if not profiles.is_empty else None
        for obj in group:
            if (
                isinstance(obj.geometry, (Line, Arc))
                and boundary is not None
                and dict(obj.attributes).get("EditorGerberCut") != ("Stroke",)
            ):
                if boundary.covers(LineString(curve_points(obj.geometry))):
                    continue
            shapes.append(object_geometry(obj))
        geometry = unary_union(shapes)
        result = (
            result.union(geometry) if polarity == Polarity.DARK else result.difference(geometry)
        )
    return result
