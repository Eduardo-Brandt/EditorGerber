"""Physical Gerber drill/rout data, distinct from annotated drill maps."""

from shapely.geometry import GeometryCollection
from shapely.ops import unary_union

from gerber_editor.core.layer import canonical_function
from gerber_editor.geometry.boolean import compose_layer, object_geometry

DRILL_ROLES = frozenset({"Drill", "Drill.PTH", "Drill.NPTH", "Drill.Blind", "Drill.Buried"})


def drill_geometry(layers, cache=None):
    """Through cuts remain physical even when their 2D layer is hidden."""
    cache = cache or {}
    shapes = []
    for layer in layers:
        role = canonical_function(layer.function)
        if role not in DRILL_ROLES:
            continue
        function = dict(layer.attributes).get(".FileFunction", ())
        if role in ("Drill.Blind", "Drill.Buried") or any(
            value.lower() in ("blind", "buried") for value in function
        ):
            raise ValueError(
                "Furos cegos/enterrados exigem stackup; somente furação passante é suportada."
            )
        geometries = {
            obj.id: cache[obj.id][1]
            if obj.id in cache and cache[obj.id][0] == obj
            else object_geometry(obj)
            for obj in layer.objects
        }
        shapes.append(compose_layer(layer.objects, geometries))
    return unary_union(shapes) if shapes else GeometryCollection()
