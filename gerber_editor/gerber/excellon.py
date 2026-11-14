"""Explicit-unit Excellon drilling and routing, represented in exact millimetres."""

import re
from decimal import Decimal as D

from gerber_editor.core.layer import CoordinateFormat, ExcellonSource, GerberLayer, detect_function
from gerber_editor.core.objects import Aperture, GerberObject, Polarity
from gerber_editor.core.primitives import Arc, Flash, Line, Point
from gerber_editor.gerber.errors import GerberError, SaveError, UnsupportedGerberError

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
FIELDS = re.compile(r"([XYIJ])(" + NUMBER + ")")


def is_excellon(data):
    return bool(re.match(rb"\s*(?:;[^\r\n]*\r?\n\s*)*M48\b", data.lstrip(b"\xef\xbb\xbf")))


class ExcellonParser:
    def parse(self, data, name="untitled.drl", path=None):
        if isinstance(data, str):
            data = data.encode("utf-8")
        text = data.decode("utf-8-sig", errors="replace")
        layer = GerberLayer(name, path=path, file_format="excellon")
        fmt = None
        declared = re.search(r"(?:FILE_FORMAT\s*=|FORMAT\s*=\{)\s*(\d+):(\d+)", text, re.I)
        if declared:
            fmt = CoordinateFormat(int(declared[1]), int(declared[2]))
        scale, suppression = None, "L"
        header, ended, absolute, down = True, False, True, False
        position, tool, mode = Point.of(0, 0), None, 5
        tools, attributes, ap_attributes, obj_attributes = {}, {}, {}, {}

        def coords(command, current):
            pairs = FIELDS.findall(command)
            if FIELDS.sub("", command) or len({k for k, _ in pairs}) != len(pairs):
                raise UnsupportedGerberError("Coordenadas Excellon não suportadas: " + command)
            if scale is None:
                raise GerberError("Excellon precisa declarar METRIC ou INCH antes das coordenadas.")
            values = {}
            for key, raw in pairs:
                if "." in raw:
                    value = D(raw)
                elif fmt:
                    value = CoordinateFormat(fmt.integer, fmt.decimal, suppression).decode(raw)
                elif D(raw) == 0:
                    value = D(0)
                else:
                    raise UnsupportedGerberError(
                        "Excellon com coordenadas inteiras precisa declarar o formato (FILE_FORMAT ou FORMAT); a escala não será presumida."
                    )
                values[key] = value * scale
            end = Point(
                values.get("X", current.x if absolute else D(0))
                + (D(0) if absolute else current.x),
                values.get("Y", current.y if absolute else D(0))
                + (D(0) if absolute else current.y),
            )
            return end, values

        def add(geometry):
            if tool is None:
                raise GerberError("Furação sem ferramenta selecionada.")
            if len(layer.objects) >= 200000:
                raise GerberError("Excellon excede 200000 objetos.")
            layer.objects.append(
                GerberObject(
                    geometry,
                    tool,
                    attributes=tuple(sorted(obj_attributes.items())),
                    origin="imported",
                )
            )

        for line_number, raw in enumerate(text.splitlines(), 1):
            try:
                command, _, comment = raw.partition(";")
                attr = re.search(r"#@!\s*(TF|TA|TO)([^,]+)(?:,(.*))?", comment)
                if attr:
                    dest = {"TF": attributes, "TA": ap_attributes, "TO": obj_attributes}[attr[1]]
                    dest[attr[2].strip()] = tuple((attr[3] or "").split(",")) if attr[3] else ()
                if re.search(r"#@!\s*TD", comment):
                    ap_attributes.clear()
                    obj_attributes.clear()
                cmd = re.sub(r"\s+", "", command).upper()
                if not cmd:
                    continue
                if ended:
                    raise GerberError("Dados após M30.")
                if cmd == "M48":
                    continue
                if cmd in ("M30", "M00", "M0"):
                    ended = True
                    continue
                if cmd in ("%", "M95"):
                    header = False
                    continue
                units = re.fullmatch(r"(METRIC|INCH)(?:,(TZ|LZ))?(?:,(0+)\.(0+))?", cmd)
                if units or cmd in ("M71", "M72"):
                    new_scale = (
                        D(1) if (units and units[1] == "METRIC") or cmd == "M71" else D("25.4")
                    )
                    if scale is not None and scale != new_scale:
                        raise UnsupportedGerberError("Mudança de unidade dentro do Excellon.")
                    scale = new_scale
                    if units:
                        # Excellon names the zeros kept: TZ suppresses leading zeros.
                        suppression = "T" if units[2] == "LZ" else "L"
                        if units[3]:
                            fmt = CoordinateFormat(len(units[3]), len(units[4]))
                    continue
                if cmd in ("FMAT,2", "G90", "G91", "ICI,ON", "ICI,OFF"):
                    if cmd != "FMAT,2":
                        absolute = cmd in ("G90", "ICI,OFF")
                    continue
                definition = re.fullmatch(r"T(\d+)((?:[FSC]" + NUMBER + r")+)", cmd)
                if definition:
                    diameter = re.search(r"C(" + NUMBER + ")", definition[2])
                    if scale is None or not diameter or D(diameter[1]) <= 0:
                        raise GerberError(
                            "Ferramenta Excellon precisa de unidade e diâmetro positivo."
                        )
                    number = int(definition[1])
                    if number <= 0 or number in tools:
                        raise GerberError("Ferramenta Excellon duplicada ou inválida.")
                    tools[number] = Aperture(
                        number + 10,
                        "C",
                        (D(diameter[1]) * scale,),
                        tuple(sorted(ap_attributes.items())),
                    )
                    layer.apertures[tools[number].code] = tools[number]
                    continue
                selection = re.fullmatch(r"T(\d+)", cmd)
                if selection:
                    number = int(selection[1])
                    if number and number not in tools:
                        raise GerberError("Ferramenta Excellon não definida.")
                    tool = tools.get(number)
                    continue
                if header:
                    raise UnsupportedGerberError("Cabeçalho Excellon não suportado: " + cmd)
                if cmd in ("M15", "M16", "M17"):
                    down = cmd == "M15"
                    continue
                repeat = re.fullmatch(r"R(\d+)(.*)", cmd)
                if repeat:
                    if mode != 5 or not layer.objects or int(repeat[1]) > 200000:
                        raise UnsupportedGerberError("Repetição Excellon inválida.")
                    _, values = coords(repeat[2], Point.of(0, 0))
                    for _ in range(int(repeat[1])):
                        position = Point(
                            position.x + values.get("X", D(0)), position.y + values.get("Y", D(0))
                        )
                        add(Flash(position))
                    continue
                if "G85" in cmd:
                    before, after = cmd.split("G85")
                    start, _ = coords(before, position)
                    position, _ = coords(after, start)
                    add(Line(start, position))
                    continue
                code = re.match(r"G0?([01235])(?=[XYIJ]|$)", cmd)
                if code:
                    mode = int(code[1])
                    cmd = cmd[code.end() :]
                if not cmd:
                    continue
                end, values = coords(cmd, position)
                if mode == 5:
                    add(Flash(end))
                elif mode in (1, 2, 3) and down:
                    if mode == 1:
                        add(Line(position, end))
                    else:
                        center = Point(
                            position.x + values.get("I", D(0)), position.y + values.get("J", D(0))
                        )
                        arc = Arc(position, end, center, mode == 2)
                        end_radius = ((end.x - center.x) ** 2 + (end.y - center.y) ** 2).sqrt()
                        tolerance = D(2).scaleb(-fmt.decimal) * scale if fmt else D("0.000002")
                        if not arc.radius or abs(arc.radius - end_radius) > tolerance:
                            raise GerberError("Arco Excellon com raios inconsistentes.")
                        add(arc)
                elif mode != 0:
                    raise UnsupportedGerberError("Roteamento Excellon sem M15.")
                position = end
            except (ValueError, ArithmeticError, GerberError) as exc:
                error = (
                    UnsupportedGerberError
                    if isinstance(exc, UnsupportedGerberError)
                    else GerberError
                )
                raise error(f"{name}, linha {line_number}: {exc}") from exc
        if not ended or scale is None:
            raise GerberError("Excellon precisa declarar unidade e terminar com M30.")
        layer.attributes = tuple(sorted(attributes.items()))
        layer.function, layer.color = detect_function(name, layer.attributes)
        if layer.function == "Mechanical":
            layer.function, layer.color = "Drill", "#c7b7ef"
        layer.saved_signature = layer.signature()
        layer.excellon_source = ExcellonSource(data, layer.signature())
        return layer


