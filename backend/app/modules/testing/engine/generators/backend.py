import random

from app.modules.testing.engine.generators import generator
from app.modules.testing.engine.model import Generated

NAMES = ["items", "buffer", "acc", "bucket", "seen", "result"]


@generator("backend.python_mutable_default")
def python_mutable_default(rng: random.Random) -> Generated:
    """Мутабельный аргумент по умолчанию: список копится между вызовами."""
    name = rng.choice(NAMES)
    calls = rng.randint(2, 4)
    values = rng.sample(range(1, 10), calls)
    code_lines = [f"def add(x, {name}=[]):", f"    {name}.append(x)", f"    return {name}", ""]
    code_lines += [f"add({value})" for value in values[:-1]]
    code_lines.append(f"print(add({values[-1]}))")
    correct = str(values)
    wrong = {
        str([values[-1]]),
        str(values[:-1]),
        str(values[1:]),
        str(list(reversed(values))),
        "None",
    }
    wrong.discard(correct)
    return Generated(
        stem="Что выведет этот код?",
        code="\n".join(code_lines),
        code_language="python",
        correct=(correct,),
        wrong=tuple(sorted(wrong)),
    )


@generator("backend.binary_search_steps")
def binary_search_steps(rng: random.Random) -> Generated:
    """Сколько сравнений в худшем случае делает бинарный поиск: ⌊log2 n⌋ + 1."""
    power = rng.randint(10, 24)
    extra = rng.randint(0, 2 ** (power - 1))
    size = 2**power + extra
    steps = size.bit_length()
    return Generated(
        stem=(
            f"Массив из {size:,} отсортированных элементов. Сколько сравнений в худшем случае "
            "сделает бинарный поиск, чтобы найти элемент или убедиться, что его нет?"
        ).replace(",", " "),
        number=float(steps),
        tolerance=0,
    )
