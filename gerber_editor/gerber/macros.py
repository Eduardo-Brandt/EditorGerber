"""Safe Decimal macro evaluator. No eval(), code execution or geometry flattening."""

from __future__ import annotations

import ast
import re
from decimal import Decimal, DecimalException

from gerber_editor.core.macros import MacroPrimitive
from gerber_editor.gerber.errors import GerberError, UnsupportedGerberError

D = Decimal


def expression(source: str, variables: dict[int, Decimal]) -> Decimal:
    source = re.sub(r"\s+", "", source).replace("x", "*").replace("X", "*")
    if len(source) > 1024 or re.search(r"[^0-9.$+*/()\-]", source):
        raise GerberError("Expressão de macro inválida.")
    source = re.sub(r"\$(\d+)", r"v\1", source)
    try:
        tree = ast.parse(source, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 256:
            raise GerberError("Expressão de macro excede o limite de complexidade.")

        def visit(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return D(ast.get_source_segment(source, node))
            if isinstance(node, ast.Name) and re.fullmatch(r"v\d+", node.id):
                return variables.get(int(node.id[1:]), D(0))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand)
                return -value if isinstance(node.op, ast.USub) else value
            if isinstance(node, ast.BinOp):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    return left / right
            raise GerberError("Operador de macro não permitido.")

        result = visit(tree.body)
        if not result.is_finite():
            raise GerberError("Resultado de macro não finito.")
        return result
    except (SyntaxError, DecimalException, RecursionError) as exc:
        raise GerberError(f"Expressão de macro inválida: {source}") from exc


def evaluate_macro(
    body: str, modifiers: tuple[Decimal, ...], scale: Decimal
) -> tuple[MacroPrimitive, ...]:
    variables = dict(enumerate(modifiers, 1))
    primitives = []
    statements = body.split("*")
    if len(statements) > 10000:
        raise GerberError("Macro excede o limite de primitivas.")
    for statement in statements:
        statement = re.sub(r"\s+", "", statement)
        if not statement or statement.startswith("0"):
            continue
        assignment = re.fullmatch(r"\$(\d+)=(.*)", statement)
        if assignment:
            variables[int(assignment[1])] = expression(assignment[2], variables)
            continue
        fields = statement.split(",")
        if not fields[0].isdigit():
            raise GerberError("Código de primitiva macro inválido.")
        code = int(fields[0])
        if code not in (1, 4, 5, 20, 21, 22):
            raise UnsupportedGerberError(f"Primitiva de macro {code} ainda não suportada.")
        values = tuple(expression(field, variables) for field in fields[1:])
        if code == 1 and len(values) == 4:
            values += (D(0),)
        expected = {1: 5, 5: 6, 20: 7, 21: 6, 22: 6}.get(code)
        if code == 4:
            if len(values) < 9 or values[1] != int(values[1]) or not 3 <= values[1] <= 5000:
                raise GerberError("Outline de macro tem contagem de vértices inválida.")
            expected = 2 * (int(values[1]) + 1) + 3
        if len(values) != expected or values[0] not in (0, 1):
            raise GerberError("Parâmetros ou exposição de macro inválidos.")
        if code == 4 and values[2:4] != values[-3:-1]:
            raise GerberError("Outline de macro aberto.")
        if code == 5 and (values[1] != int(values[1]) or not 3 <= values[1] <= 12):
            raise GerberError("Polígono de macro tem contagem de vértices inválida.")
        dimensions = {1: (1,), 4: (), 5: (4,), 20: (1,), 21: (1, 2), 22: (1, 2)}[code]
        if any(values[i] <= 0 for i in dimensions):
            raise GerberError("Dimensão de macro deve ser positiva.")
        primitive = MacroPrimitive(code, values)
        lengths = primitive.length_indexes()
        primitives.append(
            MacroPrimitive(
                code, tuple(v * scale if i in lengths else v for i, v in enumerate(values))
            )
        )
    if not primitives:
        raise GerberError("Macro sem primitivas suportadas.")
    return tuple(primitives)
