"""Pre-export validation and exact semantic round-trip checks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from gerber_editor.core.layer import GerberLayer
from gerber_editor.core.primitives import Arc, Flash, Region
from gerber_editor.gerber.errors import SaveError


def object_signature(obj) -> tuple:
    aperture = obj.aperture
    ap_signature = aperture.signature() if aperture else None
    return obj.geometry, ap_signature, obj.polarity, obj.attributes


def validate_layer(layer: GerberLayer) -> None:
    ids = set()
    for obj in layer.objects:
        if obj.id in ids:
            raise SaveError("ID de objeto duplicado.")
        ids.add(obj.id)
        if not isinstance(obj.geometry, Region) and obj.aperture is None:
            raise SaveError("Objeto sem aperture.")
        curves = [obj.geometry]
        if isinstance(obj.geometry, Region):
            if not obj.geometry.contours or any(not c for c in obj.geometry.contours):
                raise SaveError("Região vazia.")
            curves = [c for contour in obj.geometry.contours for c in contour]
            for contour in obj.geometry.contours:
                if any(a.end != b.start for a, b in zip(contour, contour[1:], strict=False)):
                    raise SaveError("Região com segmentos desconectados.")
                if contour[0].start != contour[-1].end:
                    raise SaveError("Região aberta.")
        for curve in curves:
            points = [curve.position] if isinstance(curve, Flash) else [curve.start, curve.end]
            if isinstance(curve, Arc):
                points.append(curve.center)
                if curve.radius == 0:
                    raise SaveError("Arco com raio zero.")
            for point in points:
                if not all(isinstance(v, Decimal) and v.is_finite() for v in (point.x, point.y)):
                    raise SaveError("Coordenada não finita ou sem precisão Decimal.")


@dataclass(frozen=True)
class ValidationReport:
    object_count: int
    bounds_match: bool
    mode: str
    warnings: tuple[str, ...] = ()


def compare_layers(expected: GerberLayer, actual: GerberLayer, mode: str) -> ValidationReport:
    expected_attributes = tuple(a for a in expected.attributes if a[0] != ".MD5")
    actual_attributes = tuple(a for a in actual.attributes if a[0] != ".MD5")
    if expected_attributes != actual_attributes:
        raise SaveError("Atributos de arquivo diferentes após reabertura; saída recusada.")
    if expected.legacy_names != actual.legacy_names:
        raise SaveError("Nomes de camadas legados diferentes após reabertura; saída recusada.")
    if len(expected.objects) != len(actual.objects):
        raise SaveError("Reabertura mudou o número de objetos; saída não foi gravada.")
    for index, (left, right) in enumerate(zip(expected.objects, actual.objects, strict=True)):
        if object_signature(left) != object_signature(right):
            raise SaveError(
                f"Reabertura mudou geometria/atributos do objeto {index + 1}; saída recusada."
            )
    left, right = expected.bounds, actual.bounds
    if left != right:
        raise SaveError("Bounds diferentes após reabertura; saída recusada.")
    return ValidationReport(len(actual.objects), True, mode)
