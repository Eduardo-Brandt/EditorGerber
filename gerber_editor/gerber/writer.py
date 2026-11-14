"""Lossless patch export and normalized logical export, validated before commit."""

from __future__ import annotations

import os
import re
import tempfile
from copy import copy
from decimal import Decimal
from enum import Enum
from pathlib import Path

from gerber_editor.core.layer import CoordinateFormat, GerberLayer
from gerber_editor.core.objects import Aperture
from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.gerber.errors import SaveError
from gerber_editor.gerber.parser import GerberParser
from gerber_editor.validation.checks import ValidationReport, compare_layers, validate_layer

D = Decimal


class SaveMode(str, Enum):
    PRESERVATION = "preservation"
    NORMALIZED = "normalized"


def _decimal(value: Decimal) -> str:
    return format(value, "f")


class _Emitter:
    def __init__(self, fmt: CoordinateFormat, scale: Decimal):
        self.fmt, self.scale = fmt, scale

    def coordinate(self, value: Decimal) -> str:
        scaled = value / self.scale * (D(10) ** self.fmt.decimal)
        if scaled != scaled.to_integral_value():
            raise SaveError(
                "Coordenada não representável na precisão de saída. Use outro modo/unidade."
            )
        number = int(scaled)
        digits = str(abs(number)).zfill(self.fmt.integer + self.fmt.decimal)
        if len(digits) > self.fmt.integer + self.fmt.decimal:
            raise SaveError("Coordenada excede o formato FS de saída.")
        if self.fmt.suppression == "L":
            digits = digits.lstrip("0") or "0"
        else:
            digits = digits.rstrip("0") or "0"
        return ("-" if number < 0 else "") + digits

    def xy(self, point: Point) -> str:
        return f"X{self.coordinate(point.x)}Y{self.coordinate(point.y)}"

    def aperture(self, ap: Aperture) -> str:
        if ap.macro:
            name = f"GE_D{ap.code}"
            primitives = [
                f"{p.code},{','.join(_decimal(v) for v in p.in_units(self.scale))}*"
                for p in ap.macro
            ]
            return f"%AM{name}*\n{chr(10).join(primitives)}%\n%ADD{ap.code}{name}*%\n"
        params = []
        for i, value in enumerate(ap.parameters):
            params.append(
                _decimal(value if ap.shape == "P" and i in (1, 2) else value / self.scale)
            )
        return f"%ADD{ap.code}{ap.shape},{'X'.join(params)}*%\n"

    def curve(self, curve: Line | Arc) -> str:
        if isinstance(curve, Line):
            return f"G01{self.xy(curve.end)}D01*\n"
        i = self.coordinate(curve.center.x - curve.start.x)
        j = self.coordinate(curve.center.y - curve.start.y)
        return f"G{2 if curve.clockwise else 3:02}{self.xy(curve.end)}I{i}J{j}D01*\n"

    def objects(self, objects: list) -> str:
        output = ["G75*\n"]
        for obj in objects:
            output.extend(["%TD*%\n", f"%LP{obj.polarity.value}*%\n"])
            for name, values in obj.attributes:
                output.append(f"%TO{name}{',' if values else ''}{','.join(values)}*%\n")
            if obj.aperture:
                output.append(f"D{obj.aperture.code}*\n")
            geometry = obj.geometry
            if isinstance(geometry, Flash):
                output.append(f"G01{self.xy(geometry.position)}D03*\n")
            elif isinstance(geometry, Region):
                output.append("G36*\n")
                for contour in geometry.contours:
                    output.append(f"G01{self.xy(contour[0].start)}D02*\n")
                    output.extend(self.curve(curve) for curve in contour)
                output.append("G37*\n")
            else:
                output.append(f"G01{self.xy(geometry.start)}D02*\n")
                output.append(self.curve(geometry))
        return "".join(output)


