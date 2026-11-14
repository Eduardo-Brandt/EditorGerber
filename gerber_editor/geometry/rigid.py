"""Rigid transforms of curves and aperture images, preserving local clear areas."""

from dataclasses import replace
from decimal import Decimal as D
from math import atan2, cos, degrees, radians, sin
from uuid import uuid4

from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.core.objects import Aperture
from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.tools.shapes import point_on_grid


def rotation_values(angle):
    if float(angle) % 90 == 0:
        return ((D(1), D(0)), (D(0), D(1)), (D(-1), D(0)), (D(0), D(-1)))[
            int(float(angle) / 90) % 4
        ]
    angle = radians(float(angle))
    return D(str(cos(angle))), D(str(sin(angle)))


class RigidTransform:
    def __init__(self, angle=0, center=None, dx=D(0), dy=D(0), mirror_x=False, mirror_y=False):
        center = center or Point.of(0, 0)
        c, s = rotation_values(angle)
        sx, sy = D(-1 if mirror_x else 1), D(-1 if mirror_y else 1)
        self.a, self.b, self.c, self.d = c * sx, -s * sy, s * sx, c * sy
        self.tx = center.x + dx - self.a * center.x - self.b * center.y
        self.ty = center.y + dy - self.c * center.x - self.d * center.y
        self.reflected = self.a * self.d - self.b * self.c < 0

    def point(self, p, quantum=None, local=False):
        x = self.a * p.x + self.b * p.y + (D(0) if local else self.tx)
        y = self.c * p.x + self.d * p.y + (D(0) if local else self.ty)
        return point_on_grid(x, y, quantum) if quantum else Point(x, y)

    def direction(self, angle):
        c, s = rotation_values(angle)
        return degrees(atan2(float(self.c * c + self.d * s), float(self.a * c + self.b * s)))

    def geometry(self, geometry, quantum):
        if isinstance(geometry, Flash):
            return Flash(self.point(geometry.position, quantum))
        if isinstance(geometry, Region):
            return Region(
                tuple(
                    tuple(self.geometry(curve, quantum) for curve in contour)
                    for contour in geometry.contours
                )
            )
        if isinstance(geometry, Arc):
            return Arc(
                self.point(geometry.start, quantum),
                self.point(geometry.end, quantum),
                self.point(geometry.center, quantum),
                geometry.clockwise ^ self.reflected,
            )
        return Line(self.point(geometry.start, quantum), self.point(geometry.end, quantum))

    def aperture(self, aperture):
        if aperture is None or (self.a, self.b, self.c, self.d) == (1, 0, 0, 1):
            return aperture
        if aperture.shape == "C":
            return aperture
        if aperture.shape == "P":
            p = aperture.parameters
            return replace(
                aperture,
                parameters=(p[0], p[1], D(str(self.direction(p[2] if len(p) > 2 else 0))), *p[3:]),
            )
        if aperture.shape in ("R", "O") and (self.a == 0 or self.b == 0):
            parameters = aperture.parameters
            if self.a == 0:
                parameters = (parameters[1], parameters[0], *parameters[2:])
            return replace(aperture, parameters=parameters)
        if aperture.macro:
            primitives = aperture.macro
        else:
            p = aperture.parameters
            if aperture.shape == "R":
                primitives = (MacroPrimitive(21, (D(1), p[0], p[1], D(0), D(0), D(0))),)
                hole = p[2] if len(p) > 2 else D(0)
            elif aperture.shape == "O":
                w, h = p[:2]
                r = min(w, h)
                x, y = max(D(0), w - h) / 2, max(D(0), h - w) / 2
                primitives = (
                    MacroPrimitive(20, (D(1), r, -x, -y, x, y, D(0))),
                    MacroPrimitive(1, (D(1), r, -x, -y, D(0))),
                    MacroPrimitive(1, (D(1), r, x, y, D(0))),
                )
                hole = p[2] if len(p) > 2 else D(0)
            else:
                primitives = (
                    MacroPrimitive(5, (D(1), p[1], D(0), D(0), p[0], p[2] if len(p) > 2 else D(0))),
                )
                hole = p[3] if len(p) > 3 else D(0)
            if hole:
                primitives += (MacroPrimitive(1, (D(0), hole, D(0), D(0), D(0))),)
        transformed = []
        for primitive in primitives:
            p, code = primitive.values, primitive.code
            angle = p[-1] if (code != 1 or len(p) > 4) else D(0)
            rot = RigidTransform(angle=angle)

            def xy(x, y, rot=rot):
                return self.point(rot.point(Point(x, y), local=True), local=True)

            if code == 1:
                center = xy(p[2], p[3])
                values = (p[0], p[1], center.x, center.y, D(0))
            elif code == 4:
                points = [xy(p[i], p[i + 1]) for i in range(2, len(p) - 1, 2)]
                values = (p[0], p[1], *(v for point in points for v in (point.x, point.y)), D(0))
            elif code == 20:
                start, end = xy(p[2], p[3]), xy(p[4], p[5])
                values = (p[0], p[1], start.x, start.y, end.x, end.y, D(0))
            else:
                # Rotation in AM is around the macro origin. Undo that rotation
                # for the transformed center before expressing the new primitive.
                center = (
                    xy(p[2], p[3])
                    if code == 5
                    else xy(
                        p[3] + (p[1] / 2 if code == 22 else 0),
                        p[4] + (p[2] / 2 if code == 22 else 0),
                    )
                )
                new_angle = D(str(self.direction(angle)))
                unrotated = RigidTransform(angle=-new_angle).point(center, local=True)
                if code == 5:
                    values = (p[0], p[1], unrotated.x, unrotated.y, p[4], new_angle)
                else:
                    code = 21
                    values = (p[0], p[1], p[2], unrotated.x, unrotated.y, new_angle)
            transformed.append(MacroPrimitive(code, tuple(values)))
        return Aperture(aperture.code, "MACRO", (), aperture.attributes, tuple(transformed))

    def object(self, obj, quantum, *, clone=False, group_ids=None):
        group_ids = group_ids if group_ids is not None else {}
        selection_group = obj.group_id
        if clone and selection_group:
            selection_group = group_ids.setdefault(("objects", selection_group), uuid4().hex)
        geometry = self.geometry(obj.geometry, quantum)
        aperture = self.aperture(obj.aperture)
        if isinstance(obj.geometry, Line) and obj.aperture.shape == "R" and aperture.macro:
            # The sweep of an axis-aligned rectangle over a line is the convex
            # hull of its two endpoint rectangles. Emit that exact outline,
            # rather than a draw with a rotated macro aperture.
            half_w, half_h = (v / 2 for v in obj.aperture.parameters[:2])
            points = sorted(
                {
                    (p.x + x, p.y + y)
                    for p in (obj.geometry.start, obj.geometry.end)
                    for x in (-half_w, half_w)
                    for y in (-half_h, half_h)
                }
            )

            def cross(o, a, b):
                return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

            halves = []
            for values in (points, list(reversed(points))):
                hull = []
                for point in values:
                    while len(hull) >= 2 and cross(hull[-2], hull[-1], point) <= 0:
                        hull.pop()
                    hull.append(point)
                halves.extend(hull[:-1])
            outline = [self.point(Point(x, y), quantum) for x, y in halves]
            geometry = Region(
                (
                    tuple(
                        Line(a, b) for a, b in zip(outline, outline[1:] + outline[:1], strict=True)
                    ),
                )
            )
            aperture = None
        text = obj.text_entity
        if text:
            group_id = text.group_id
            if clone:
                group_id = group_ids.setdefault(group_id, uuid4().hex)
            text = replace(
                text,
                position=self.point(text.position, quantum),
                rotation=self.direction(text.rotation),
                mirror_y=text.mirror_y ^ self.reflected,
                group_id=group_id,
            )
        return replace(
            obj,
            geometry=geometry,
            aperture=aperture,
            text_entity=text,
            group_id=selection_group,
            id=uuid4().hex if clone else obj.id,
            source_tokens=() if clone else obj.source_tokens,
            origin="created" if clone else obj.origin,
        )


def remap_apertures(layer, objects):
    """Allocate independent D codes, without modifying the destination layer."""
    existing = {ap.signature(): ap for ap in layer.apertures.values()}
    existing.update(
        {obj.aperture.signature(): obj.aperture for obj in layer.objects if obj.aperture}
    )
    code = max([9, *layer.apertures, *(obj.aperture.code for obj in layer.objects if obj.aperture)])
    output = []
    for obj in objects:
        ap = obj.aperture
        if ap:
            if ap.signature() not in existing:
                code += 1
                existing[ap.signature()] = replace(ap, code=code)
            ap = existing[ap.signature()]
        output.append(replace(obj, aperture=ap))
    return output
