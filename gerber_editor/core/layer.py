"""Layer ownership and read-only provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from gerber_editor.core.objects import Aperture, Attributes, GerberObject
from gerber_editor.core.primitives import Bounds


@dataclass(frozen=True)
class CoordinateFormat:
    integer: int = 4
    decimal: int = 6
    suppression: str = "L"

    def decode(self, value: str) -> Decimal:
        if "." in value:
            return Decimal(value)
        sign = -1 if value.startswith("-") else 1
        digits = value.lstrip("+-")
        if not digits or len(digits) > self.integer + self.decimal:
            raise ValueError(f"Coordenada inválida: {value}")
        if self.suppression == "T":
            digits = digits.ljust(self.integer + self.decimal, "0")
        return sign * Decimal(digits).scaleb(-self.decimal)


@dataclass
class GerberSource:
    data: bytes
    tokens: list  # Token objects; kept here to avoid a model -> parser dependency.
    coordinate_format: CoordinateFormat
    unit_scale: Decimal
    original_objects: dict[str, GerberObject]
    operations: dict[int, int]
    end_token: int
    final_polarity: str = "D"


@dataclass(frozen=True)
class ExcellonSource:
    data: bytes
    original_signature: tuple


@dataclass
class GerberLayer:
    name: str
    objects: list[GerberObject] = field(default_factory=list)
    apertures: dict[int, Aperture] = field(default_factory=dict)
    attributes: Attributes = ()
    legacy_names: tuple[str, ...] = ()
    path: Path | None = None
    source: GerberSource | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    function: str = "Mechanical"
    color: str = "#f2df88"
    opacity: float = 1.0
    visible: bool = True
    revision: int = 0
    saved_signature: tuple = ()
    group_revision: int = 0
    file_format: str = "gerber"
    excellon_source: ExcellonSource | None = None

    def signature(self) -> tuple:
        return tuple(self.objects)

    @property
    def modified(self) -> bool:
        return self.signature() != self.saved_signature

    @property
    def bounds(self) -> Bounds | None:
        if not self.objects:
            return None
        result = self.objects[0].bounds
        for obj in self.objects[1:]:
            result = result.union(obj.bounds)
        return result


def canonical_function(value):
    inner = re.fullmatch(r"(?:inner|iner|in)[ _.-]*(\d+)(?:[ _.-]*cu)?", value, re.IGNORECASE)
    if inner:
        return f"In{int(inner[1])}.Cu"
    known = (
        "F.Cu",
        "B.Cu",
        "F.Mask",
        "B.Mask",
        "F.Silk",
        "B.Silk",
        "F.Paste",
        "B.Paste",
        "Edge.Cuts",
        "Route.Cuts",
        "Drill",
        "Drill.PTH",
        "Drill.NPTH",
        "Drill.Blind",
        "Drill.Buried",
        "Drill drawing",
    )
    normalized = value.replace("_", ".")
    return next((role for role in known if role.lower() == normalized.lower()), value)


def detect_function(name: str, attributes: Attributes = ()) -> tuple[str, str]:
    if dict(attributes).get("EditorGerberRole", ()) == ("Route.Cuts",):
        return "Route.Cuts", "#ff77cc"
    attr = dict(attributes).get(".FileFunction", ())
    if attr and attr[0].lower() in ("plated", "nonplated"):
        kind = attr[3].lower() if len(attr) > 3 else ""
        if kind in ("blind", "buried"):
            return "Drill." + kind.title(), "#c7b7ef"
        return "Drill.PTH" if attr[0].lower() == "plated" else "Drill.NPTH", "#c7b7ef"
    if attr and attr[0].lower() == "drillmap":
        return "Drill drawing", "#c7b7ef"
    if not attr:
        legacy = {
            "srlc": ("F.Silk", "#f2df88"),
            "srls": ("B.Silk", "#d59bdf"),
            "mslc": ("F.Mask", "#5ebd81"),
            "msls": ("B.Mask", "#91c4dc"),
            "splc": ("F.Paste", "#a7bacd"),
            "spls": ("B.Paste", "#b7a3cb"),
            "olc": ("F.Cu", "#df6565"),
            "ols": ("B.Cu", "#65a2e6"),
            "fur": ("Drill", "#c7b7ef"),
        }
        if Path(name).stem.lower() in legacy:
            return legacy[Path(name).stem.lower()]
    text = ",".join(attr).lower() if attr else name.lower()
    if not attr:
        if re.search(r"drill[-_. ]?(?:map|drawing|legend)", text):
            return "Drill drawing", "#c7b7ef"
        if re.search(r"drill|fura[çc][aã]o|(?:^|[-_. ])n?pth(?:$|[-_. ])|\.drl$", text):
            role = "Drill.NPTH" if "npth" in text else "Drill.PTH" if "pth" in text else "Drill"
            return role, "#c7b7ef"
    inner = re.search(r"(?<![a-z0-9])(?:inner|iner|in)[ _.-]*(\d+)(?:[ _.-]*cu)?(?=$|[_. -])", text)
    if inner:
        return f"In{int(inner[1])}.Cu", "#d5aa58"
    if any(word in text for word in ("route_cuts", "route.cuts", "cutouts", "slots")):
        return "Route.Cuts", "#ff77cc"
    back = bool(re.search(r"(?:^|[-_. ])b[_. -]|bottom|,bot|\.gb[oslp](?:$|[^a-z])", text))
    side = "B" if back else "F"
    if any(k in text for k in ("legend", "silk", ".gto", ".gbo")):
        return f"{side}.Silk", "#f2df88" if not back else "#d59bdf"
    if any(k in text for k in ("soldermask", "mask", ".gts", ".gbs")):
        return f"{side}.Mask", "#5ebd81"
    if any(k in text for k in ("paste", ".gtp", ".gbp")):
        return f"{side}.Paste", "#a7bacd"
    if any(k in text for k in ("profile", "edge", "outline", ".gko", ".gm1")):
        return "Edge.Cuts", "#e7d153"
    if any(k in text for k in ("copper", ".cu", "_cu", ".gtl", ".gbl")):
        if attr and len(attr) > 2 and attr[2].lower() == "inr":
            return f"In{attr[1].lstrip('L')}.Cu", "#d5aa58"
        return f"{side}.Cu", "#df6565" if not back else "#65a2e6"
    return "Mechanical", "#9eb2c8"
