"""Versioned JSON clipboard, with Decimal coordinates and no executable payloads."""

import json
from dataclasses import asdict
from decimal import Decimal as D

from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.core.text_entity import TextEntity

MIME_TYPE = "application/x-editor-gerber-objects+json"


def encode(objects, anchor):
    def geometry(g):
        if isinstance(g, Region):
            return {
                "kind": "Region",
                "contours": [[geometry(c) for c in contour] for contour in g.contours],
            }
        return {"kind": type(g).__name__, **asdict(g)}

    return json.dumps(
        {
            "schema": 1,
            "anchor": asdict(anchor),
            "objects": [
                {
                    "geometry": geometry(obj.geometry),
                    "aperture": asdict(obj.aperture) if obj.aperture else None,
                    "polarity": obj.polarity.value,
                    "attributes": obj.attributes,
                    "text_entity": asdict(obj.text_entity) if obj.text_entity else None,
                    **({"group_id": obj.group_id} if obj.group_id else {}),
                    **({"visible": False} if not obj.visible else {}),
                }
                for obj in objects
            ],
        },
        default=str,
    ).encode("utf-8")


def decode(data):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("Clipboard exceeds 64 MB")
    payload = json.loads(bytes(data))
    if payload["schema"] != 1 or not 0 < len(payload["objects"]) <= 200000:
        raise ValueError("Invalid clipboard format")

    def point(value):
        p = Point(D(value["x"]), D(value["y"]))
        if not p.x.is_finite() or not p.y.is_finite():
            raise ValueError("Invalid clipboard coordinate")
        return p

    def geometry(value):
        kind = value["kind"]
        if kind == "Region":
            return Region(
                tuple(tuple(geometry(c) for c in contour) for contour in value["contours"])
            )
        if kind == "Flash":
            return Flash(point(value["position"]))
        if kind == "Arc":
            return Arc(
                point(value["start"]),
                point(value["end"]),
                point(value["center"]),
                bool(value["clockwise"]),
            )
        if kind == "Line":
            return Line(point(value["start"]), point(value["end"]))
        raise ValueError("Invalid clipboard geometry")

    def attrs(value):
        return tuple((key, tuple(values)) for key, values in value)

    result = []
    for item in payload["objects"]:
        group_id = item.get("group_id")
        visible = item.get("visible", True)
        if not isinstance(visible, bool):
            raise ValueError("Invalid clipboard visibility")
        if group_id is not None and (not isinstance(group_id, str) or not 0 < len(group_id) <= 128):
            raise ValueError("Invalid clipboard group")
        a = item["aperture"]
        ap = (
            Aperture(
                int(a["code"]),
                a["shape"],
                tuple(D(v) for v in a["parameters"]),
                attrs(a["attributes"]),
                tuple(
                    MacroPrimitive(p["code"], tuple(D(v) for v in p["values"])) for p in a["macro"]
                ),
            )
            if a
            else None
        )
        t = item.get("text_entity")
        if t:
            t = {
                **t,
                "position": point(t["position"]),
                "height": D(t["height"]),
                "stroke": D(t["stroke"]),
            }
        result.append(
            GerberObject(
                geometry(item["geometry"]),
                ap,
                Polarity(item["polarity"]),
                attrs(item["attributes"]),
                text_entity=TextEntity(**t) if t else None,
                group_id=group_id,
                visible=visible,
            )
        )
    return result, point(payload["anchor"])
