"""Parameter edits create independent apertures and never change neighbouring objects."""

from dataclasses import replace
from decimal import Decimal as D
from math import atan2, cos, degrees, radians, sin

from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.geometry.rigid import remap_apertures
from gerber_editor.tools.shapes import layer_quantum, point_on_grid


def object_values(obj):
    """Read bulk-edit defaults without constructing a dialog per object."""
    g = obj.geometry
    values = {}
    if isinstance(g, Line):
        dx, dy = g.end.x - g.start.x, g.end.y - g.start.y
        values = dict(
            sx=g.start.x,
            sy=g.start.y,
            ex=g.end.x,
            ey=g.end.y,
            length=(dx * dx + dy * dy).sqrt(),
            direction=degrees(atan2(float(dy), float(dx))),
            by_length=False,
        )
    elif isinstance(g, Arc):
        angle, sweep = g.angles()
        values = dict(
            cx=g.center.x,
            cy=g.center.y,
            radius=g.radius,
            start_angle=degrees(angle),
            sweep=abs(degrees(sweep)),
            clockwise=g.clockwise,
        )
    elif isinstance(g, Flash):
        values = dict(x=g.position.x, y=g.position.y)
    elif isinstance(g, Region):
        values = dict(
            offset_x=D(0),
            offset_y=D(0),
            rotation=0,
            center_x=D(str((obj.bounds.left + obj.bounds.right) / 2)),
            center_y=D(str((obj.bounds.bottom + obj.bounds.top) / 2)),
        )
    ap = obj.aperture
    if ap and not ap.macro and (isinstance(g, Flash) or ap.shape == "C"):
        values["width"] = ap.parameters[0]
        if ap.shape in ("R", "O"):
            values["height"] = ap.parameters[1]
    return values


def edit_object(layer, obj, values):
    quantum = layer_quantum(layer)
    g = obj.geometry

    def point(x, y):
        return point_on_grid(x, y, quantum)

    if isinstance(g, Line):
        start = point(values["sx"], values["sy"])
        if values.get("by_length"):
            length, angle = values["length"], radians(values["direction"])
            end = point(
                start.x + length * D(str(cos(angle))), start.y + length * D(str(sin(angle)))
            )
        else:
            end = point(values["ex"], values["ey"])
        if start == end:
            raise ValueError("A linha deve ter comprimento positivo.")
        geometry = Line(start, end)
    elif isinstance(g, Arc):
        center = point(values["cx"], values["cy"])
        radius = values["radius"]
        if radius <= 0:
            raise ValueError("O raio deve ser positivo.")
        angle = radians(values["start_angle"])
        sweep = values["sweep"]
        if not 0 < sweep <= 360:
            raise ValueError("O ângulo deve estar entre 0 e 360 graus.")

        def around(a):
            return point(center.x + radius * D(str(cos(a))), center.y + radius * D(str(sin(a))))

        start = around(angle)
        end = (
            start
            if sweep == 360
            else around(angle + radians(sweep) * (-1 if values["clockwise"] else 1))
        )
        geometry = Arc(start, end, center, values["clockwise"])
    elif isinstance(g, Flash):
        geometry = Flash(point(values["x"], values["y"]))
    elif isinstance(g, Region):
        from gerber_editor.geometry.rigid import RigidTransform

        transform = RigidTransform(
            angle=values["rotation"],
            center=Point(values["center_x"], values["center_y"]),
            dx=values["offset_x"],
            dy=values["offset_y"],
        )
        geometry = transform.geometry(g, quantum)
    else:
        raise ValueError("Selecione uma linha, arco, círculo, flash ou texto editável.")
    if "_changed" in values and not (set(values["_changed"]) - {"width", "height"}):
        geometry = g
    ap = obj.aperture
    if "width" in values and ap:
        if values["width"] <= 0:
            raise ValueError("A espessura deve ser positiva.")
        parameters = list(ap.parameters)
        parameters[0] = values["width"]
        if "height" in values:
            parameters[1] = values["height"]
        ap = replace(ap, parameters=tuple(parameters))
    changed = replace(obj, geometry=geometry, aperture=ap)
    return remap_apertures(layer, [changed])[0]