def serialize_excellon(layer, preservation=False):
    source = layer.excellon_source
    if preservation and source and layer.signature() == source.original_signature:
        return source.data
    tools = {}
    for obj in layer.objects:
        ap = obj.aperture
        if (
            not isinstance(obj.geometry, (Flash, Line, Arc))
            or not ap
            or ap.shape != "C"
            or len(ap.parameters) != 1
            or ap.width <= 0
            or obj.polarity != Polarity.DARK
        ):
            raise SaveError(
                "Excellon aceita furos e rasgos com ferramenta circular. Use Salvar como Gerber para outras formas."
            )
        tools.setdefault(ap.signature(), (len(tools) + 1, ap))
    lines = ["M48", "; FORMAT={-:-/ absolute / metric / decimal}"]
    lines += [
        f"; #@! TF{key}{',' if values else ''}{','.join(values)}"
        for key, values in layer.attributes
        if key != ".MD5"
    ]
    lines += ["FMAT,2", "METRIC"]
    for number, ap in tools.values():
        lines.append("; #@! TD")
        lines += [
            f"; #@! TA{key}{',' if values else ''}{','.join(values)}"
            for key, values in ap.attributes
        ]
        lines.append(f"T{number}C{ap.width:f}")
    lines += ["%", "G90", "G05"]

    def decimal(value):
        text = format(value, "f")
        return text if "." in text else text + ".0"

    def xy(point):
        # Always include decimal points to remove any implicit-format ambiguity.
        return f"X{decimal(point.x)}Y{decimal(point.y)}"

    for obj in layer.objects:
        number, _ = tools[obj.aperture.signature()]
        lines += ["; #@! TD", f"T{number}"]
        lines += [
            f"; #@! TO{key}{',' if values else ''}{','.join(values)}"
            for key, values in obj.attributes
        ]
        g = obj.geometry
        if isinstance(g, Flash):
            lines += ["G05", xy(g.position)]
        elif isinstance(g, Line):
            lines.append(xy(g.start) + "G85" + xy(g.end))
        else:
            i, j = g.center.x - g.start.x, g.center.y - g.start.y
            lines += [
                "G00" + xy(g.start),
                "M15",
                f"G0{2 if g.clockwise else 3}{xy(g.end)}I{decimal(i)}J{decimal(j)}",
                "M16",
                "G05",
            ]
    return ("\n".join(lines + ["M30", ""])).encode("utf-8")
