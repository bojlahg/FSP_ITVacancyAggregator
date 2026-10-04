"""Безопасная арифметика для numeric-ответов: только числа, параметры и + - * / // % ** min max round abs."""

import ast
import operator
import re

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"min": min, "max": max, "round": round, "abs": abs}
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def substitute(text: str, params: dict) -> str:
    """{{name}} → значение параметра. Одинарные фигурные скобки (код, JSON) не трогаются."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in params:
            raise KeyError(f"неизвестный параметр {{{{{name}}}}}")
        return str(params[name])

    return PLACEHOLDER.sub(replace, text)


def evaluate(expr: str, params: dict) -> float:
    tree = ast.parse(substitute(expr, params), mode="eval")
    return float(_eval(tree.body))


def _eval(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        return _BINARY[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*(_eval(arg) for arg in node.args))
    raise ValueError(f"недопустимое выражение: {ast.dump(node)}")
