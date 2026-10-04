"""Python-генераторы для заданий, которые нельзя описать декларативно (вывод кода, расчёты).

Генератор — функция (random.Random) -> Generated, регистрируется декоратором @generator("spec.name").
Верный ответ вычисляется детерминированно в Python, без exec кода кандидата.
"""

import importlib
import pkgutil
import random
from collections.abc import Callable

from app.modules.testing.engine.model import Generated

GeneratorFn = Callable[[random.Random], Generated]
REGISTRY: dict[str, GeneratorFn] = {}


def generator(name: str) -> Callable[[GeneratorFn], GeneratorFn]:
    def register(function: GeneratorFn) -> GeneratorFn:
        if name in REGISTRY:
            raise ValueError(f"генератор {name} зарегистрирован дважды")
        REGISTRY[name] = function
        return function

    return register


def load_all() -> dict[str, GeneratorFn]:
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
    return REGISTRY
