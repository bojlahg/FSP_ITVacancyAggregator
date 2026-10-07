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
# {{n}} или {{n|повтор|повтора|повторов}}: формы — для 1, 2–4 и 5+; кириллица отличает их от пайпов Angular
_FORM = r"[а-яё][^{}|]*"
PLACEHOLDER = re.compile(rf"\{{\{{\s*(\w+)\s*(?:\|({_FORM})\|({_FORM})\|({_FORM}))?\}}\}}", re.IGNORECASE)


def plural(n: int, one: str, few: str, many: str) -> str:
    """Форма слова после числа: 1 повтор, 3 повтора, 11 повторов, 21 повтор."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def substitute(text: str, params: dict) -> str:
    """{{name}} → значение параметра, {{name|форма1|форма2|форма5}} → «число слово» в нужной форме.

    Одинарные фигурные скобки (код, JSON) не трогаются.
    """

    def replace(match: re.Match) -> str:
        name, *forms = match.groups()
        if name not in params:
            raise KeyError(f"неизвестный параметр {{{{{name}}}}}")
        value = params[name]
        if forms[0] is None:
            return str(value)
        return f"{value} {plural(value, *(form.strip() for form in forms))}"

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
