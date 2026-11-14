"""Strict RS-274X state machine; source records remain separate from geometry."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from gerber_editor.core.layer import CoordinateFormat, GerberLayer, GerberSource, detect_function
from gerber_editor.core.objects import Aperture, Attributes, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line, Point, Region
from gerber_editor.gerber.errors import GerberError, UnsupportedGerberError
from gerber_editor.gerber.macros import evaluate_macro
from gerber_editor.gerber.tokenizer import Token, tokenize

D = Decimal
FIELDS = re.compile(r"([XYIJ])([+-]?(?:\d+(?:\.\d*)?|\.\d+))")


def attributes(values: dict[str, tuple[str, ...]]) -> Attributes:
    return tuple(sorted(values.items()))


@dataclass
class _State:
    layer: GerberLayer
    fmt: CoordinateFormat | None = None
    scale: Decimal | None = None
    position: Point = Point.of(0, 0)
    aperture: Aperture | None = None
    operation: int = 2
    interpolation: int = 1
    multi_quadrant: bool = True
    polarity: Polarity = Polarity.DARK
    file_attributes: dict = field(default_factory=dict)
    aperture_attributes: dict = field(default_factory=dict)
    object_attributes: dict = field(default_factory=dict)
    region_start: int | None = None
    contours: list = field(default_factory=list)
    contour: list = field(default_factory=list)
    operations: dict[int, int] = field(default_factory=dict)
    ended: bool = False
    end_token: int = -1
    macros: dict[str, str] = field(default_factory=dict)


class GerberParser:
    def parse_file(self, path: str | Path) -> GerberLayer:
        path = Path(path)
        return self.parse(path.read_bytes(), path.name, path)

    def parse(
        self, data: bytes | str, name: str = "untitled.gbr", path: Path | None = None
    ) -> GerberLayer:
        if isinstance(data, str):
            data = data.encode("latin-1")
        from gerber_editor.gerber.excellon import ExcellonParser, is_excellon

        if is_excellon(data):
            return ExcellonParser().parse(data, name, path)
        tokens = tokenize(data)
        state = _State(GerberLayer(name=name, path=path))
        for index, token in enumerate(tokens):
            try:
                if state.ended:
                    raise GerberError("Dados após M02.")
                if token.extended:
                    self._extended(state, token)
                else:
                    self._standard(state, token.command, index)
            except (GerberError, ValueError, InvalidOperation) as exc:
                error_type = (
                    UnsupportedGerberError
                    if isinstance(exc, UnsupportedGerberError)
                    else GerberError
                )
                raise error_type(f"{name}, byte {token.start}: {exc}") from exc
        if state.region_start is not None:
            raise GerberError("Região sem G37.")
        if not state.ended or state.fmt is None or state.scale is None:
            raise GerberError("Arquivo precisa declarar FS, MO e terminar com M02.")
        layer = state.layer
        layer.attributes = attributes(state.file_attributes)
        layer.function, layer.color = detect_function(name, layer.attributes)
        if layer.function == "Mechanical":
            for legacy_name in layer.legacy_names:
                function, color = detect_function(legacy_name, layer.attributes)
                if function != "Mechanical":
                    layer.function, layer.color = function, color
                    break
        layer.source = GerberSource(
            data,
            tokens,
            state.fmt,
            state.scale,
            {obj.id: obj for obj in layer.objects},
            state.operations,
            state.end_token,
            state.polarity.value,
        )
        layer.saved_signature = layer.signature()
        return layer

    def _extended(self, state: _State, token: Token) -> None:
        if token.command.startswith("AM"):
            header, _, body = token.command.partition("*")
            name = header[2:].strip()
            if not re.fullmatch(r"[A-Za-z_$][\w.$]*", name) or name in state.macros:
                raise GerberError("Nome de macro inválido ou duplicado.")
            state.macros[name] = body
            return
        for original in token.command.rstrip("*").split("*"):
            cmd = re.sub(r"\s+", "", original)
            if cmd.startswith("FS"):
                match = re.fullmatch(r"FS([LT])AX(\d)(\d)Y(\d)(\d)", cmd)
                if not match:
                    raise UnsupportedGerberError("FS incremental ou formato não suportado.")
                suppression, xi, xd, yi, yd = match.groups()
                if (xi, xd) != (yi, yd) or not (1 <= int(xi) <= 6 and 1 <= int(xd) <= 7):
                    raise UnsupportedGerberError(
                        "Formatos X/Y diferentes ou fora dos limites do MVP."
                    )
                fmt = CoordinateFormat(int(xi), int(xd), suppression)
                if state.fmt and state.fmt != fmt:
                    raise UnsupportedGerberError("Mudança de FS dentro do arquivo.")
                state.fmt = fmt
            elif cmd in ("MOMM", "MOIN"):
                scale = D(1) if cmd == "MOMM" else D("25.4")
                if state.scale and state.scale != scale:
                    raise UnsupportedGerberError("Mudança de unidade dentro do arquivo.")
                state.scale = scale
            elif cmd == "IPPOS":
                # Legacy positive image polarity is the normal RS-274X image.
                pass
            elif cmd == "IPNEG":
                raise UnsupportedGerberError("Imagem IPNEG requer suporte a plano negativo global.")
            elif cmd.startswith("LN"):
                state.layer.legacy_names += (original[2:].strip(),)
            elif cmd.startswith("IN"):
                # Legacy descriptive names have no effect on the image. The
                # lossless source keeps them for preservation export.
                pass
            elif cmd.startswith("AD"):
                self._aperture(state, cmd)
            elif cmd in ("LPD", "LPC"):
                if state.region_start is not None:
                    raise GerberError("Polaridade alterada dentro de região.")
                state.polarity = Polarity(cmd[-1])
            elif cmd.startswith(("TF", "TA", "TO")):
                target = {
                    "TF": state.file_attributes,
                    "TA": state.aperture_attributes,
                    "TO": state.object_attributes,
                }[cmd[:2]]
                parts = original[2:].strip().split(",")
                if not parts[0]:
                    raise GerberError("Atributo sem nome.")
                target[parts[0]] = tuple(parts[1:])
            elif cmd.startswith("TD"):
                name = cmd[2:]
                for target in (state.aperture_attributes, state.object_attributes):
                    if name:
                        target.pop(name, None)
                    else:
                        target.clear()
            else:
                raise UnsupportedGerberError(f"Comando estendido não suportado: %{cmd}*%")

    def _aperture(self, state: _State, cmd: str) -> None:
        if state.scale is None:
            raise GerberError("MO deve vir antes de AD.")
        match = re.fullmatch(r"ADD(\d+)([A-Za-z_$][\w.$]*)(?:,(.*))?", cmd)
        if not match:
            raise GerberError("Definição AD inválida.")
        code, shape, raw = match.groups()
        params = tuple(D(p) for p in raw.split("X")) if raw else ()
        if not all(value.is_finite() for value in params):
            raise GerberError("Parâmetro de aperture não finito.")
        if int(code) < 10 or int(code) in state.layer.apertures:
            raise GerberError("D-code de aperture inválido/duplicado.")
        if shape not in ("C", "R", "O", "P"):
            if shape not in state.macros:
                raise GerberError(f"Macro {shape} não definida.")
            macro = evaluate_macro(state.macros[shape], params, state.scale)
            state.layer.apertures[int(code)] = Aperture(
                int(code), "MACRO", params, attributes(state.aperture_attributes), macro
            )
            return
        allowed = {"C": (1, 2), "R": (2, 3), "O": (2, 3), "P": (2, 3, 4)}
        if (
            len(params) not in allowed[shape]
            or int(code) < 10
            or int(code) in state.layer.apertures
        ):
            raise GerberError("Parâmetros ou D-code de aperture inválidos/duplicados.")
        scaled = []
        for i, value in enumerate(params):
            scaled.append(value if shape == "P" and i in (1, 2) else value * state.scale)
        if (scaled[0] < 0 if shape == "C" else scaled[0] <= 0) or (
            shape in ("R", "O") and scaled[1] <= 0
        ):
            raise GerberError("Dimensão de aperture deve ser positiva.")
        if shape == "P" and (params[1] != int(params[1]) or not 3 <= params[1] <= 12):
            raise GerberError("Polígono deve ter de 3 a 12 vértices.")
        hole_index = {"C": 1, "R": 2, "O": 2, "P": 3}[shape]
        if len(scaled) > hole_index:
            limit = min(scaled[:2]) if shape in ("R", "O") else scaled[0]
            if not 0 <= scaled[hole_index] < limit:
                raise GerberError("Furo de aperture inválido.")
        state.layer.apertures[int(code)] = Aperture(
            int(code), shape, tuple(scaled), attributes(state.aperture_attributes)
        )

    def _standard(self, state: _State, original: str, index: int) -> None:
        if original.lstrip().startswith("G04"):
            return
        cmd = re.sub(r"\s+", "", original)
        if cmd in ("M02", "M2"):
            if state.region_start is not None:
                raise GerberError("M02 dentro de região.")
            state.ended, state.end_token = True, index
            return
        gcodes = [int(g) for g in re.findall(r"G(\d+)", cmd)]
        for code in gcodes:
            if code in (1, 2, 3):
                state.interpolation = code
            elif code == 74:
                state.multi_quadrant = False
            elif code == 75:
                state.multi_quadrant = True
            elif code in (54, 90):
                pass
            elif code == 36:
                if state.region_start is not None or cmd != "G36":
                    raise GerberError("G36 inválido ou região aninhada.")
                state.region_start, state.contours, state.contour = index, [], []
            elif code == 37:
                if state.region_start is None or cmd != "G37":
                    raise GerberError("G37 sem G36 ou comando combinado.")
                self._finish_contour(state)
                if not state.contours:
                    raise GerberError("Região vazia.")
                obj = GerberObject(
                    Region(tuple(state.contours)),
                    None,
                    state.polarity,
                    attributes(state.object_attributes),
                    source_tokens=tuple(range(state.region_start, index + 1)),
                    origin="imported",
                )
                state.layer.objects.append(obj)
                state.region_start = None
            else:
                raise UnsupportedGerberError(f"G{code:02} não suportado.")
        rest = re.sub(r"G\d+", "", cmd)
        dmatch = re.search(r"D(\d+)$", rest)
        explicit = int(dmatch.group(1)) if dmatch else None
        if dmatch:
            rest = rest[: dmatch.start()]
        pairs = FIELDS.findall(rest)
        if FIELDS.sub("", rest) or len({k for k, _ in pairs}) != len(pairs):
            raise GerberError(f"Comando inválido: {original}")
        if explicit is not None and explicit >= 10:
            if pairs or state.region_start is not None:
                raise GerberError("Seleção de aperture em posição inválida.")
            if explicit not in state.layer.apertures:
                raise GerberError(f"Aperture D{explicit} não definida.")
            state.aperture = state.layer.apertures[explicit]
            return
        if explicit is not None:
            if explicit not in (1, 2, 3):
                raise GerberError(f"Operação D{explicit} inválida.")
            state.operation = explicit
        if not pairs and explicit is None:
            return
        if not pairs and explicit == 2:
            return
        if state.fmt is None or state.scale is None:
            raise GerberError("Coordenadas antes de FS/MO.")
        values = {k: state.fmt.decode(v) * state.scale for k, v in pairs}
        destination = Point(values.get("X", state.position.x), values.get("Y", state.position.y))
        operation = state.operation
        state.operations[index] = operation
        if operation == 2:
            if state.region_start is not None:
                self._finish_contour(state)
        elif operation == 3:
            if state.region_start is not None:
                raise GerberError("Flash dentro de região.")
            self._require_aperture(state)
            self._add(state, Flash(destination), index)
        else:
            if state.region_start is None:
                self._require_aperture(state)
                aperture = state.aperture
                if aperture.macro:
                    raise UnsupportedGerberError("Draw com aperture macro ainda não suportado.")
                hole_index = {"C": 1, "R": 2, "O": 2, "P": 3}[aperture.shape]
                if len(aperture.parameters) > hole_index and aperture.parameters[hole_index] != 0:
                    raise UnsupportedGerberError("Draw com aperture furada não suportado.")
            if state.interpolation == 1:
                if "I" in values or "J" in values:
                    raise GerberError("I/J em interpolação linear.")
                curve = Line(state.position, destination)
            else:
                curve = self._arc(state, destination, values)
            if state.region_start is not None:
                state.contour.append(curve)
            else:
                self._add(state, curve, index)
        state.position = destination

    @staticmethod
    def _require_aperture(state: _State) -> None:
        if state.aperture is None:
            raise GerberError("Objeto sem aperture selecionada.")

    @staticmethod
    def _add(state: _State, geometry, index: int) -> None:
        state.layer.objects.append(
            GerberObject(
                geometry,
                state.aperture,
                state.polarity,
                attributes(state.object_attributes),
                source_tokens=(index,),
                origin="imported",
            )
        )

    @staticmethod
    def _finish_contour(state: _State) -> None:
        if not state.contour:
            return
        if state.contour[-1].end != state.contour[0].start:
            raise GerberError("Contorno de região aberto; nenhum reparo foi aplicado.")
        state.contours.append(tuple(state.contour))
        state.contour = []

    @staticmethod
    def _arc(state: _State, end: Point, values: dict) -> Arc:
        i, j = values.get("I", D(0)), values.get("J", D(0))
        if i == 0 and j == 0:
            raise GerberError("Arco sem centro válido.")
        offsets = (
            [(i, j)]
            if state.multi_quadrant
            else list({(a * abs(i), b * abs(j)) for a in (-1, 1) for b in (-1, 1)})
        )
        tolerance = D(2).scaleb(-state.fmt.decimal) * state.scale
        candidates = []
        for dx, dy in offsets:
            center = Point(state.position.x + dx, state.position.y + dy)
            arc = Arc(state.position, end, center, state.interpolation == 2)
            end_radius = ((end.x - center.x) ** 2 + (end.y - center.y) ** 2).sqrt()
            error = abs(arc.radius - end_radius)
            if error <= tolerance and (
                state.multi_quadrant or abs(arc.angles()[1]) <= math.pi / 2 + 1e-6
            ):
                candidates.append((error, arc))
        if not candidates:
            raise GerberError("Arco inválido: raios inconsistentes ou quadrante incorreto.")
        return min(candidates, key=lambda pair: pair[0])[1]