class GerberWriter:
    def serialize(self, layer: GerberLayer, mode: SaveMode = SaveMode.PRESERVATION) -> bytes:
        validate_layer(layer)
        if layer.file_format == "excellon":
            from gerber_editor.gerber.excellon import serialize_excellon

            data = serialize_excellon(layer, mode == SaveMode.PRESERVATION)
        elif mode == SaveMode.PRESERVATION and layer.source:
            data = self._preservation(layer)
        else:
            data = self._normalized(layer)
        parsed = GerberParser().parse(data, layer.name)
        compare_layers(layer, parsed, mode.value)
        return data

    def save(
        self,
        layer: GerberLayer,
        path: str | Path,
        mode: SaveMode = SaveMode.PRESERVATION,
        *,
        overwrite: bool = False,
    ) -> ValidationReport:
        path = Path(path)
        if layer.file_format == "excellon" and path.suffix.lower() in (".gbr", ".ger", ".gerber"):
            layer = copy(layer)
            layer.file_format = "gerber"
        elif path.suffix.lower() in (".drl", ".xln") and layer.file_format != "excellon":
            layer = copy(layer)
            layer.file_format = "excellon"
        if path.exists() and not overwrite:
            raise SaveError("Destino já existe. Confirmação explícita é necessária.")
        data = self.serialize(layer, mode)
        actual = GerberParser().parse(data, path.name)
        report = compare_layers(layer, actual, mode.value)
        handle, temporary = tempfile.mkstemp(prefix=".gerber-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Validate the staged file from disk before the atomic commit.
            compare_layers(layer, GerberParser().parse_file(temporary), mode.value)
            # Link is an atomic no-clobber commit when overwrite was not authorized.
            if overwrite:
                os.replace(temporary, path)
            else:
                os.link(temporary, path)
                os.unlink(temporary)
            temporary = ""
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        # Read the actual destination again, as promised by the UI workflow.
        report = compare_layers(layer, GerberParser().parse_file(path), mode.value)
        return report

    def _preservation(self, layer: GerberLayer) -> bytes:
        source = layer.source
        originals = source.original_objects
        existing = [obj for obj in layer.objects if obj.id in originals]
        existing_ids = {obj.id for obj in existing}
        if any(obj != originals[obj.id] for obj in existing):
            raise SaveError("Objeto importado alterado: exporte em modo normalized.")
        if [o.id for o in existing] != [o for o in originals if o in existing_ids]:
            raise SaveError("Ordem original alterada: exporte em modo normalized.")
        additions = [obj for obj in layer.objects if obj.id not in originals]
        if layer.objects != existing + additions:
            raise SaveError("Preservation exige novas geometrias após os objetos originais.")
        removed = [obj for key, obj in originals.items() if key not in existing_ids]
        if not additions and not removed:
            return source.data
        deleted = {index for obj in removed for index in obj.source_tokens}
        emitter = _Emitter(source.coordinate_format, source.unit_scale)
        new_apertures = {}
        for obj in additions:
            ap = obj.aperture
            if ap is None:
                continue
            if ap.code in layer.apertures and layer.apertures[ap.code] != ap:
                raise SaveError("D-code colide com aperture original.")
            if ap.code not in layer.apertures:
                if ap.code in new_apertures and new_apertures[ap.code] != ap:
                    raise SaveError("D-code novo duplicado.")
                new_apertures[ap.code] = ap
        inserted = ["\n%TD*%\n"]
        for ap in new_apertures.values():
            inserted.append("%TD*%\n")
            for key, values in ap.attributes:
                inserted.append(f"%TA{key}{',' if values else ''}{','.join(values)}*%\n")
            inserted.append(emitter.aperture(ap))
        if additions:
            inserted.append(emitter.objects(additions))
        output = []
        for index, token in enumerate(source.tokens):
            raw = token.raw
            if token.extended and "TF.MD5," in token.command:
                raw = re.sub(r"TF\.MD5,[^*]*\*", "", raw)
                if raw.strip() == "%%":
                    raw = ""
            if index in deleted and token.command.strip() in ("G36", "G37"):
                raw = "".join(c for c in raw if c.isspace())
            elif source.operations.get(index) is not None and removed:
                operation = 2 if index in deleted else source.operations[index]
                if index in deleted:
                    raw = re.sub(r"[IJ][+-]?(?:\d+(?:\.\d*)?|\.\d+)", "", raw)
                if re.search(r"D0?[123](?=\s*\*)", raw):
                    raw = re.sub(r"D0?[123](?=\s*\*)", f"D{operation:02}", raw)
                else:
                    raw = raw[:-1] + f"D{operation:02}*"
            if index == source.end_token and additions:
                output.append("".join(inserted))
            output.append(raw)
        output.append(source.data[source.tokens[-1].end :].decode("latin-1"))
        return "".join(output).encode("latin-1")

    def _normalized(self, layer: GerberLayer) -> bytes:
        # Try metric, then original units to retain sub-nanometre inch coordinates exactly.
        scales = [D(1)]
        if layer.source and layer.source.unit_scale != D(1):
            scales.append(layer.source.unit_scale)
        error = None
        for scale in scales:
            try:
                return self._normalized_in_unit(layer, scale)
            except SaveError as exc:
                error = exc
        raise error

    @staticmethod
    def _normalized_in_unit(layer: GerberLayer, scale: Decimal) -> bytes:
        decimals = 6
        if layer.source and layer.source.unit_scale == scale:
            # Legacy arcs can carry radius discrepancies permitted by their
            # original coordinate grid. Increasing FS precision would falsely
            # promise tighter arc accuracy without changing their exact data.
            decimals = min(6, layer.source.coordinate_format.decimal)
        emitter = _Emitter(CoordinateFormat(6, decimals), scale)
        output = [
            "G04 Editor Gerber - normalized logical geometry*\n",
            f"%FSLAX6{decimals}Y6{decimals}*%\n",
            "%MOMM*%\n" if scale == 1 else "%MOIN*%\n",
        ]
        for key, values in layer.attributes:
            if key != ".MD5":
                output.append(f"%TF{key}{',' if values else ''}{','.join(values)}*%\n")
        for name in layer.legacy_names:
            output.append(f"%LN{name}*%\n")
        apertures = {}
        for obj in layer.objects:
            ap = obj.aperture
            if ap:
                if ap.code in apertures and apertures[ap.code] != ap:
                    raise SaveError("D-codes colidentes.")
                apertures[ap.code] = ap
        for ap in apertures.values():
            output.append("%TD*%\n")
            for key, values in ap.attributes:
                output.append(f"%TA{key}{',' if values else ''}{','.join(values)}*%\n")
            output.append(emitter.aperture(ap))
        output.extend([emitter.objects(layer.objects), "%TD*%\nM02*\n"])
        return "".join(output).encode("latin-1")
