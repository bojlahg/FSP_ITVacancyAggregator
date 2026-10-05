"""Генераторы заданий frontend: вывод JS-кода, специфичность CSS, расчёты. Ответ считается в Python."""

import random
from collections import Counter, deque
from collections.abc import Iterable

from app.modules.testing.engine.generators import generator
from app.modules.testing.engine.model import Generated

LETTERS = list("ABCDEFGHKMNPRSTUVXYZ")


def _distinct_wrong(correct: str, candidates: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for text in candidates:
        if text != correct and text not in result:
            result.append(text)
    return tuple(result)


def _spaced(values: Iterable[object]) -> str:
    return " ".join(str(value) for value in values)


# --- CSS ---------------------------------------------------------------------------------------

TAGS = ["div", "ul", "li", "a", "nav", "section", "button", "span", "p", "header", "form", "article"]
CLASSES = ["card", "active", "menu", "item", "title", "btn", "primary", "list", "open", "large"]
IDS = ["main", "app", "sidebar", "header", "cart", "profile"]
ATTRS = ['[type="text"]', "[disabled]", '[data-role="tab"]', '[href^="http"]', '[aria-expanded="true"]']
PSEUDO_CLASSES = [":hover", ":focus", ":first-child", ":last-child", ":nth-child(2)"]
PSEUDO_ELEMENTS = ["::before", "::after"]
COMBINATORS = [" ", " > ", " + ", " ~ "]


def _fmt_spec(spec: tuple[int, int, int]) -> str:
    return f"({spec[0]}, {spec[1]}, {spec[2]})"


def _spec_wrong(correct: tuple[int, int, int], candidates: list[tuple[int, int, int]]) -> tuple[str, ...]:
    a, b, c = correct
    candidates = candidates + [(a + 1, b, c), (a, b + 1, c), (a, b, c + 1), (a, max(b - 1, 0), c + 1)]
    valid = [_fmt_spec(spec) for spec in candidates if min(spec) >= 0]
    return _distinct_wrong(_fmt_spec(correct), valid)


@generator("frontend.css_specificity_basic")
def css_specificity_basic(rng: random.Random) -> Generated:
    """Специфичность (a, b, c): id; классы, атрибуты, псевдоклассы; теги и псевдоэлементы."""
    a = b = c = 0
    attrs = pseudo_classes = pseudo_elements = 0
    ids = rng.sample(IDS, 2)
    id_budget = rng.randint(0, 2)
    compounds: list[str] = []
    for _ in range(rng.randint(2, 4)):
        part = ""
        if rng.random() < 0.7:
            part += rng.choice(TAGS)
            c += 1
        if id_budget and rng.random() < 0.5:
            part += "#" + ids[id_budget - 1]
            id_budget -= 1
            a += 1
        for name in rng.sample(CLASSES, rng.randint(0, 2)):
            part += "." + name
            b += 1
        if rng.random() < 0.3:
            part += rng.choice(ATTRS)
            b += 1
            attrs += 1
        if rng.random() < 0.3:
            part += rng.choice(PSEUDO_CLASSES)
            b += 1
            pseudo_classes += 1
        if not part:
            part = rng.choice(TAGS)
            c += 1
        compounds.append(part)
    if rng.random() < 0.4:
        compounds[-1] += rng.choice(PSEUDO_ELEMENTS)
        c += 1
        pseudo_elements = 1
    if attrs + pseudo_classes + pseudo_elements == 0:
        compounds[0] += rng.choice(PSEUDO_CLASSES)
        b += 1
        pseudo_classes = 1
    selector = compounds[0]
    for part in compounds[1:]:
        selector += rng.choice(COMBINATORS) + part
    correct = (a, b, c)
    wrong = _spec_wrong(
        correct,
        [
            (a, b - pseudo_classes, c + pseudo_classes),
            (a, b - attrs, c),
            (a, b + pseudo_elements, c - pseudo_elements),
            (0, a + b, c) if a else (a, b, c + len(compounds) - 1),
            (a, b, c - pseudo_elements),
        ],
    )
    return Generated(
        stem=(
            "Какова специфичность селектора? Формат ответа: (id; классы, атрибуты и псевдоклассы; "
            "теги и псевдоэлементы)."
        ),
        code=selector + " {\n  color: red;\n}",
        code_language="css",
        correct=(_fmt_spec(correct),),
        wrong=wrong,
    )


FUNCTIONAL_ARGS = [
    (".note", (0, 1, 0)),
    ("#promo", (1, 0, 0)),
    ("p", (0, 0, 1)),
    (".card.wide", (0, 2, 0)),
    ("ul li", (0, 0, 2)),
    ("#nav .link", (1, 1, 0)),
    ("[data-state]", (0, 1, 0)),
    ("a:hover", (0, 1, 1)),
]


def _add(x: tuple[int, int, int], y: tuple[int, int, int]) -> tuple[int, int, int]:
    return (x[0] + y[0], x[1] + y[1], x[2] + y[2])


@generator("frontend.css_specificity_functional")
def css_specificity_functional(rng: random.Random) -> Generated:
    """:is() и :not() берут специфичность самого специфичного аргумента, :where() — ноль."""
    base_tag, base_class = rng.choice(TAGS), rng.choice(CLASSES)
    base = (0, 1, 1)
    tail_tag = rng.choice(["a", "span", "li", "button", "p"])
    tail = (0, 0, 1)
    counting = rng.choice([":is", ":not"])
    while True:
        pairs = rng.sample(FUNCTIONAL_ARGS, 4)
        is_args, where_args = pairs[:2], pairs[2:]
        if is_args[0][1] != is_args[1][1]:
            break
    counted_max = max(spec for _, spec in is_args)
    counted_sum = _add(is_args[0][1], is_args[1][1])
    where_max = max(spec for _, spec in where_args)
    is_text = f"{counting}({', '.join(text for text, _ in is_args)})"
    where_text = f":where({', '.join(text for text, _ in where_args)})"
    if rng.random() < 0.5:
        selector = f"{base_tag}.{base_class} {is_text} > {tail_tag}{where_text}"
    else:
        selector = f"{base_tag}.{base_class}{where_text} {tail_tag}{is_text}"
    common = _add(base, tail)
    correct = _add(common, counted_max)
    wrong = _spec_wrong(
        correct,
        [
            _add(correct, where_max),
            _add(common, counted_sum),
            _add(common, (0, 1, 0)),
            _add(common, (0, 2, 0)),
            _add(_add(common, counted_sum), where_max),
            common,
        ],
    )
    return Generated(
        stem=(
            "Какова специфичность селектора? Формат ответа: (id; классы, атрибуты и псевдоклассы; "
            f"теги и псевдоэлементы). Учтите правила для {counting}() и :where()."
        ),
        code=selector + " {\n  color: red;\n}",
        code_language="css",
        correct=(_fmt_spec(correct),),
        wrong=wrong,
    )


@generator("frontend.box_model_width")
def box_model_width(rng: random.Random) -> Generated:
    """content-box: ширина + padding + border; border-box: width уже включает padding и border."""
    width = rng.randrange(200, 501, 10)
    padding = rng.randrange(8, 33, 2)
    border = rng.randint(1, 6)
    margin = rng.randrange(10, 41, 5)
    cls = rng.choice(["card", "panel", "banner", "tile"])
    mode = rng.choice(["content-box", "border-box"])
    code = (
        f".{cls} {{\n  box-sizing: {mode};\n  width: {width}px;\n  padding: {padding}px;\n"
        f"  border: {border}px solid #ccc;\n  margin: {margin}px;\n}}"
    )
    if mode == "content-box":
        question = "Какова ширина элемента от внешнего края левой рамки до внешнего края правой рамки (px)?"
        number = width + 2 * padding + 2 * border
    else:
        question = "Какова ширина области содержимого (content) элемента в пикселях?"
        number = width - 2 * padding - 2 * border
    return Generated(
        stem=f"Блок .{cls} отображается как блочный элемент. {question}",
        code=code,
        code_language="css",
        number=float(number),
    )


@generator("frontend.flex_grow_width")
def flex_grow_width(rng: random.Random) -> Generated:
    """Свободное место делится пропорционально flex-grow и прибавляется к flex-basis."""
    grows = [rng.randint(1, 3) for _ in range(3)]
    total = sum(grows)
    free = total * 10 * rng.randint(1, 6)
    bases = [rng.randrange(50, 201, 10) for _ in range(3)]
    width = sum(bases) + free
    names = ["a", "b", "c"]
    target = rng.randrange(3)
    rules = "\n".join(f".{names[i]} {{ flex: {grows[i]} 1 {bases[i]}px; }}" for i in range(3))
    code = (
        f".row {{ display: flex; width: {width}px; }}\n{rules}\n\n"
        '<div class="row">\n  <div class="a"></div>\n  <div class="b"></div>\n  <div class="c"></div>\n</div>'
    )
    return Generated(
        stem=(
            f"У дочерних элементов нет содержимого, padding, border и margin, gap не задан. "
            f"Какой будет ширина элемента .{names[target]} в пикселях?"
        ),
        code=code,
        code_language="css",
        number=float(bases[target] + free * grows[target] // total),
    )


SCRIPT_MODES = {
    "": "Загрузка и выполнение скрипта блокируют разбор HTML: парсер "
    "ждёт, пока скрипт загрузится и выполнится",
    "async": (
        "Скрипт загружается параллельно с разбором HTML и выполняется сразу после загрузки; "
        "порядок выполнения нескольких таких скриптов не гарантирован"
    ),
    "defer": (
        "Скрипт загружается параллельно с разбором HTML и выполняется после окончания разбора, "
        "до DOMContentLoaded, в порядке следования в документе"
    ),
    'type="module"': (
        "Модульный скрипт загружается параллельно и по умолчанию выполняется отложенно — "
        "после окончания разбора HTML, как скрипт с defer"
    ),
}
SCRIPT_WRONG = [
    "Скрипт загружается только после события load окна и ничего не блокирует",
    "Скрипт выполняется в отдельном потоке параллельно с основным потоком страницы",
]


@generator("frontend.script_loading")
def script_loading(rng: random.Random) -> Generated:
    mode = rng.choice(list(SCRIPT_MODES))
    name = rng.choice(["analytics", "app", "vendor", "widget", "chat"])
    attr = f" {mode}" if mode else ""
    equivalent = {"defer": 'type="module"', 'type="module"': "defer"}.get(mode)
    wrong = [text for key, text in SCRIPT_MODES.items() if key not in {mode, equivalent}] + SCRIPT_WRONG
    return Generated(
        stem="Скрипт подключён в <head> обычной HTML-страницы. Как браузер его загрузит и выполнит?",
        code=f'<script{attr} src="/js/{name}.js"></script>',
        code_language="html",
        correct=(SCRIPT_MODES[mode],),
        wrong=tuple(wrong),
    )


# --- JavaScript --------------------------------------------------------------------------------


def _run_event_loop(statements: list[tuple[str, list[str]]]) -> list[str]:
    """Модель event loop: синхронный код, затем очередь микрозадач до опустошения, затем таймеры.

    Цепочка микрозадач (then().then(), await подряд) ставит следующий шаг в очередь, только когда
    выполнился предыдущий.
    """
    output: list[str] = []
    micro: deque[list[str]] = deque()
    macro: list[str] = []
    for kind, values in statements:
        if kind == "sync":
            output.append(values[0])
        elif kind == "timeout":
            macro.append(values[0])
        elif kind in {"then", "micro"}:
            micro.append(list(values))
        elif kind == "async":
            output.append(values[0])
            micro.append(list(values[1:]))
    while micro:
        chain = micro.popleft()
        output.append(chain[0])
        if len(chain) > 1:
            micro.append(chain[1:])
    return output + macro


def _js_line(kind: str, values: list[str]) -> str:
    if kind == "sync":
        return f"console.log('{values[0]}');"
    if kind == "timeout":
        return f"setTimeout(() => console.log('{values[0]}'), 0);"
    if kind == "micro":
        return f"queueMicrotask(() => console.log('{values[0]}'));"
    if kind == "then":
        chain = "".join(f"\n  .then(() => console.log('{value}'))" for value in values)
        return f"Promise.resolve(){chain};"
    return "run();"


def _fill_permutations(rng: random.Random, correct: list[str], wrong: list[str], needed: int = 4) -> None:
    attempts = 0
    while len(set(wrong) - {_spaced(correct)}) < needed and attempts < 50:
        attempts += 1
        candidate = correct[:]
        rng.shuffle(candidate)
        wrong.append(_spaced(candidate))


@generator("frontend.js_event_loop_basic")
def js_event_loop_basic(rng: random.Random) -> Generated:
    """Синхронный код → микрозадачи (then, queueMicrotask) в порядке постановки → setTimeout."""
    kinds = ["timeout"] * rng.randint(1, 2) + ["then"] * rng.randint(1, 2) + ["micro"] * rng.randint(0, 1)
    kinds += ["sync"] * rng.randint(0, 1)
    rng.shuffle(kinds)
    kinds = ["sync", *kinds, "sync"]
    labels = rng.sample(LETTERS, len(kinds))
    statements = [(kind, [label]) for kind, label in zip(kinds, labels, strict=True)]
    correct = _run_event_loop(statements)
    sync = [label for kind, label in zip(kinds, labels, strict=True) if kind == "sync"]
    micro = [label for kind, label in zip(kinds, labels, strict=True) if kind in {"then", "micro"}]
    timers = [label for kind, label in zip(kinds, labels, strict=True) if kind == "timeout"]
    wrong = [
        _spaced(labels),
        _spaced(sync + timers + micro),
        _spaced(micro + sync + timers),
        _spaced(sync + micro[::-1] + timers),
        _spaced(sync + timers[::-1] + micro[::-1]),
    ]
    _fill_permutations(rng, correct, wrong)
    return Generated(
        stem="В каком порядке будут выведены значения? (через пробел)",
        code="\n".join(_js_line(kind, [label]) for kind, label in zip(kinds, labels, strict=True)),
        code_language="javascript",
        correct=(_spaced(correct),),
        wrong=_distinct_wrong(_spaced(correct), wrong),
    )


@generator("frontend.js_event_loop_async")
def js_event_loop_async(rng: random.Random) -> Generated:
    """async/await и цепочки then: каждый шаг цепочки — отдельная микрозадача."""
    two_awaits = rng.random() < 0.5
    labels = iter(rng.sample(LETTERS, 9))
    first, last = next(labels), next(labels)
    run_values = [next(labels), next(labels)] + ([next(labels)] if two_awaits else [])
    then_values = [next(labels), next(labels)]
    timer = next(labels)
    middle = [("timeout", [timer]), ("then", then_values), ("async", run_values)]
    rng.shuffle(middle)
    statements = [("sync", [first]), *middle, ("sync", [last])]
    correct = _run_event_loop(statements)

    run_body = [f"  console.log('{run_values[0]}');", "  await null;", f"  console.log('{run_values[1]}');"]
    if two_awaits:
        run_body += ["  await null;", f"  console.log('{run_values[2]}');"]
    code = ["async function run() {", *run_body, "}", ""]
    code += [_js_line(kind, values) for kind, values in statements]

    # correct = [first, run0, last, *микрозадачи, timer]: таймер — единственная макрозадача
    micro_order = correct[3:-1]
    chains_whole = [first, run_values[0], last]
    for kind, values in middle:
        if kind == "async":
            chains_whole += values[1:]
        elif kind == "then":
            chains_whole += values
    chains_whole.append(timer)
    sync_async = [first, *run_values, last] + [v for v in micro_order if v not in run_values] + [timer]
    timers_first = [first, run_values[0], last, timer, *micro_order]
    wrong = [_spaced(chains_whole), _spaced(sync_async), _spaced(timers_first)]
    _fill_permutations(rng, correct, wrong)
    return Generated(
        stem="В каком порядке будут выведены значения? (через пробел)",
        code="\n".join(code),
        code_language="javascript",
        correct=(_spaced(correct),),
        wrong=_distinct_wrong(_spaced(correct), wrong),
    )


LOOSE_TRUE = [
    "null == undefined",
    "0 == ''",
    "'1' == 1",
    "'0' == false",
    "[] == false",
    "[1] == 1",
    "[] == ![]",
    "null >= 0",
    "true == 1",
    "[2] == '2'",
]
LOOSE_FALSE = [
    "null == 0",
    "undefined == 0",
    "NaN == NaN",
    "null == false",
    "undefined == false",
    "'true' == true",
    "[] == []",
    "'2' == true",
    "'0' == ''",
    "undefined >= 0",
]


@generator("frontend.js_loose_equality")
def js_loose_equality(rng: random.Random) -> Generated:
    """Нестрогое сравнение: null == только undefined, объекты приводятся к примитиву, NaN ≠ NaN."""
    return Generated(
        stem="Какие из выражений JavaScript вернут true? Выберите все верные.",
        correct=tuple(rng.sample(LOOSE_TRUE, 4)),
        wrong=tuple(rng.sample(LOOSE_FALSE, 4)),
    )


@generator("frontend.js_closure_loop")
def js_closure_loop(rng: random.Random) -> Generated:
    """var — одна переменная на весь цикл; let — новая привязка на каждую итерацию."""
    decl = rng.choice(["var", "let"])
    start = rng.randint(0, 3)
    step = rng.choice([1, 2, 3])
    count = rng.randint(3, 4)
    values = [start + step * i for i in range(count)]
    end = values[-1] + 1
    final = start + step * count
    name = rng.choice(["i", "n", "k", "idx"])
    increment = f"{name}++" if step == 1 else f"{name} += {step}"
    code = (
        f"for ({decl} {name} = {start}; {name} < {end}; {increment}) {{\n"
        f"  setTimeout(() => console.log({name}), 0);\n}}"
    )
    var_answer = _spaced([final] * count)
    let_answer = _spaced(values)
    correct = var_answer if decl == "var" else let_answer
    wrong = [
        let_answer if decl == "var" else var_answer,
        _spaced([values[-1]] * count),
        _spaced([end] * count),
        _spaced(v + step for v in values),
        _spaced(["undefined"] * count),
    ]
    return Generated(
        stem="Что будет выведено в консоль? (значения через пробел, в порядке вывода)",
        code=code,
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("frontend.js_array_chain")
def js_array_chain(rng: random.Random) -> Generated:
    divisor = rng.choice([2, 3])
    factor = rng.choice([2, 3, 10])
    init = rng.choice([0, 5, 10, 100])
    while True:
        numbers = [rng.randint(1, 20) for _ in range(rng.randint(5, 7))]
        picked = [x for x in numbers if x % divisor == 0]
        if 2 <= len(picked) < len(numbers):
            break
    name = rng.choice(["nums", "values", "items", "scores"])
    correct = init + sum(x * factor for x in picked)
    wrong = [
        str(sum(x * factor for x in picked)),
        str(init + sum(picked)),
        str(init + sum(x * factor for x in numbers)),
        str(init + sum(x * factor for x in numbers if (x * factor) % divisor == 0)),
        str(init + len(picked) * factor),
        str(correct + factor),
    ]
    code = (
        f"const {name} = [{', '.join(map(str, numbers))}];\n"
        f"const result = {name}\n"
        f"  .filter(x => x % {divisor} === 0)\n"
        f"  .map(x => x * {factor})\n"
        f"  .reduce((acc, x) => acc + x, {init});\n"
        "console.log(result);"
    )
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="javascript",
        correct=(str(correct),),
        wrong=_distinct_wrong(str(correct), wrong),
    )


@generator("frontend.js_default_sort")
def js_default_sort(rng: random.Random) -> Generated:
    """sort() без компаратора сравнивает элементы как строки."""
    while True:
        numbers = rng.sample(list(range(2, 10)), 2) + rng.sample(list(range(10, 100)), 2)
        numbers += rng.sample(list(range(100, 400)), 1)
        rng.shuffle(numbers)
        lexical = sorted(numbers, key=str)
        if lexical != sorted(numbers):
            break
    name = rng.choice(["prices", "ids", "ages", "ranks"])
    join = lambda seq: ", ".join(map(str, seq))  # noqa: E731
    correct = join(lexical)
    wrong = [join(sorted(numbers)), join(sorted(numbers, reverse=True)), join(numbers), join(lexical[::-1])]
    return Generated(
        stem="Что выведет этот код?",
        code=f"const {name} = [{join(numbers)}];\nconsole.log({name}.sort().join(', '));",
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


TYPEOF_CASES = [
    ("null", "object", ["null"]),
    ("NaN", "number", ["NaN"]),
    ("[]", "object", ["array"]),
    ("class {}", "function", ["class"]),
    ("Symbol('id')", "symbol", ["string"]),
    ("10n", "bigint", ["number"]),
    ("new Number(5)", "object", ["number"]),
    ("undeclaredVariable", "undefined", ["ReferenceError"]),
]


@generator("frontend.js_typeof")
def js_typeof(rng: random.Random) -> Generated:
    (expr1, right1, wrongs1), (expr2, right2, wrongs2) = rng.sample(TYPEOF_CASES, 2)
    if right1 == right2:
        (expr2, right2, wrongs2) = next(case for case in TYPEOF_CASES if case[1] != right1)

    def option(x: str, y: str) -> str:
        return "Ошибка ReferenceError" if "ReferenceError" in {x, y} else f"{x} {y}"

    correct = option(right1, right2)
    wrong = [option(wrongs1[0], right2), option(right1, wrongs2[0]), option(wrongs1[0], wrongs2[0])]
    wrong += [option(right2, right1), option(right1, right1), option(right2, right2), "object object"]
    comment = ""
    if "undeclaredVariable" in {expr1, expr2}:
        comment = "// переменная undeclaredVariable нигде не объявлена\n"
    return Generated(
        stem="Что выведет этот код?",
        code=f"{comment}console.log(typeof {expr1}, typeof {expr2});",
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


PEOPLE = ["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор"]


@generator("frontend.js_this_binding")
def js_this_binding(rng: random.Random) -> Generated:
    """this определяется способом вызова; bind фиксирует this навсегда; стрелка игнорирует call."""
    first, second = rng.sample(PEOPLE, 2)
    obj1, obj2 = rng.sample(["user", "admin", "author", "owner", "guest"], 2)
    method = rng.choice(["getName", "whoAmI", "label"])
    calls = {
        "fn()": "Ошибка TypeError",
        f"fn.call({obj2})": second,
        f"fn.bind({obj2}).call({obj1})": second,
        f"wrapper.call({obj2})": first,
    }
    call = rng.choice(list(calls))
    code = (
        "'use strict';\n"
        f"const {obj1} = {{ name: '{first}', {method}() {{ return this.name; }} }};\n"
        f"const {obj2} = {{ name: '{second}' }};\n"
        f"const fn = {obj1}.{method};\n"
        f"const wrapper = () => {obj1}.{method}();\n"
        f"console.log({call});"
    )
    correct = calls[call]
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, [first, second, "undefined", "Ошибка TypeError"]),
    )


TS_FIELDS = [
    ("id", "number"),
    ("name", "string"),
    ("email", "string"),
    ("age", "number"),
    ("active", "boolean"),
    ("role", "string"),
    ("createdAt", "Date"),
    ("tags", "string[]"),
]


def _ts_object(fields: list[tuple[str, str, bool]]) -> str:
    return (
        "{ " + "; ".join(f"{name}{'?' if optional else ''}: {kind}" for name, kind, optional in fields) + " }"
    )


@generator("frontend.ts_utility_type")
def ts_utility_type(rng: random.Random) -> Generated:
    interface = rng.choice(["User", "Product", "Order", "Account"])
    picked = rng.sample(TS_FIELDS, 4)
    optional_index = rng.randrange(4)
    fields = [(name, kind, i == optional_index) for i, (name, kind) in enumerate(picked)]
    other_index = rng.choice([i for i in range(4) if i != optional_index])
    keys = sorted({optional_index, other_index})
    key_names = [fields[i][0] for i in keys]
    selected = [fields[i] for i in keys]
    rest = [field for i, field in enumerate(fields) if i not in keys]
    results = {
        "Pick": _ts_object(selected),
        "Omit": _ts_object(rest),
        "Partial<Pick": _ts_object([(n, k, True) for n, k, _ in selected]),
        "Required<Pick": _ts_object([(n, k, False) for n, k, _ in selected]),
    }
    op = rng.choice(list(results))
    union = " | ".join(f"'{name}'" for name in key_names)
    expression = {
        "Pick": f"Pick<{interface}, {union}>",
        "Omit": f"Omit<{interface}, {union}>",
        "Partial<Pick": f"Partial<Pick<{interface}, {union}>>",
        "Required<Pick": f"Required<Pick<{interface}, {union}>>",
    }[op]
    body = "\n".join(f"  {name}{'?' if optional else ''}: {kind};" for name, kind, optional in fields)
    correct = results[op]
    wrong = [text for key, text in results.items() if key != op]
    wrong.append(_ts_object([(n, k, True) for n, k, _ in fields]))
    wrong.append(_ts_object([(n, k, False) for n, k, _ in rest]))
    return Generated(
        stem="Какому типу эквивалентен Result?",
        code=f"interface {interface} {{\n{body}\n}}\n\ntype Result = {expression};",
        code_language="typescript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("frontend.js_prototype_shadowing")
def js_prototype_shadowing(rng: random.Random) -> Generated:
    """this.x += … читает свойство из прототипа, а записывает собственное свойство объекта."""
    prop = rng.choice(["count", "score", "level", "total"])
    start = rng.randint(1, 9)
    step = rng.randint(2, 5)
    calls = rng.randint(2, 3)
    base_call = rng.random() < 0.5
    lines = [
        f"const base = {{ {prop}: {start}, inc() {{ this.{prop} += {step}; }} }};",
        "const child = Object.create(base);",
    ]
    lines += ["child.inc();"] * calls
    if base_call:
        lines.append("base.inc();")
    lines.append(f"console.log(base.{prop}, child.{prop});")
    base_value = start + (step if base_call else 0)
    child_value = start + step * calls
    correct = f"{base_value} {child_value}"
    shared = start + step * (calls + (1 if base_call else 0))
    wrong = [
        f"{shared} {shared}",
        f"{start} {start}",
        f"{child_value} {child_value}",
        f"{base_value} {base_value}",
        f"{child_value} {base_value}",
        f"{start} {child_value + (step if base_call else 0)}",
    ]
    return Generated(
        stem="Что выведет этот код?",
        code="\n".join(lines),
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


# --- HTTP --------------------------------------------------------------------------------------

CORS_SIMPLE = [
    "fetch(url)",
    "fetch(url, { method: 'HEAD' })",
    "fetch(url, { method: 'POST', body: formData })  // formData — объект FormData",
    "fetch(url, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text })",
    "fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })",
    "fetch(url, { headers: { 'Accept-Language': 'ru' } })",
    "fetch(url, { credentials: 'include' })",
]
CORS_PREFLIGHT = [
    "fetch(url, { method: 'PUT', body })",
    "fetch(url, { method: 'DELETE' })",
    "fetch(url, { method: 'PATCH', body })",
    "fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })",
    "fetch(url, { headers: { Authorization: `Bearer ${token}` } })",
    "fetch(url, { headers: { 'X-Request-Id': id } })",
]


@generator("frontend.cors_preflight")
def cors_preflight(rng: random.Random) -> Generated:
    """Preflight не нужен только для GET/HEAD/POST с safelisted-заголовками и простым Content-Type."""
    site = rng.choice(["shop.example", "app.example", "portal.example"])
    api = rng.choice(["api.partner.example", "data.other.example", "backend.service.example"])
    path = rng.choice(["orders", "profile", "items", "reports"])
    return Generated(
        stem=(
            f"Страница https://{site} выполняет запросы к const url = 'https://{api}/{path}'. "
            "Какие из запросов браузер предварит preflight-запросом OPTIONS? Выберите все верные."
        ),
        correct=tuple(rng.sample(CORS_PREFLIGHT, 4)),
        wrong=tuple(rng.sample(CORS_SIMPLE, 4)),
    )


HTTP_SCENARIOS = [
    ("Запрос пришёл без токена или с истёкшим токеном", "401 Unauthorized"),
    ("Пользователь аутентифицирован, но у его роли нет прав на это действие", "403 Forbidden"),
    ("POST-запрос успешно создал новый ресурс", "201 Created"),
    ("DELETE выполнен успешно, тело ответа не возвращается", "204 No Content"),
    ("Клиент прислал If-None-Match, и ETag ресурса не изменился", "304 Not Modified"),
    ("Клиент превысил лимит запросов в минуту", "429 Too Many Requests"),
    ("Запрошен ресурс по идентификатору, которого не существует", "404 Not Found"),
]


@generator("frontend.http_status_scenario")
def http_status_scenario(rng: random.Random) -> Generated:
    situation, code = rng.choice(HTTP_SCENARIOS)
    resource = rng.choice(["/api/orders", "/api/profile", "/api/cart", "/api/projects"])
    stem = rng.choice(
        [
            f"Фронтенд обращается к {resource}. Ситуация: {situation}. Какой код ответа корректен?",
            f"{situation} (эндпоинт {resource}). Какой HTTP-статус должен вернуть сервер?",
        ]
    )
    return Generated(
        stem=stem,
        correct=(code,),
        wrong=tuple(other for _, other in HTTP_SCENARIOS if other != code) + ("200 OK",),
    )


# --- Производительность ------------------------------------------------------------------------

VITALS = {
    "LCP": "время отрисовки самого крупного видимого элемента контента (изображения или блока текста)",
    "CLS": "суммарные неожиданные сдвиги макета страницы",
    "INP": "задержку от действия пользователя (клик, нажатие клавиши) до отрисовки следующего кадра",
}
VITALS_WRONG = ["FCP", "TTFB", "TBT", "FID"]


@generator("frontend.web_vitals_metric")
def web_vitals_metric(rng: random.Random) -> Generated:
    metric = rng.choice(list(VITALS))
    page = rng.choice(["главной страницы", "карточки товара", "страницы статьи", "ленты новостей"])
    stem = rng.choice(
        [
            f"Какая метрика Core Web Vitals для {page} измеряет {VITALS[metric]}?",
            f"Команда хочет отслеживать {VITALS[metric]} для {page}. Какую метрику Core Web Vitals смотреть?",
        ]
    )
    wrong = [other for other in VITALS if other != metric] + VITALS_WRONG
    return Generated(stem=stem, correct=(metric,), wrong=tuple(wrong))


DEBOUNCE_SCENARIOS = [
    (
        "Поле поиска должно отправлять запрос, только когда пользователь перестал печатать на {ms} мс",
        "debounce",
    ),
    ("Автосохранение черновика: сохранять через {ms} мс после последнего изменения текста", "debounce"),
    (
        "Пересчитать раскладку один раз, когда пользователь закончил менять размер окна (пауза {ms} мс)",
        "debounce",
    ),
    (
        "Во время прокрутки проверять, не пора ли подгрузить следующую страницу, не чаще раза в {ms} мс",
        "throttle",
    ),
    ("Отправлять координаты курсора в аналитику во время движения мыши не чаще раза в {ms} мс", "throttle"),
    ("Обновлять индикатор прогресса чтения при скролле не чаще раза в {ms} мс", "throttle"),
]


@generator("frontend.debounce_or_throttle")
def debounce_or_throttle(rng: random.Random) -> Generated:
    text, answer = rng.choice(DEBOUNCE_SCENARIOS)
    ms = rng.choice([100, 200, 300, 500])
    other = "throttle" if answer == "debounce" else "debounce"
    return Generated(
        stem=f"{text.format(ms=ms)}. Какую технику применить?",
        correct=(answer,),
        wrong=(other, "мемоизация (memoize)", "ленивая загрузка (lazy loading)", "вынос в Web Worker"),
    )


@generator("frontend.debounce_calls")
def debounce_calls(rng: random.Random) -> Generated:
    """Trailing debounce срабатывает один раз на каждую серию событий с паузами короче ожидания."""
    wait = rng.choice([200, 300, 500])
    bursts = rng.randint(2, 4)
    times: list[int] = []
    now = 0
    for burst in range(bursts):
        if burst:
            now += rng.randrange(wait + 60, wait + 401, 10)
        for event in range(rng.randint(2, 4)):
            if event:
                now += rng.randrange(40, wait - 50, 10)
            times.append(now)
    fn = rng.choice(["search", "save", "validate"])
    return Generated(
        stem=(
            f"Обработчик ввода обёрнут в debounce({fn}, {wait}): {fn} вызывается через {wait} мс после "
            f"последнего события, если за это время новых событий не было. События ввода приходят в моменты "
            f"(мс): {', '.join(map(str, times))}. Сколько раз будет вызвана {fn}?"
        ),
        number=float(bursts),
    )


@generator("frontend.total_blocking_time")
def total_blocking_time(rng: random.Random) -> Generated:
    """TBT = сумма (длительность − 50 мс) по задачам длиннее 50 мс между FCP и TTI."""
    durations = []
    for _ in range(rng.randint(6, 8)):
        duration = rng.randrange(20, 301, 5)
        if duration == 50:
            duration = 55
        durations.append(duration)
    if all(d <= 50 for d in durations):
        durations[0] = 120
    if all(d > 50 for d in durations):
        durations[-1] = 35
    tbt = sum(d - 50 for d in durations if d > 50)
    return Generated(
        stem=(
            "Между FCP и TTI в главном потоке выполнились задачи длительностью (мс): "
            f"{', '.join(map(str, durations))}. Чему равен Total Blocking Time (мс)?"
        ),
        number=float(tbt),
    )


# --- Тестирование и архитектура ----------------------------------------------------------------


RTL_TEXTS = [
    "Ошибка оплаты",
    "Заказ оформлен",
    "Нет результатов",
    "Профиль сохранён",
    "Сессия истекла",
    "Файл загружен",
    "Неверный пароль",
    "Товар добавлен в корзину",
    "Письмо отправлено",
    "Доступ запрещён",
    "Изменения сохранены",
    "Список пуст",
]


@generator("frontend.rtl_query_choice")
def rtl_query_choice(rng: random.Random) -> Generated:
    """getBy бросает ошибку, queryBy возвращает null, findBy ждёт появления (Promise)."""
    text = rng.choice(RTL_TEXTS)
    comp = rng.choice(
        ["CheckoutForm", "LoginForm", "ProfilePage", "SearchResults", "UploadDialog", "CartPanel"]
    )
    if rng.random() < 0.5:
        stem = rng.choice(
            [
                f"Нужно проверить, что после рендера <{comp} /> текст «{text}» НЕ отображается. "
                "Какой запрос подходит?",
                f"Тест на React Testing Library: после render(<{comp} />) сообщения «{text}» быть не должно. "
                "Какая проверка корректна?",
            ]
        )
        correct = f"expect(screen.queryByText('{text}')).not.toBeInTheDocument()"
        wrong = [
            f"expect(screen.getByText('{text}')).not.toBeInTheDocument()",
            f"expect(await screen.findByText('{text}')).not.toBeInTheDocument()",
            f"expect(screen.getAllByText('{text}')).toHaveLength(0)",
            f"expect(screen.queryByText('{text}')).toBeInTheDocument()",
        ]
    else:
        stem = rng.choice(
            [
                f"В <{comp} /> текст «{text}» появляется после асинхронного запроса, который замокан. "
                "Каким запросом дождаться его появления?",
                f"После render(<{comp} />) компонент загружает данные (запрос замокан) и затем показывает "
                f"«{text}». Какая проверка корректно дождётся текста?",
            ]
        )
        correct = f"expect(await screen.findByText('{text}')).toBeInTheDocument()"
        wrong = [
            f"expect(screen.getByText('{text}')).toBeInTheDocument()",
            f"expect(screen.queryByText('{text}')).toBeInTheDocument()",
            f"expect(screen.queryAllByText('{text}')).not.toHaveLength(0)",
            f"await waitFor(() => screen.queryByText('{text}'))",
        ]
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


STATE_SCENARIOS = [
    ("Фильтры каталога {x} должны сохраняться при перезагрузке, и ими можно поделиться ссылкой", "url"),
    ("Номер страницы и сортировка таблицы {x} должны восстанавливаться по кнопке «Назад» браузера", "url"),
    ("Выбранная вкладка на странице {x} должна открываться у коллеги, которому отправили ссылку", "url"),
    (
        "Список {x} с сервера нужен нескольким экранам; нужны кэш, фоновое обновление и повтор запроса",
        "server",
    ),
    ("Карточка из списка {x} загружается с сервера, после редактирования её нужно инвалидировать", "server"),
    ("Данные {x} с API, которые должны обновляться при возврате фокуса на вкладку", "server"),
    ("Флаг «открыт ли выпадающий список» в фильтре {x} нужен только одному компоненту", "local"),
    ("Значение поля поиска {x} внутри одного компонента до отправки формы", "local"),
    ("Признак «показать пароль» в форме входа, который нужен только самому полю пароля", "local"),
    (
        "Содержимое черновика {x} редактируется на клиенте, до отправки на сервер не сохраняется и нужно "
        "шапке и нескольким далёким друг от друга страницам",
        "global",
    ),
    (
        "Открыто ли боковое меню: им управляют кнопка в шапке и сам сайдбар со списком {x}, они в разных "
        "ветках дерева",
        "global",
    ),
]
STATE_OPTIONS = {
    "url": "В URL (query-параметры)",
    "server": "В кэше серверного состояния (TanStack Query, RTK Query, SWR)",
    "local": "В локальном состоянии компонента (useState)",
    "global": "В глобальном клиентском состоянии (Context или стор: Redux, Zustand, Pinia)",
}
STATE_WRONG = [
    "В глобальной переменной window",
    "В cookie, чтобы сервер всегда знал значение",
    "В localStorage с чтением при каждом рендере",
]
STATE_ENTITIES = ["заказов", "товаров", "сотрудников", "задач", "вакансий", "документов"]


@generator("frontend.state_placement")
def state_placement(rng: random.Random) -> Generated:
    text, answer = rng.choice(STATE_SCENARIOS)
    question = rng.choice(
        ["Где лучше всего хранить это состояние?", "Где разумнее всего держать это состояние?"]
    )
    wrong = [label for key, label in STATE_OPTIONS.items() if key != answer] + STATE_WRONG
    return Generated(
        stem=f"{text.format(x=rng.choice(STATE_ENTITIES))}. {question}",
        correct=(STATE_OPTIONS[answer],),
        wrong=tuple(wrong),
    )


# --- Алгоритмы ---------------------------------------------------------------------------------


@generator("frontend.dom_document_order")
def dom_document_order(rng: random.Random) -> Generated:
    """querySelectorAll возвращает элементы в порядке документа — обход дерева в глубину (preorder)."""
    labels = iter(rng.sample(LETTERS, 9))
    tree: list[tuple[str, list[str]]] = []
    child_count = rng.randint(2, 3)
    deep = rng.randrange(child_count - 1)
    for index in range(child_count):
        grandchildren = rng.randint(1, 2) if index == deep else rng.randint(0, 2)
        tree.append((next(labels), [next(labels) for _ in range(grandchildren)]))
    preorder = [x for parent, kids in tree for x in [parent, *kids]]
    bfs = [parent for parent, _ in tree] + [kid for _, kids in tree for kid in kids]
    postorder = [x for parent, kids in tree for x in [*kids, parent]]
    reversed_children = [x for parent, kids in tree for x in [parent, *kids[::-1]]][::-1]
    lines = ['<div id="root">']
    for parent, kids in tree:
        if kids:
            lines.append(f'  <div class="item" data-id="{parent}">')
            lines += [f'    <span class="item" data-id="{kid}"></span>' for kid in kids]
            lines.append("  </div>")
        else:
            lines.append(f'  <div class="item" data-id="{parent}"></div>')
    lines.append("</div>")
    lines.append("<script>")
    lines.append("  const ids = [...document.querySelectorAll('#root .item')].map(el => el.dataset.id);")
    lines.append("  console.log(ids.join(' '));")
    lines.append("</script>")
    correct = _spaced(preorder)
    wrong = [_spaced(bfs), _spaced(postorder), _spaced(reversed_children), _spaced(preorder[::-1])]
    return Generated(
        stem="Что выведет скрипт?",
        code="\n".join(lines),
        code_language="html",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


BRACKETS = {"(": ")", "[": "]", "{": "}"}


@generator("frontend.bracket_depth")
def bracket_depth(rng: random.Random) -> Generated:
    """Максимальный размер стека при проверке скобок = максимальная глубина вложенности."""
    while True:
        pairs = rng.randint(6, 8)
        stack: list[str] = []
        text = ""
        opened = 0
        deepest = 0
        while opened < pairs or stack:
            if stack and (opened == pairs or rng.random() < 0.45):
                text += BRACKETS[stack.pop()]
            else:
                bracket = rng.choice(list(BRACKETS))
                stack.append(bracket)
                text += bracket
                opened += 1
                deepest = max(deepest, len(stack))
        if 3 <= deepest <= 5:
            break
    return Generated(
        stem=(
            "Функция проверки скобок проходит строку слева направо: открывающую скобку кладёт в стек, "
            "на закрывающей снимает верхний элемент. Какого максимального размера достигнет стек?"
        ),
        code=f"isBalanced('{text}')",
        code_language="javascript",
        number=float(deepest),
    )


LOOP_VARIANTS = [
    (
        "for (let {i} = 1; {i} < n; {i} *= {g}) {{\n  for (let {j} = 0; {j} < {i}; {j}++) {{"
        "\n    work();\n  }}\n}}",
        "O(n)",
    ),
    (
        "for (let {i} = n; {i} > 0; {i} = Math.floor({i} / {g})) {{\n"
        "  for (let {j} = 0; {j} < {i}; {j}++) {{\n    work();\n  }}\n}}",
        "O(n)",
    ),
    (
        "for (let {i} = 1; {i} < n; {i} *= {g}) {{\n  for (let {j} = 0; {j} < n; {j}++) {{"
        "\n    work();\n  }}\n}}",
        "O(n log n)",
    ),
    (
        "for (let {i} = 0; {i} < n; {i}++) {{\n  for (let {j} = 1; {j} < n; {j} *= {g}) {{"
        "\n    work();\n  }}\n}}",
        "O(n log n)",
    ),
    (
        "for (let {i} = n; {i} > 1; {i} = Math.floor({i} / {g})) {{\n"
        "  for (let {j} = 0; {j} < n; {j}++) {{\n    work();\n  }}\n}}",
        "O(n log n)",
    ),
]
LOOP_NAMES = [("i", "j"), ("k", "m"), ("a", "b"), ("step", "pos"), ("size", "x"), ("len", "t"), ("p", "q")]


@generator("frontend.loop_complexity")
def loop_complexity(rng: random.Random) -> Generated:
    """Вложенные циклы с геометрическим шагом: сумма 1 + 2 + 4 + … < 2n даёт O(n), а не O(n log n)."""
    template, answer = rng.choice(LOOP_VARIANTS)
    i, j = rng.choice(LOOP_NAMES)
    stem = rng.choice(
        [
            "Какова асимптотическая сложность фрагмента по числу вызовов work() (work — O(1))?",
            "Сколько раз асимптотически вызовется work() в зависимости от n? Сама work() — O(1).",
        ]
    )
    return Generated(
        stem=stem,
        code=template.format(i=i, j=j, g=rng.choice([2, 3])),
        code_language="javascript",
        correct=(answer,),
        wrong=tuple(x for x in ["O(n)", "O(n log n)", "O(n²)", "O(log n)", "O(log² n)"] if x != answer),
    )


@generator("frontend.fib_calls")
def fib_calls(rng: random.Random) -> Generated:
    """Число вызовов наивной рекурсии: C(n) = 1 + C(n−1) + C(n−2), C(0) = C(1) = 1."""
    n = rng.randint(5, 7)
    calls = [1, 1]
    for k in range(2, n + 1):
        calls.append(1 + calls[k - 1] + calls[k - 2])
    name = rng.choice(["fib", "f", "calc", "seq", "rec", "fibo", "count", "solve"])
    counter = rng.choice(["calls", "counter", "hits", "invocations"])
    base = rng.choice(["n < 2", "n <= 1"])
    code = (
        f"let {counter} = 0;\n"
        f"function {name}(n) {{\n  {counter}++;\n  if ({base}) return n;"
        f"\n  return {name}(n - 1) + {name}(n - 2);\n}}\n"
        f"{name}({n});\nconsole.log({counter});"
    )
    stem = rng.choice(
        ["Что выведет этот код?", f"Сколько раз будет вызвана функция {name} (что выведет код)?"]
    )
    return Generated(stem=stem, code=code, code_language="javascript", number=float(calls[n]))


# --- React, Vue, Angular -----------------------------------------------------------------------


@generator("frontend.react_state_batching")
def react_state_batching(rng: random.Random) -> Generated:
    """setX(value) берёт значение из замыкания рендера, setX(fn) применяется к результату очереди."""
    start = rng.randint(0, 5)
    while True:
        ops = [(rng.choice(["direct", "updater"]), rng.randint(1, 4)) for _ in range(rng.randint(3, 4))]
        kinds = [kind for kind, _ in ops]
        if "direct" in kinds and kinds[-1] == "updater" and kinds.count("updater") >= 1:
            break
    value = start
    lines = []
    for kind, amount in ops:
        if kind == "direct":
            value = start + amount
            lines.append(f"    setCount(count + {amount});")
        else:
            value += amount
            lines.append(f"    setCount(c => c + {amount});")
    naive = start + sum(amount for _, amount in ops)
    updaters_only = start + sum(amount for kind, amount in ops if kind == "updater")
    last_direct = start + [amount for kind, amount in ops if kind == "direct"][-1]
    code = (
        "function Counter() {\n"
        f"  const [count, setCount] = useState({start});\n"
        "  function handleClick() {\n" + "\n".join(lines) + "\n  }\n"
        "  return <button onClick={handleClick}>{count}</button>;\n}"
    )
    correct = str(value)
    wrong = [
        str(naive),
        str(updaters_only),
        str(last_direct),
        str(start + ops[-1][1]),
        str(value + 1),
        str(start),
    ]
    return Generated(
        stem="Какое значение count отобразится после одного клика по кнопке?",
        code=code,
        code_language="jsx",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("frontend.react_effect_deps")
def react_effect_deps(rng: random.Random) -> Generated:
    first, second = rng.sample(["userId", "page", "query", "filter", "locale"], 2)
    effect = rng.choice(["loadData()", "subscribe()", "trackView()"])
    variants = {
        "": "После каждого рендера компонента",
        "[]": "Один раз после монтирования; cleanup — при размонтировании",
        f"[{first}]": f"После монтирования и после рендеров, в которых изменилось значение {first}",
        f"[{first}, {second}]": (
            f"После монтирования и после рендеров, в которых изменилось {first} или {second}"
        ),
    }
    deps = rng.choice(list(variants))
    call = f"useEffect(() => {{\n  {effect};\n}}{', ' + deps if deps else ''});"
    wrong = [text for key, text in variants.items() if key != deps]
    wrong += [
        "Синхронно перед каждым рендером компонента",
        f"Только когда одновременно изменились и {first}, и {second}",
    ]
    return Generated(
        stem="Когда выполнится эффект в production-сборке?",
        code=call,
        code_language="jsx",
        correct=(variants[deps],),
        wrong=tuple(wrong),
    )


@generator("frontend.react_stale_interval")
def react_stale_interval(rng: random.Random) -> Generated:
    """Эффект с [] замыкает count первого рендера: setCount(count + k) каждый раз даёт одно значение."""
    start = rng.randint(0, 5)
    step = rng.randint(1, 3)
    seconds = rng.randint(3, 6)
    code = (
        "function Ticker() {\n"
        f"  const [count, setCount] = useState({start});\n"
        "  useEffect(() => {\n"
        f"    const id = setInterval(() => setCount(count + {step}), 1000);\n"
        "    return () => clearInterval(id);\n"
        "  }, []);\n"
        "  return <span>{count}</span>;\n}"
    )
    correct = str(start + step)
    wrong = [str(start + step * seconds), str(start), str(start + step * (seconds - 1)), str(start + seconds)]
    return Generated(
        stem=f"Что покажет компонент через {seconds},5 с после монтирования?",
        code=code,
        code_language="jsx",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("frontend.vue_if_show")
def vue_if_show(rng: random.Random) -> Generated:
    directive = rng.choice(["v-if", "v-show"])
    flag = rng.choice(["isOpen", "visible", "showDetails", "expanded"])
    component = rng.choice(["UserCard", "OrderDetails", "ChartPanel", "CommentList"])
    descriptions = {
        "v-if": "Элемент не создаётся в DOM, дочерний компонент не монтируется",
        "v-show": "Элемент есть в DOM и скрыт через CSS display: none, компонент смонтирован",
    }
    other = "v-show" if directive == "v-if" else "v-if"
    return Generated(
        stem=f'В шаблоне Vue написано <{component} {directive}="{flag}" />, и {flag} = false. Что верно?',
        correct=(descriptions[directive],),
        wrong=(
            descriptions[other],
            "Элемент скрыт через visibility: hidden и продолжает занимать место",
            "Элемент удалён из DOM, но экземпляр компонента остаётся смонтированным",
            "Элемент рендерится с атрибутом hidden, его хуки mounted не вызываются",
        ),
    )


@generator("frontend.ng_binding_syntax")
def ng_binding_syntax(rng: random.Random) -> Generated:
    value = rng.choice(["title", "userName", "total"])
    flag = rng.choice(["isBusy", "isLocked", "saving"])
    handler = rng.choice(["save()", "submit()", "toggle()"])
    model = rng.choice(["query", "email", "comment"])
    syntaxes = {
        "text": (f"вывести значение свойства {value} текстом в шаблоне", f"{{{{ {value} }}}}"),
        "prop": (f"передать значение {flag} в DOM-свойство disabled кнопки", f'[disabled]="{flag}"'),
        "event": (f"вызвать {handler} при клике по кнопке", f'(click)="{handler}"'),
        "two_way": (f"связать поле ввода со свойством {model} в обе стороны", f'[(ngModel)]="{model}"'),
    }
    key = rng.choice(list(syntaxes))
    need, answer = syntaxes[key]
    wrong = [syntax for other, (_, syntax) in syntaxes.items() if other != key]
    wrong += [f'([ngModel])="{model}"', f'{{disabled}}="{flag}"']
    return Generated(
        stem=f"Шаблон Angular, задача — {need}. Какой синтаксис нужен?",
        correct=(answer,),
        wrong=tuple(wrong),
    )


RXJS_SCENARIOS = [
    ("Автодополнение в поиске {x}: при новом вводе предыдущий HTTP-запрос нужно отменить", "switchMap"),
    (
        "Переключение вкладок в списке {x}: нужны данные только последней выбранной вкладки, прежний "
        "запрос отменяется",
        "switchMap",
    ),
    (
        "Страница просмотра {x} с параметром id в маршруте: при смене id загрузка для прежнего id "
        "должна прерываться",
        "switchMap",
    ),
    ("Сохранение изменений {x}: запросы должны уходить строго по очереди, ни один не теряется", "concatMap"),
    (
        "Очередь выгрузки {x} на сервер: следующий запрос начинается только после завершения предыдущего, "
        "порядок важен",
        "concatMap",
    ),
    (
        "Журнал действий над списком {x}: каждое событие отправляется на сервер в исходном порядке, без "
        "потерь и без параллельных запросов",
        "concatMap",
    ),
    ("Кнопка «Экспорт {x}»: пока запрос выполняется, повторные клики нужно игнорировать", "exhaustMap"),
    (
        "Кнопка «Обновить» над списком {x}: пока идёт обновление, новые нажатия не должны запускать запросы",
        "exhaustMap",
    ),
    (
        "Отправка формы импорта {x}: пока запрос выполняется, повторные отправки (двойной клик, Enter) "
        "игнорируются",
        "exhaustMap",
    ),
    (
        "Загрузка вложений для {x}: файлы независимы, запросы выполняются параллельно, порядок не важен",
        "mergeMap",
    ),
    (
        "Массовое удаление {x}: для каждого выбранного элемента сразу уходит независимый запрос, все "
        "должны выполниться, порядок не важен",
        "mergeMap",
    ),
    (
        "Подгрузка подробностей {x} по мере появления id в потоке: запросы независимы, идут параллельно "
        "и не отменяются",
        "mergeMap",
    ),
]
RXJS_ENTITIES = ["заказов", "товаров", "документов", "профилей", "задач", "отчётов"]
RXJS_OPERATORS = ["switchMap", "concatMap", "exhaustMap", "mergeMap"]


@generator("frontend.rxjs_flattening")
def rxjs_flattening(rng: random.Random) -> Generated:
    text, answer = rng.choice(RXJS_SCENARIOS)
    question = rng.choice(
        [
            "Каким оператором RxJS превратить поток событий в HTTP-запросы?",
            "Какой оператор высшего порядка RxJS подходит для этого?",
            "Какой оператор RxJS обеспечит такое поведение при отображении событий в запросы?",
        ]
    )
    return Generated(
        stem=f"{text.format(x=rng.choice(RXJS_ENTITIES))}. {question}",
        correct=(answer,),
        wrong=tuple(op for op in RXJS_OPERATORS if op != answer),
    )


# --- Базовые и senior-задания, добавленные для покрытия шкалы ----------------------------------


@generator("frontend.css_font_units")
def css_font_units(rng: random.Random) -> Generated:
    """em в font-size считается от font-size родителя, rem — от font-size корневого элемента html."""
    root = rng.choice([10, 12, 16, 20])
    parent = rng.choice([value for value in range(12, 33, 2) if value != root])
    factor = rng.choice([0.5, 1.5, 2, 2.5])
    unit = rng.choice(["em", "rem"])
    cls = rng.choice(["note", "title", "price", "label", "hint", "caption"])
    wrapper = rng.choice(["card", "panel", "sidebar", "footer", "modal"])
    factor_text = f"{factor:g}"
    code = (
        f"html {{ font-size: {root}px; }}\n.{wrapper} {{ font-size: {parent}px; }}\n"
        f".{cls} {{ font-size: {factor_text}{unit}; }}\n\n"
        f'<div class="{wrapper}">\n  <p class="{cls}">Текст</p>\n</div>'
    )
    number = (parent if unit == "em" else root) * factor
    return Generated(
        stem=f"Каким будет вычисленный font-size элемента .{cls} в пикселях?",
        code=code,
        code_language="css",
        number=float(number),
    )


@generator("frontend.margin_collapse")
def margin_collapse(rng: random.Random) -> Generated:
    """Вертикальные margin соседних блоков схлопываются: расстояние = больший из двух."""
    first, second = rng.sample(["intro", "header", "lead", "card", "notice", "summary", "banner"], 2)
    bottom = rng.randrange(10, 61, 2)
    top = rng.choice([value for value in range(10, 61, 2) if value != bottom])
    padding = rng.randrange(8, 25, 4)
    side = rng.choice([0, 8, 16])
    code = (
        f".{first} {{ display: block; margin: 0 {side}px {bottom}px; padding: {padding}px; }}\n"
        f".{second} {{ display: block; margin: {top}px {side}px 0; padding: {padding}px; }}\n\n"
        f'<div class="{first}">…</div>\n<div class="{second}">…</div>'
    )
    return Generated(
        stem=(
            "Блоки идут подряд в обычном потоке (родитель — обычный block, не flex и не grid). "
            f"Какое расстояние в пикселях будет между нижней границей рамки .{first} "
            f"и верхней границей рамки .{second}?"
        ),
        code=code,
        code_language="css",
        number=float(max(bottom, top)),
    )


@generator("frontend.flex_shrink_width")
def flex_shrink_width(rng: random.Random) -> Generated:
    """Нехватка места делится пропорционально flex-shrink × flex-basis, а не одному flex-shrink."""
    names = ["a", "b", "c"]
    while True:
        bases = [rng.choice([100, 150, 200, 250, 300, 400]) for _ in range(3)]
        shrinks = [rng.randint(1, 3) for _ in range(3)]
        overflow = rng.randrange(60, 301, 10)
        weights = [s * b for s, b in zip(shrinks, bases, strict=True)]
        total = sum(weights)
        target = rng.randrange(3)
        naive = overflow * shrinks[target] / sum(shrinks)
        exact = overflow * weights[target]
        if exact % total == 0 and len(set(shrinks)) > 1 and naive != exact / total:
            break
    width = sum(bases) - overflow
    rules = "\n".join(f".{names[i]} {{ flex: 0 {shrinks[i]} {bases[i]}px; }}" for i in range(3))
    code = (
        f".row {{ display: flex; width: {width}px; }}\n{rules}\n\n"
        '<div class="row">\n  <div class="a"></div>\n  <div class="b"></div>\n  <div class="c"></div>\n</div>'
    )
    return Generated(
        stem=(
            "У дочерних элементов нет содержимого, padding, border и margin; gap и min-width не заданы. "
            f"Какой будет ширина элемента .{names[target]} в пикселях?"
        ),
        code=code,
        code_language="css",
        number=float(bases[target] - exact // total),
    )


SELECTOR_KINDS = {
    "descendant": ("{p} {c}", "элементы {c}, находящиеся внутри {p} на любой глубине вложенности"),
    "child": ("{p} > {c}", "только элементы {c}, которые являются прямыми дочерними элементами {p}"),
    "adjacent": ("{p} + {c}", "элемент {c}, который идёт сразу после {p} и имеет того же родителя"),
    "sibling": ("{p} ~ {c}", "все элементы {c}, которые идут после {p} и имеют того же родителя"),
    "compound": ("{p}{c}", "элементы, у которых одновременно есть оба класса — {p} и {c}"),
    "group": ("{p}, {c}", "все элементы {p} и все элементы {c}"),
}
SELECTOR_CLASSES = [".menu", ".item", ".card", ".title", ".list", ".row", ".tab", ".badge", ".form", ".field"]


@generator("frontend.css_combinators")
def css_combinators(rng: random.Random) -> Generated:
    parent, child = rng.sample(SELECTOR_CLASSES, 2)
    kind = rng.choice(list(SELECTOR_KINDS))
    selector, description = SELECTOR_KINDS[kind]
    stem = rng.choice(
        [
            f"Нужно выбрать {description.format(p=parent, c=child)}. Какой селектор подходит?",
            f"Какой CSS-селектор выбирает {description.format(p=parent, c=child)}?",
        ]
    )
    return Generated(
        stem=stem,
        correct=(selector.format(p=parent, c=child),),
        wrong=tuple(sel.format(p=parent, c=child) for key, (sel, _) in SELECTOR_KINDS.items() if key != kind),
    )


@generator("frontend.js_coercion_basic")
def js_coercion_basic(rng: random.Random) -> Generated:
    """+ со строкой склеивает, а -, * и / приводят строку к числу."""
    x = rng.randint(2, 9)
    y = rng.randint(1, 9)
    op = rng.choice(["-", "*"])
    first, second = rng.sample(["a", "b", "x", "y", "count", "price", "qty", "step"], 2)
    numeric = x - y if op == "-" else x * y
    concat = f"{x}{y}"
    order = rng.random() < 0.5
    left, right = (f"{first} + {second}", f"{first} {op} {second}")
    results = (concat, str(numeric))
    if not order:
        left, right = right, left
        results = results[::-1]
    code = f"const {first} = '{x}';\nconst {second} = {y};\nconsole.log({left}, {right});"
    correct = f"{results[0]} {results[1]}"
    swap = {concat: str(x + y), str(numeric): "NaN"}
    wrong = [
        f"{swap[results[0]]} {results[1]}",
        f"{results[0]} {swap[results[1]]}",
        f"{swap[results[0]]} {swap[results[1]]}",
        "TypeError",
        f"{results[1]} {results[0]}",
    ]
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


def _run_promise_chain(steps: list[tuple[str, int]], start: int, mistake: str = "") -> str:
    """Семантика цепочки промисов; mistake моделирует типичное заблуждение для дистракторов."""
    ok, value = True, start
    for kind, k in steps:
        if kind == "add":
            if ok or mistake == "then_runs":
                value += k
        elif kind == "mul":
            if ok or mistake == "then_runs":
                value *= k
        elif kind == "throw":
            if ok or mistake == "then_runs":
                ok, value = False, value + k
        elif kind == "finally":
            if mistake == "finally_value":
                ok, value = True, k
        elif kind == "catch":
            if not ok:
                ok, value = mistake != "catch_keeps", value + k
        elif kind == "then2":
            if ok:
                value *= 2
            else:
                ok, value = mistake != "catch_keeps", value - k
    return f"{'ok' if ok else 'err'} {value}"


def _promise_line(kind: str, k: int) -> str:
    return {
        "add": f"  .then(v => v + {k})",
        "mul": f"  .then(v => v * {k})",
        "throw": f"  .then(v => {{ throw v + {k}; }})",
        "finally": f"  .finally(() => {k})",
        "catch": f"  .catch(e => e + {k})",
        "then2": f"  .then(v => v * 2, e => e - {k})",
    }[kind]


@generator("frontend.js_promise_chain")
def js_promise_chain(rng: random.Random) -> Generated:
    """Отклонение пропускает then без onRejected; finally не меняет результат; catch восстанавливает."""
    start = rng.randint(1, 6)
    recover = rng.choice(["catch", "then2"])
    skipped = rng.choice(["add", "mul"])
    after = rng.choice(["add", "mul"])
    finally_after = rng.random() < 0.5
    steps = [("add", rng.randint(1, 5)), ("throw", rng.randint(1, 5)), (skipped, rng.randint(2, 4))]
    if not finally_after:
        steps.append(("finally", rng.randint(10, 99)))
    steps.append((recover, rng.randint(1, 5)))
    if finally_after:
        steps.append(("finally", rng.randint(10, 99)))
    steps.append((after, rng.randint(2, 3)))
    correct = _run_promise_chain(steps, start)
    wrong = [_run_promise_chain(steps, start, m) for m in ("then_runs", "finally_value", "catch_keeps")]
    status, number = correct.split()
    other = "err" if status == "ok" else "ok"
    wrong += [f"{other} {number}", f"{status} {start}", f"{status} {int(number) + steps[-1][1]}"]
    code = "\n".join(
        [f"Promise.resolve({start})", *(_promise_line(kind, k) for kind, k in steps)]
        + ["  .then(v => console.log('ok', v), e => console.log('err', e));"]
    )
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


JSX_NAMES = ["Save", "Delete", "Toggle", "Submit", "Select"]


@generator("frontend.react_jsx_syntax")
def react_jsx_syntax(rng: random.Random) -> Generated:
    color = rng.choice(["red", "gray", "navy", "green"])
    size = rng.choice([12, 14, 16, 18, 20])
    name = rng.choice(JSX_NAMES)
    items = rng.choice(["users", "orders", "tasks", "products"])
    flag = rng.choice(["isOpen", "visible", "showModal", "expanded"])
    modal = rng.choice(["Modal", "Dialog", "Popup", "Drawer"])
    var = rng.choice(["name", "userName", "title", "city"])
    scenarios = [
        (
            f"задаёт элементу p инлайн-стили: цвет {color} и размер шрифта {size}px",
            f"<p style={{{{ color: '{color}', fontSize: {size} }}}}>…</p>",
            [
                f'<p style="color: {color}; font-size: {size}px">…</p>',
                f"<p style={{{{ color: '{color}', font-size: {size} }}}}>…</p>",
                f"<p style={{ color: '{color}', fontSize: {size} }}>…</p>",
                f"<p css={{{{ color: '{color}', fontSize: {size} }}}}>…</p>",
            ],
        ),
        (
            f"вызывает функцию handle{name} при клике по кнопке",
            f"<button onClick={{handle{name}}}>OK</button>",
            [
                f"<button onClick={{handle{name}()}}>OK</button>",
                f'<button onclick="handle{name}()">OK</button>',
                f'<button onClick="handle{name}">OK</button>',
                f"<button on-click={{handle{name}}}>OK</button>",
            ],
        ),
        (
            f"выводит массив {items} списком li",
            f"<ul>{{{items}.map(item => <li key={{item.id}}>{{item.name}}</li>)}}</ul>",
            [
                f"<ul>{{{items}.forEach(item => <li key={{item.id}}>{{item.name}}</li>)}}</ul>",
                f"<ul>{{for (const item of {items}) <li key={{item.id}}>{{item.name}}</li>}}</ul>",
                f'<ul><li v-for="item in {items}" key={{item.id}}>{{item.name}}</li></ul>',
                f"<ul>{{{items}.map(item => {{ <li key={{item.id}}>{{item.name}}</li> }})}}</ul>",
            ],
        ),
        (
            f"показывает <{modal} /> только когда {flag} равно true",
            f"<div>{{{flag} && <{modal} />}}</div>",
            [
                f"<div>{{if ({flag}) <{modal} />}}</div>",
                f"<div><{modal} if={{{flag}}} /></div>",
                f"<div>{{{flag} ? <{modal} />}}</div>",
                f"<div>{{{flag} || <{modal} />}}</div>",
            ],
        ),
        (
            f"выводит значение переменной {var} внутри текста приветствия",
            f"<p>Привет, {{{var}}}!</p>",
            [
                f"<p>Привет, {{{{{var}}}}}!</p>",
                f"<p>Привет, ${{{var}}}!</p>",
                f'<p>Привет, "{var}"!</p>',
                f"<p>Привет, {var}!</p>",
            ],
        ),
    ]
    need, correct, wrong = rng.choice(scenarios)
    stem = rng.choice(
        [f"Какой JSX корректно {need}?", f"Нужен JSX-фрагмент, который {need}. Какой вариант верный?"]
    )
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


@generator("frontend.vue_template_syntax")
def vue_template_syntax(rng: random.Random) -> Generated:
    value = rng.choice(["title", "userName", "total", "status"])
    url = rng.choice(["profileUrl", "link", "avatarSrc", "docUrl"])
    attr = "src" if url == "avatarSrc" else "href"
    tag = "img" if attr == "src" else "a"
    handler = rng.choice(["save", "submit", "toggle", "reload"])
    items = rng.choice(["users", "orders", "tasks", "products"])
    model = rng.choice(["query", "email", "comment", "phone"])
    flag = rng.choice(["isOpen", "visible", "hasError", "loading"])
    scenarios = [
        (
            f"вывести значение {value} текстом",
            f"<p>{{{{ {value} }}}}</p>",
            [f"<p>{{ {value} }}</p>", f"<p>${{{value}}}</p>", f'<p [text]="{value}"></p>'],
        ),
        (
            f"привязать атрибут {attr} элемента {tag} к свойству {url}",
            f'<{tag} :{attr}="{url}">',
            [
                f'<{tag} {attr}="{{{{ {url} }}}}">',
                f'<{tag} [{attr}]="{url}">',
                f"<{tag} {attr}={{{url}}}>",
                f'<{tag} v-{attr}="{url}">',
            ],
        ),
        (
            f"вызвать метод {handler} при клике по кнопке",
            f'<button @click="{handler}">',
            [
                f'<button (click)="{handler}()">',
                f"<button onClick={{{handler}}}>",
                f'<button v-click="{handler}">',
                f'<button :click="{handler}">',
            ],
        ),
        (
            f"вывести элемент li для каждого элемента массива {items}",
            f'<li v-for="item in {items}" :key="item.id">{{{{ item.name }}}}</li>',
            [
                f'<li *ngFor="let item of {items}">{{{{ item.name }}}}</li>',
                f'<li v-each="item in {items}" :key="item.id">{{{{ item.name }}}}</li>',
                f'<li v-for="{items}" :key="id">{{{{ name }}}}</li>',
            ],
        ),
        (
            f"связать поле ввода со свойством {model} в обе стороны",
            f'<input v-model="{model}" />',
            [
                f'<input [(ngModel)]="{model}" />',
                f'<input :value="{model}" />',
                f'<input v-bind="{model}" />',
            ],
        ),
        (
            f"не создавать блок в DOM, пока {flag} ложно",
            f'<div v-if="{flag}">…</div>',
            [f'<div *ngIf="{flag}">…</div>', f'<div v-show="{flag}">…</div>', f'<div :if="{flag}">…</div>'],
        ),
    ]
    need, correct, wrong = rng.choice(scenarios)
    stem = rng.choice(
        [
            f"Шаблон Vue 3, задача — {need}. Какой синтаксис нужен?",
            f"Как в шаблоне Vue {need}?",
            f"Какая запись в шаблоне Vue 3 позволяет {need}?",
        ]
    )
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


HTTP_METHOD_SCENARIOS = [
    ("получить список {res}", "GET", False),
    ("загрузить одну запись из {res} по идентификатору", "GET", True),
    ("создать новую запись в коллекции {res}, идентификатор назначает сервер", "POST", False),
    ("полностью заменить запись из {res} новым представлением, переданным целиком", "PUT", True),
    ("изменить у записи из {res} только поле status, не передавая остальные поля", "PATCH", True),
    ("удалить запись из {res} по идентификатору", "DELETE", True),
]
HTTP_RESOURCES = {
    "orders": "заказов",
    "users": "пользователей",
    "tasks": "задач",
    "products": "товаров",
    "comments": "комментариев",
    "invoices": "счетов",
}


@generator("frontend.http_method_choice")
def http_method_choice(rng: random.Random) -> Generated:
    text, method, item = rng.choice(HTTP_METHOD_SCENARIOS)
    res = rng.choice(list(HTTP_RESOURCES))
    path = f"/api/{res}/{rng.randint(2, 999)}" if item else f"/api/{res}"
    need = text.format(res=HTTP_RESOURCES[res])
    stem = rng.choice(
        [
            f"REST API: нужно {need}. Какой запрос подходит?",
            f"Фронтенду нужно {need}. Какой HTTP-метод выбрать по соглашениям REST?",
        ]
    )
    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    return Generated(
        stem=stem,
        correct=(f"{method} {path}",),
        wrong=tuple(f"{other} {path}" for other in methods if other != method),
    )


HTTP_CLASSES = {
    2: "Успех: запрос получен, понят и обработан",
    3: "Перенаправление: для завершения запроса клиенту нужно действие (другой адрес или кэш)",
    4: "Ошибка клиента: запрос некорректен или не может быть выполнен из-за клиента",
    5: "Ошибка сервера: запрос корректен, но сервер не смог его обработать",
}
HTTP_CLASS_CODES = [
    200,
    201,
    202,
    204,
    301,
    302,
    304,
    307,
    400,
    401,
    403,
    404,
    409,
    422,
    429,
    500,
    502,
    503,
    504,
]


@generator("frontend.http_status_class")
def http_status_class(rng: random.Random) -> Generated:
    code = rng.choice(HTTP_CLASS_CODES)
    path = rng.choice(["/api/orders", "/api/profile", "/api/cart", "/api/search", "/api/login"])
    stem = rng.choice(
        [
            f"Запрос к {path} вернул статус {code}. К какому классу ответов относится этот код?",
            f"Что в общем случае означает код ответа {code} (по его первой цифре)? Запрос шёл к {path}.",
        ]
    )
    cls = code // 100
    wrong = [text for key, text in HTTP_CLASSES.items() if key != cls]
    wrong.append("Информационный ответ: запрос получен, обработка продолжается")
    return Generated(stem=stem, correct=(HTTP_CLASSES[cls],), wrong=tuple(wrong))


DS_SCENARIOS = [
    ("история отмены действий (Ctrl+Z) в редакторе {x}: отменяется последнее действие", "stack"),
    ("кнопка «Назад» в многошаговом мастере создания {x}: возврат к последнему открытому шагу", "stack"),
    ("проверка, что открывающие и закрывающие теги в шаблоне списка {x} правильно вложены", "stack"),
    ("отправка уведомлений о статусе {x} строго в порядке поступления", "queue"),
    ("обход дерева категорий {x} по уровням (в ширину)", "queue"),
    ("буфер запросов на сохранение {x}, которые отправляются по одному в порядке создания", "queue"),
    ("быстрый поиск {x} по id за O(1) в среднем, без перебора массива", "map"),
    ("подсчёт, сколько раз встречается каждое значение поля в выгрузке {x}", "map"),
]
DS_OPTIONS = {
    "stack": "Стек (LIFO): push и pop с одного конца",
    "queue": "Очередь (FIFO): добавление в конец, извлечение из начала",
    "map": "Map (хеш-таблица) с ключом по значению",
}
DS_WRONG = ["Отсортированный массив с поиском перебором", "Двумерный массив (матрица)"]
DS_ENTITIES = ["заказов", "задач", "документов", "товаров", "платежей", "статей"]


@generator("frontend.stack_or_queue")
def stack_or_queue(rng: random.Random) -> Generated:
    text, answer = rng.choice(DS_SCENARIOS)
    entity = rng.choice(DS_ENTITIES)
    stem = rng.choice(
        [
            f"Задача: {text.format(x=entity)}. Какая структура данных подходит лучше всего?",
            f"Какую структуру данных естественно использовать для задачи: {text.format(x=entity)}?",
        ]
    )
    wrong = [label for key, label in DS_OPTIONS.items() if key != answer] + DS_WRONG
    return Generated(stem=stem, correct=(DS_OPTIONS[answer],), wrong=tuple(wrong))


@generator("frontend.binary_search_steps")
def binary_search_steps(rng: random.Random) -> Generated:
    """Худший случай бинарного поиска — ⌊log2 n⌋ + 1 итераций (число бит в n)."""
    n = rng.randrange(40, 5001)
    while n & (n - 1) == 0:
        n += 1
    name = rng.choice(["ids", "prices", "timestamps", "scores", "sorted"])
    target = rng.choice(["x", "target", "value", "needle"])
    code = (
        f"function search({name}, {target}) {{\n  let lo = 0, hi = {name}.length - 1;\n"
        "  while (lo <= hi) {\n    const mid = (lo + hi) >> 1;\n"
        f"    if ({name}[mid] === {target}) return mid;\n"
        f"    if ({name}[mid] < {target}) lo = mid + 1;\n    else hi = mid - 1;\n"
        "  }\n  return -1;\n}"
    )
    return Generated(
        stem=(
            f"Массив {name} отсортирован по возрастанию и содержит {n} элементов. Какое наибольшее число "
            "итераций цикла while может выполнить search (худший случай, включая отсутствующее значение)?"
        ),
        code=code,
        code_language="javascript",
        number=float(n.bit_length()),
    )


MODULE_NAMES = ["api", "store", "utils", "config", "logger", "router", "theme", "i18n", "auth"]


def _walk_modules(module: str, imports: dict[str, list[str]], order: list[str], pre: list[str]) -> None:
    if module in pre:
        return
    pre.append(module)
    for dep in imports[module]:
        _walk_modules(dep, imports, order, pre)
    order.append(module)


@generator("frontend.module_eval_order")
def module_eval_order(rng: random.Random) -> Generated:
    """ES-модули выполняются обходом графа импортов в глубину: зависимости раньше, каждый модуль один раз."""
    while True:
        names = rng.sample(MODULE_NAMES, 5)
        imports: dict[str, list[str]] = {"main": rng.sample(names[:3], 2)}
        for index, name in enumerate(names):
            later = names[index + 1 :]
            imports[name] = rng.sample(later, min(len(later), rng.randint(0, 2)))
        importers = Counter(dep for deps in imports.values() for dep in deps)
        order: list[str] = []
        pre: list[str] = []

        _walk_modules("main", imports, order, pre)
        if len(order) >= 5 and max(importers.values()) >= 2:
            break
    bfs: list[str] = []
    queue = deque(["main"])
    while queue:
        module = queue.popleft()
        if module not in bfs:
            bfs.append(module)
            queue.extend(imports[module])
    blocks = []
    for module in ["main", *[name for name in names if name in order]]:
        lines = [f"// {module}.js", *(f"import './{dep}.js';" for dep in imports[module])]
        blocks.append("\n".join([*lines, f"console.log('{module}');"]))
    correct = _spaced(order)
    wrong = [_spaced(pre), _spaced(bfs), _spaced(bfs[::-1]), _spaced(order[:-1][::-1] + ["main"])]
    _fill_permutations(rng, order, wrong)
    return Generated(
        stem=(
            'Браузер загружает <script type="module" src="main.js">. Что будет выведено в консоль '
            "(через пробел)?"
        ),
        code="\n\n".join(blocks),
        code_language="javascript",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )
