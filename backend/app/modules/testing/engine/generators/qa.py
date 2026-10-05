"""Генераторы заданий QA: тест-дизайн, SQL на сгенерированных данных, API, нагрузка, pytest и JUnit."""

import json
import math
import random
from collections.abc import Iterable

from app.modules.testing.engine.generators import generator
from app.modules.testing.engine.model import Generated


def _distinct_wrong(correct: str, candidates: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for text in candidates:
        if text != correct and text not in result:
            result.append(text)
    return tuple(result)


def _joined(values: Iterable[int]) -> str:
    return ", ".join(str(value) for value in values)


# --- Тест-дизайн -------------------------------------------------------------------------------

EQUIVALENCE_DOMAINS = [
    (
        "Сервис рассчитывает тариф доставки по весу посылки",
        "кг",
        ["«Лёгкий»", "«Средний»", "«Тяжёлый»", "«Грузовой»"],
    ),
    (
        "Банк определяет ставку по сроку вклада",
        "мес.",
        ["ставка 10%", "ставка 12%", "ставка 14%", "ставка 15%"],
    ),
    (
        "Магазин даёт скидку по количеству товаров в заказе",
        "шт.",
        ["без скидки", "скидка 5%", "скидка 10%", "скидка 15%"],
    ),
]


@generator("qa.equivalence_classes")
def equivalence_classes(rng: random.Random) -> Generated:
    """Классы: по одному на каждый валидный диапазон + невалидные ниже минимума и выше максимума."""
    text, unit, labels = rng.choice(EQUIVALENCE_DOMAINS)
    ranges = rng.randint(2, 4)
    cuts = sorted(rng.sample(range(3, 60), ranges))
    upper_open = rng.random() < 0.5
    parts = []
    low = 1
    for index in range(ranges):
        high = cuts[index]
        if index == ranges - 1 and upper_open:
            parts.append(f"от {low} {unit} — {labels[index]}")
        else:
            parts.append(f"{low}–{high} {unit} — {labels[index]}")
        low = high + 1
    if upper_open:
        limits = "Значения меньше 1 не принимаются, верхнего ограничения нет."
        answer = ranges + 1
    else:
        limits = f"Значения меньше 1 и больше {cuts[-1]} не принимаются."
        answer = ranges + 2
    return Generated(
        stem=(
            f"{text} (целое число, {unit}): {'; '.join(parts)}. {limits} Сколько классов эквивалентности "
            "(валидных и невалидных) нужно выделить по значению этого "
            "поля? Нечисловой ввод не рассматривайте."
        ),
        number=float(answer),
    )


BOUNDARY_FIELDS = [
    ("Возраст клиента", "лет"),
    ("Количество билетов в заказе", "шт."),
    ("Длина пароля", "символов"),
    ("Срок аренды", "дней"),
]


@generator("qa.boundary_values_inclusive")
def boundary_values_inclusive(rng: random.Random) -> Generated:
    field, unit = rng.choice(BOUNDARY_FIELDS)
    low = rng.randint(2, 20)
    high = low + rng.randint(10, 80)
    correct = _joined([low - 1, low, high, high + 1])
    wrong = [
        _joined([low, high]),
        _joined([low + 1, high - 1]),
        _joined([low - 1, low, low + 1, high - 1, high, high + 1]),
        _joined([low - 1, high + 1]),
        _joined([low, low + 1, high - 1, high]),
    ]
    return Generated(
        stem=(
            f"Поле «{field}» принимает целые значения от {low} до {high} {unit} включительно. Какой набор "
            "значений даёт двухточечный анализ граничных значений (граница и ближайшее значение за ней)?"
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


EXCLUSIVE_RULES = [
    "Скидка действует, если сумма заказа (целые рубли) строго больше {low} и строго меньше {high}",
    "Бонус начисляется, если число покупок за месяц строго больше {low} и строго меньше {high}",
    "Тариф «Стандарт» применяется, если расстояние в км (целое) больше {low} и меньше {high}",
]


@generator("qa.boundary_values_exclusive")
def boundary_values_exclusive(rng: random.Random) -> Generated:
    """При строгих неравенствах валидный диапазон — [low+1; high−1], границы сдвигаются внутрь."""
    low = rng.choice([rng.randint(5, 50), rng.randrange(100, 1001, 100)])
    high = low + rng.choice([rng.randint(20, 90), rng.randrange(1000, 5001, 500)])
    rule = rng.choice(EXCLUSIVE_RULES).format(low=low, high=high)
    correct = _joined([low, low + 1, high - 1, high])
    wrong = [
        _joined([low - 1, low, high, high + 1]),
        _joined([low + 1, high - 1]),
        _joined([low, high]),
        _joined([low - 1, low + 1, high - 1, high + 1]),
    ]
    return Generated(
        stem=(
            f"{rule}. Какой набор значений даёт двухточечный анализ граничных значений "
            "(для каждой границы — последнее валидное и первое невалидное значение)?"
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


PAIRWISE_PARAMS = [
    "Браузер",
    "ОС",
    "Язык интерфейса",
    "Тип аккаунта",
    "Способ оплаты",
    "Валюта",
    "Тип устройства",
]


@generator("qa.pairwise_lower_bound")
def pairwise_lower_bound(rng: random.Random) -> Generated:
    """Нижняя граница pairwise = произведение двух самых больших доменов: все их пары обязательны."""
    names = rng.sample(PAIRWISE_PARAMS, 4)
    counts = [rng.randint(2, 6) for _ in names]
    if sorted(counts)[-2] < 3:
        counts[0] = 4
    top = sorted(counts)[-2:]
    listing = "; ".join(f"{name} — вариантов: {count}" for name, count in zip(names, counts, strict=True))
    return Generated(
        stem=(
            f"Параметры формы: {listing}. Все комбинации допустимы. Какое минимальное число тестов "
            "теоретически необходимо для попарного (pairwise) покрытия, то есть какова нижняя граница?"
        ),
        number=float(top[0] * top[1]),
    )


STATE_DOMAINS = [
    (
        "Заказ",
        ["Создан", "Оплачен", "Отправлен", "Доставлен", "Отменён"],
        ["оплатить", "отправить", "доставить", "отменить"],
        [
            ("Создан", "оплатить", "Оплачен"),
            ("Оплачен", "отправить", "Отправлен"),
            ("Отправлен", "доставить", "Доставлен"),
        ],
        [
            ("Создан", "отменить", "Отменён"),
            ("Оплачен", "отменить", "Отменён"),
            ("Отправлен", "отменить", "Отменён"),
        ],
    ),
    (
        "Заявка на отпуск",
        ["Черновик", "На согласовании", "Одобрена", "Отклонена"],
        ["отправить", "одобрить", "отклонить", "отозвать"],
        [
            ("Черновик", "отправить", "На согласовании"),
            ("На согласовании", "одобрить", "Одобрена"),
            ("На согласовании", "отклонить", "Отклонена"),
        ],
        [
            ("На согласовании", "отозвать", "Черновик"),
            ("Одобрена", "отозвать", "Черновик"),
            ("Отклонена", "отправить", "На согласовании"),
        ],
    ),
    (
        "Подписка",
        ["Пробная", "Активна", "Приостановлена", "Отменена"],
        ["оплатить", "приостановить", "возобновить", "отменить"],
        [
            ("Пробная", "оплатить", "Активна"),
            ("Активна", "приостановить", "Приостановлена"),
            ("Приостановлена", "возобновить", "Активна"),
        ],
        [
            ("Пробная", "отменить", "Отменена"),
            ("Активна", "отменить", "Отменена"),
            ("Приостановлена", "отменить", "Отменена"),
        ],
    ),
]


@generator("qa.state_transition_invalid")
def state_transition_invalid(rng: random.Random) -> Generated:
    """Недопустимые пары = |состояния| × |события| − число допустимых переходов."""
    entity, states, events, core, optional = rng.choice(STATE_DOMAINS)
    extra = rng.sample(optional, rng.randint(1, 3))
    valid = [t for t in core + optional if t in core or t in extra]
    listing = "; ".join(f"{src} —[{event}]→ {dst}" for src, event, dst in valid)
    return Generated(
        stem=(
            f"Объект «{entity}». Состояния: {', '.join(states)}. События: {', '.join(events)}. "
            f"Допустимые переходы: {listing}. Любое другое событие в любом состоянии должно отклоняться. "
            "Сколько тестов нужно, чтобы по одному разу проверить каждую "
            "недопустимую пару «состояние — событие»?"
        ),
        number=float(len(states) * len(events) - len(valid)),
    )


TECHNIQUES = {
    "bva": "Анализ граничных значений",
    "decision": "Таблица решений",
    "state": "Диаграмма состояний и переходов",
    "pairwise": "Попарное тестирование (pairwise)",
    "guess": "Предугадывание ошибок (error guessing)",
}
TECHNIQUE_SCENARIOS = [
    ("Нужно проверить поведение на краях допустимого диапазона: поле принимает {a}–{b} символов", "bva"),
    (
        "Размер скидки зависит от сочетания трёх условий: статус "
        "клиента, сумма заказа больше {b} ₽, наличие промокода",
        "decision",
    ),
    (
        "Документ проходит статусы «черновик → на проверке → "
        "опубликован → в архиве», часть переходов запрещена",
        "state",
    ),
    (
        "В настройках отчёта {a} выпадающих списков по 4–6 значений; полный перебор комбинаций невозможен",
        "pairwise",
    ),
    (
        "Опытный тестировщик целенаправленно проверяет места, где в "
        "похожих формах раньше часто находились дефекты",
        "guess",
    ),
]


@generator("qa.technique_choice")
def technique_choice(rng: random.Random) -> Generated:
    text, answer = rng.choice(TECHNIQUE_SCENARIOS)
    a, b = rng.randint(5, 8), rng.randrange(1000, 10001, 500)
    return Generated(
        stem=f"{text.format(a=a, b=b)}. Какая техника тест-дизайна подходит лучше всего?",
        correct=(TECHNIQUES[answer],),
        wrong=tuple(label for key, label in TECHNIQUES.items() if key != answer),
    )


SEVERITY_OPTIONS = {
    (True, True): "Серьёзность высокая, приоритет высокий",
    (True, False): "Серьёзность высокая, приоритет низкий",
    (False, True): "Серьёзность низкая, приоритет высокий",
    (False, False): "Серьёзность низкая, приоритет низкий",
}
SEVERITY_SCENARIOS = [
    ("На главной странице {product} с опечаткой написано название компании", (False, True)),
    (
        "Приложение {product} падает при экспорте отчёта в устаревший формат, которым пользуются единицы",
        (True, False),
    ),
    ("Ни один пользователь {product} не может оплатить заказ", (True, True)),
    ("На редко открываемой странице настроек {product} иконка смещена на 2 пикселя", (False, False)),
]


@generator("qa.severity_priority")
def severity_priority(rng: random.Random) -> Generated:
    """Severity — влияние дефекта на систему, priority — срочность исправления для бизнеса."""
    text, key = rng.choice(SEVERITY_SCENARIOS)
    product = rng.choice(["интернет-магазина", "онлайн-банка", "сервиса доставки", "онлайн-кинотеатра"])
    return Generated(
        stem=f"{text.format(product=product)}. Какие серьёзность "
        f"(severity) и приоритет (priority) у дефекта?",
        correct=(SEVERITY_OPTIONS[key],),
        wrong=tuple(label for other, label in SEVERITY_OPTIONS.items() if other != key),
    )


def _numeric_block(rng: random.Random, var: str, conditions: int, with_else: bool) -> list[str]:
    """Цепочка if / else if (/ else) по одной переменной: conditions + 1 исход с else и без него."""
    thresholds = sorted(rng.sample(range(10, 100, 5), conditions))
    lines = []
    for index, value in enumerate(thresholds):
        keyword = "if" if index == 0 else "} else if"
        lines += [f"  {keyword} ({var} < {value}) {{", f"    rate += {index + 1};"]
    if with_else:
        lines += ["  } else {", f"    rate += {conditions + 1};"]
    lines.append("  }")
    return lines


@generator("qa.branch_coverage")
def branch_coverage(rng: random.Random) -> Generated:
    """Независимые блоки покрываются одновременно: минимум тестов = max числа исходов среди блоков."""
    variables = rng.sample(["age", "amount", "days", "weight", "items"], 2)
    flag = rng.choice(["isVip", "hasCoupon", "isNight"])
    blocks: list[tuple[list[str], int]] = []
    first = rng.randint(2, 3)
    blocks.append((_numeric_block(rng, variables[0], first, with_else=True), first + 1))
    if rng.random() < 0.5:
        second = rng.randint(2, 3)
        blocks.append((_numeric_block(rng, variables[1], second, with_else=False), second + 1))
        used = variables
    else:
        blocks.append(([f"  if ({flag}) {{", "    rate *= 2;", "  }"], 2))
        used = [variables[0], flag]
    rng.shuffle(blocks)
    params = ", ".join(used)
    code = [f"function calcRate({params}) {{", "  let rate = 0;"]
    for lines, _ in blocks:
        code += lines
    code += ["  return rate;", "}"]
    answer = max(outcomes for _, outcomes in blocks)
    return Generated(
        stem=(
            "Параметры функции независимы, любые их сочетания допустимы. Какое минимальное число тестов "
            "даёт 100% покрытие ветвей (branch coverage)? Учитывайте и неявную ветку if без else."
        ),
        code="\n".join(code),
        code_language="javascript",
        number=float(answer),
    )


MCDC_CONDITIONS = ["isActive", "hasBalance", "isVerified", "withinLimit", "isWorkingHours", "hasConsent"]


@generator("qa.mcdc_tests")
def mcdc_tests(rng: random.Random) -> Generated:
    """Для n независимых условий, связанных только && (или только ||), MC/DC требует n + 1 тест."""
    count = rng.randint(2, 5)
    names = rng.sample(MCDC_CONDITIONS, count)
    operator = rng.choice(["&&", "||"])
    return Generated(
        stem=(
            "Условия независимы друг от друга. Какое минимальное число тестов нужно для 100% покрытия "
            "MC/DC (каждое условие должно независимо повлиять на результат решения)?"
        ),
        code=f"if ({f' {operator} '.join(names)}) {{\n  approve();\n}}",
        code_language="javascript",
        number=float(count + 1),
    )


# --- API ---------------------------------------------------------------------------------------

API_SCENARIOS = [
    ("Запрос к {path} отправлен без заголовка Authorization", "401 Unauthorized"),
    (
        "Пользователь с ролью «читатель» отправил DELETE {path}/42, удалять может только администратор",
        "403 Forbidden",
    ),
    ("GET {path}/999999 — записи с таким id не существует", "404 Not Found"),
    ("На {path} отправлен PUT, а эндпоинт поддерживает только GET и POST", "405 Method Not Allowed"),
    (
        "POST {path} отправлен с Content-Type: application/xml, а API принимает только JSON",
        "415 Unsupported Media Type",
    ),
    ("POST {path} успешно создал запись", "201 Created"),
]


@generator("qa.api_status_scenario")
def api_status_scenario(rng: random.Random) -> Generated:
    text, code = rng.choice(API_SCENARIOS)
    path = rng.choice(["/api/v1/orders", "/api/v1/users", "/api/v1/tickets", "/api/v1/invoices"])
    return Generated(
        stem=f"{text.format(path=path)}. Какой код ответа ожидать от корректно реализованного REST API?",
        correct=(code,),
        wrong=tuple(other for _, other in API_SCENARIOS if other != code) + ("500 Internal Server Error",),
    )


@generator("qa.jsonpath_filter")
def jsonpath_filter(rng: random.Random) -> Generated:
    count = rng.randint(5, 6)
    ids = rng.sample(range(1, 40), count)
    prices = rng.sample(range(100, 2001, 50), count)
    pivot = rng.choice(sorted(prices)[1:-1])
    op = rng.choice([">", ">=", "<", "<="])
    checks = {
        ">": lambda p: p > pivot,
        ">=": lambda p: p >= pivot,
        "<": lambda p: p < pivot,
        "<=": lambda p: p <= pivot,
    }
    mirror = {">": ">=", ">=": ">", "<": "<=", "<=": "<"}
    in_stock = [rng.random() < 0.6 for _ in range(count)]
    items = [{"id": i, "price": p, "inStock": s} for i, p, s in zip(ids, prices, in_stock, strict=True)]

    def select(operator: str) -> str:
        return "[" + ", ".join(str(item["id"]) for item in items if checks[operator](item["price"])) + "]"

    correct = select(op)
    complement = "[" + ", ".join(str(i["id"]) for i in items if not checks[op](i["price"])) + "]"
    wrong = [
        select(mirror[op]),
        complement,
        "[" + ", ".join(str(i) for i in ids) + "]",
        "[" + ", ".join(str(i["price"]) for i in items if checks[op](i["price"])) + "]",
        "[]",
    ]
    body = json.dumps({"items": items}, ensure_ascii=False, indent=2)
    return Generated(
        stem=f"Что вернёт JSONPath-выражение $.items[?(@.price {op} {pivot})].id для этого ответа API?",
        code=body,
        code_language="json",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


SCHEMA_ENUMS = {"role": ["admin", "editor", "viewer"], "status": ["new", "paid", "closed"]}


@generator("qa.json_schema_invalid")
def json_schema_invalid(rng: random.Random) -> Generated:
    id_name = rng.choice(["id", "userId", "orderId"])
    text_name = rng.choice(["email", "login", "title"])
    enum_name = rng.choice(list(SCHEMA_ENUMS))
    allowed = SCHEMA_ENUMS[enum_name]
    schema = {
        "type": "object",
        "required": [id_name, text_name],
        "properties": {
            id_name: {"type": "integer", "minimum": 1},
            text_name: {"type": "string", "minLength": 3},
            enum_name: {"enum": allowed},
        },
        "additionalProperties": False,
    }
    words = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya"]

    def valid_doc() -> dict:
        doc = {id_name: rng.randint(1, 999), text_name: rng.choice(words) + str(rng.randint(1, 99))}
        if rng.random() < 0.6:
            doc[enum_name] = rng.choice(allowed)
        return doc

    valid: list[str] = []
    while len(valid) < 4:
        text = json.dumps(valid_doc(), ensure_ascii=False)
        if text not in valid:
            valid.append(text)
    broken = valid_doc()
    kind = rng.choice(["missing", "string_id", "zero_id", "enum", "extra", "short", "float_id"])
    if kind == "missing":
        del broken[text_name]
    elif kind == "string_id":
        broken[id_name] = str(broken[id_name])
    elif kind == "zero_id":
        broken[id_name] = 0
    elif kind == "enum":
        broken[enum_name] = rng.choice(["owner", "guest", "draft", "unknown"])
    elif kind == "extra":
        broken["comment"] = "ok"
    elif kind == "short":
        broken[text_name] = rng.choice(["ab", "x", "yo"])
    else:
        broken[id_name] = broken[id_name] + 0.5
    return Generated(
        stem="Какой из ответов API НЕ пройдёт валидацию по JSON Schema?",
        code=json.dumps(schema, ensure_ascii=False, indent=2),
        code_language="json",
        correct=(json.dumps(broken, ensure_ascii=False),),
        wrong=tuple(valid),
    )


# --- SQL ---------------------------------------------------------------------------------------


def _table(name: str, columns: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return "NULL" if value is None else str(value)

    widths = [max(len(col), *(len(cell(row[i])) for row in rows)) for i, col in enumerate(columns)]
    lines = [f"-- {name}", "-- " + " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))]
    for row in rows:
        lines.append("-- " + " | ".join(cell(value).ljust(widths[i]) for i, value in enumerate(row)))
    return "\n".join(lines)


STATUSES = ["paid", "new", "cancelled"]


def _orders(rng: random.Random, count: int, users: list[int]) -> list[list[object]]:
    return [
        [index + 1, rng.choice(users), rng.choice(STATUSES), rng.randrange(100, 3001, 50)]
        for index in range(count)
    ]


@generator("qa.sql_where_count")
def sql_where_count(rng: random.Random) -> Generated:
    while True:
        rows = _orders(rng, rng.randint(7, 9), [1, 2, 3, 4])
        status = rng.choice(STATUSES)
        if rng.random() < 0.5:
            limit = rng.choice([row[3] for row in rows])
            where = f"status = '{status}' AND amount > {limit}"
            answer = sum(1 for row in rows if row[2] == status and row[3] > limit)
        else:
            low, high = sorted(rng.sample([row[3] for row in rows], 2))
            where = f"amount BETWEEN {low} AND {high}"
            answer = sum(1 for row in rows if low <= row[3] <= high)
        if 1 <= answer < len(rows):
            break
    code = _table("orders", ["id", "user_id", "status", "amount"], rows)
    code += f"\n\nSELECT COUNT(*) FROM orders WHERE {where};"
    return Generated(stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(answer))


@generator("qa.sql_null_count")
def sql_null_count(rng: random.Random) -> Generated:
    """COUNT(col) пропускает NULL; сравнение NULL <> 'x' даёт UNKNOWN, и строка не попадает в WHERE."""
    column, values = rng.choice(
        [("coupon", ["SALE10", "WELCOME", "VIP"]), ("city", ["Казань", "Омск", "Тула"])]
    )
    while True:
        rows = [
            [
                index + 1,
                rng.choice(["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Зоя", "Илья"]),
                None if rng.random() < 0.35 else rng.choice(values),
            ]
            for index in range(rng.randint(7, 9))
        ]
        nulls = sum(1 for row in rows if row[2] is None)
        if 2 <= nulls <= len(rows) - 3:
            break
    if rng.random() < 0.5:
        query = f"SELECT COUNT({column}) FROM customers;"
        answer = len(rows) - nulls
    else:
        target = rng.choice(values)
        query = f"SELECT COUNT(*) FROM customers WHERE {column} <> '{target}';"
        answer = sum(1 for row in rows if row[2] is not None and row[2] != target)
    code = _table("customers", ["id", "name", column], rows) + "\n\n" + query
    return Generated(stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(answer))


def _users(rng: random.Random) -> list[list[object]]:
    names = rng.sample(["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор"], rng.randint(4, 5))
    return [[index + 1, name] for index, name in enumerate(names)]


@generator("qa.sql_left_join_count")
def sql_left_join_count(rng: random.Random) -> Generated:
    """LEFT JOIN: пользователь без заказов даёт одну строку, с k заказами — k строк."""
    while True:
        users = _users(rng)
        ids = [row[0] for row in users]
        orders = _orders(rng, rng.randint(5, 7), ids)
        counts = [sum(1 for order in orders if order[1] == uid) for uid in ids]
        if 0 in counts and max(counts) >= 2:
            break
    answer = sum(max(1, count) for count in counts)
    code = _table("users", ["id", "name"], users) + "\n\n"
    code += _table("orders", ["id", "user_id", "status", "amount"], orders)
    code += "\n\nSELECT COUNT(*)\nFROM users u\nLEFT JOIN orders o ON o.user_id = u.id;"
    return Generated(stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(answer))


@generator("qa.sql_left_join_filter")
def sql_left_join_filter(rng: random.Random) -> Generated:
    """Фильтр по правой таблице в WHERE отсекает NULL-строки (LEFT JOIN становится INNER), в ON — нет."""
    while True:
        users = _users(rng)
        ids = [row[0] for row in users]
        orders = _orders(rng, rng.randint(6, 8), ids)
        paid = [sum(1 for o in orders if o[1] == uid and o[2] == "paid") for uid in ids]
        if 0 in paid and max(paid) >= 2:
            break
    if rng.random() < 0.5:
        join = "LEFT JOIN orders o ON o.user_id = u.id\nWHERE o.status = 'paid'"
        answer = sum(paid)
    else:
        join = "LEFT JOIN orders o ON o.user_id = u.id AND o.status = 'paid'"
        answer = sum(max(1, count) for count in paid)
    code = _table("users", ["id", "name"], users) + "\n\n"
    code += _table("orders", ["id", "user_id", "status", "amount"], orders)
    code += f"\n\nSELECT u.name, o.id\nFROM users u\n{join};"
    return Generated(
        stem="Сколько строк вернёт запрос?", code=code, code_language="sql", number=float(answer)
    )


@generator("qa.sql_group_having")
def sql_group_having(rng: random.Random) -> Generated:
    while True:
        orders = _orders(rng, rng.randint(8, 10), [1, 2, 3, 4, 5])
        if rng.random() < 0.5:
            threshold = rng.randint(2, 3)
            having = f"COUNT(*) >= {threshold}"
            groups = {uid for uid in range(1, 6) if sum(1 for o in orders if o[1] == uid) >= threshold}
        else:
            threshold = rng.randrange(1500, 4001, 500)
            having = f"SUM(amount) > {threshold}"
            groups = {uid for uid in range(1, 6) if sum(o[3] for o in orders if o[1] == uid) > threshold}
        present = {o[1] for o in orders}
        if 1 <= len(groups) < len(present):
            break
    code = _table("orders", ["id", "user_id", "status", "amount"], orders)
    code += f"\n\nSELECT user_id\nFROM orders\nGROUP BY user_id\nHAVING {having};"
    return Generated(
        stem="Сколько строк вернёт запрос?", code=code, code_language="sql", number=float(len(groups))
    )


@generator("qa.sql_task_query")
def sql_task_query(rng: random.Random) -> Generated:
    table = rng.choice(["customers", "clients", "users"])
    column = rng.choice(["city", "country", "segment"])
    limit = rng.choice([3, 5, 10])
    tasks = [
        (
            f"Получить список уникальных значений {column} из таблицы {table}",
            f"SELECT DISTINCT {column} FROM {table};",
            [
                f"SELECT {column} FROM {table};",
                f"SELECT COUNT(DISTINCT {column}) FROM {table};",
                f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL;",
            ],
        ),
        (
            f"Получить {limit} самых дорогих товаров из таблицы products",
            f"SELECT * FROM products ORDER BY price DESC LIMIT {limit};",
            [
                f"SELECT * FROM products ORDER BY price ASC LIMIT {limit};",
                f"SELECT * FROM products LIMIT {limit};",
                f"SELECT MAX(price) FROM products LIMIT {limit};",
            ],
        ),
        (
            "Посчитать количество заказов в каждом статусе",
            "SELECT status, COUNT(*) FROM orders GROUP BY status;",
            [
                "SELECT status, COUNT(*) FROM orders;",
                "SELECT COUNT(DISTINCT status) FROM orders;",
                "SELECT status, COUNT(*) FROM orders ORDER BY status;",
            ],
        ),
        (
            f"Найти записи в {table}, у которых не заполнен email (значение NULL)",
            f"SELECT * FROM {table} WHERE email IS NULL;",
            [
                f"SELECT * FROM {table} WHERE email = NULL;",
                f"SELECT * FROM {table} WHERE email = '';",
                f"SELECT * FROM {table} WHERE email IS NOT NULL;",
            ],
        ),
    ]
    task, correct, wrong = rng.choice(tasks)
    return Generated(
        stem=f"{task}. Какой запрос (PostgreSQL) решает задачу?",
        correct=(correct,),
        wrong=tuple(wrong),
    )


# --- Процессы, нагрузка, веб и мобильные -------------------------------------------------------

TEST_TYPES = {
    "smoke": "Дымовое (smoke)",
    "retest": "Повторное (re-test, подтверждающее)",
    "regression": "Регрессионное",
}
TEST_TYPE_SCENARIOS = [
    (
        "Пришла новая сборка {build}; за 15 минут нужно понять, работают ли "
        "ключевые функции и брать ли её в детальное тестирование",
        "smoke",
    ),
    ("Разработчик исправил дефект {bug}; нужно убедиться, что именно он больше не воспроизводится", "retest"),
    (
        "В сборке {build} исправили расчёт доставки; нужно убедиться, "
        "что не сломались ранее работавшие функции",
        "regression",
    ),
]


@generator("qa.test_type_scenario")
def test_type_scenario(rng: random.Random) -> Generated:
    text, answer = rng.choice(TEST_TYPE_SCENARIOS)
    build = f"{rng.randint(1, 4)}.{rng.randint(0, 20)}.{rng.randint(0, 9)}"
    bug = f"{rng.choice(['SHOP', 'PAY', 'CRM'])}-{rng.randint(100, 9999)}"
    wrong = [label for key, label in TEST_TYPES.items() if key != answer]
    wrong += ["Нагрузочное", "Юзабилити-тестирование"]
    return Generated(
        stem=f"{text.format(build=build, bug=bug)}. Какой вид тестирования проводится?",
        correct=(TEST_TYPES[answer],),
        wrong=tuple(wrong),
    )


PERF_TYPES = {
    "load": "Нагрузочное (load)",
    "stress": "Стрессовое (stress)",
    "soak": "Тестирование стабильности (soak, endurance)",
    "spike": "Тестирование пиковой нагрузки (spike)",
}
PERF_SCENARIOS = [
    (
        "Проверить, что сервис выдерживает ожидаемые {rps} RPS в течение часа с допустимым временем ответа",
        "load",
    ),
    (
        "Постепенно увеличивать нагрузку сверх {rps} RPS до отказа, "
        "чтобы найти предел и проверить восстановление",
        "stress",
    ),
    ("Держать обычные {rps} RPS в течение 24 часов, чтобы выявить утечки памяти и деградацию", "soak"),
    ("Резко поднять нагрузку с {base} до {rps} RPS за минуту, как при старте распродажи", "spike"),
]


@generator("qa.perf_test_type")
def perf_test_type(rng: random.Random) -> Generated:
    text, answer = rng.choice(PERF_SCENARIOS)
    rps = rng.randrange(200, 3001, 100)
    stem = text.format(rps=rps, base=rps // 20)
    return Generated(
        stem=f"{stem}. Как называется такой вид тестирования производительности?",
        correct=(PERF_TYPES[answer],),
        wrong=tuple(label for key, label in PERF_TYPES.items() if key != answer) + ("Объёмное (volume)",),
    )


def _ru_number(value: float) -> str:
    return (f"{value:g}").replace(".", ",")


@generator("qa.littles_law")
def littles_law(rng: random.Random) -> Generated:
    """Закрытая модель: X = N / (R + Z) — закон Литтла для цикла «ответ + think time»."""
    response = rng.choice([0.5, 1.0, 1.5, 2.0])
    think = rng.choice([2, 3, 4, 5, 8])
    cycle = response + think
    throughput = rng.randrange(10, 201, 10)
    users = int(throughput * cycle)
    if rng.random() < 0.5:
        stem = (
            f"В нагрузочном тесте с закрытой моделью {users} "
            f"виртуальных пользователей. Среднее время ответа — "
            f"{_ru_number(response)} с, пауза между запросами (think time) — {think} с. Какую интенсивность "
            "запросов в секунду создаст тест в установившемся режиме?"
        )
        answer = throughput
    else:
        stem = (
            f"Нужно подать {throughput} запросов в секунду. Среднее время ответа — {_ru_number(response)} с, "
            f"think time — {think} с, модель нагрузки закрытая. Сколько виртуальных пользователей нужно?"
        )
        answer = users
    return Generated(stem=stem, number=float(answer))


@generator("qa.percentile_nearest_rank")
def percentile_nearest_rank(rng: random.Random) -> Generated:
    size = rng.choice([10, 20])
    percentile = rng.choice([50, 90] if size == 10 else [90, 95])
    values = rng.sample(range(80, 2001, 10), size)
    rank = math.ceil(percentile / 100 * size)
    answer = sorted(values)[rank - 1]
    return Generated(
        stem=(
            f"Время ответа {size} запросов (мс): "
            f"{', '.join(map(str, values))}. Найдите p{percentile} методом "
            f"ближайшего ранга: k = ⌈{percentile}/100 · n⌉, ответ — k-е значение в упорядоченном по "
            "возрастанию списке."
        ),
        number=float(answer),
    )


DEVTOOLS = {
    "Network": "посмотреть статус и тело ответа запроса к {api}",
    "Console": "увидеть текст необработанной JavaScript-ошибки после клика по «{button}»",
    "Application": "проверить, какие cookie и данные localStorage сохранил сайт после входа",
    "Elements": "посмотреть, какие CSS-правила применились к кнопке «{button}»",
    "Performance": "записать профиль, чтобы найти долгие задачи при прокрутке ленты",
}


@generator("qa.devtools_tab")
def devtools_tab(rng: random.Random) -> Generated:
    tab = rng.choice(list(DEVTOOLS))
    task = DEVTOOLS[tab].format(
        api=rng.choice(["/api/cart", "/api/login", "/api/search"]),
        button=rng.choice(["Купить", "Сохранить", "Отправить"]),
    )
    return Generated(
        stem=f"Нужно {task}. Какая вкладка Chrome DevTools для этого предназначена?",
        correct=(tab,),
        wrong=tuple(other for other in DEVTOOLS if other != tab),
    )


MOBILE_TOOLS = {
    "Посмотреть системный лог Android-устройства во время падения приложения": "adb logcat",
    "Установить сборку {app}.apk на подключённое Android-устройство": "adb install {app}.apk",
    "Перехватить и подменить HTTPS-ответ сервера для мобильного приложения": (
        "HTTP-прокси (Charles, Proxyman, mitmproxy) с сертификатом, установленным на устройство"
    ),
    "Проверить веб-версию на медленном "
    "мобильном интернете в Chrome": "Throttling на вкладке Network в Chrome DevTools",
    "Посмотреть иерархию UI-элементов на экране Android-приложения": "Layout Inspector в Android Studio",
}


@generator("qa.mobile_tool")
def mobile_tool(rng: random.Random) -> Generated:
    app = rng.choice(["shop", "bank", "delivery", "app-release"])
    task = rng.choice(list(MOBILE_TOOLS))
    answer = MOBILE_TOOLS[task].format(app=app)
    wrong = [tool.format(app=app) for other, tool in MOBILE_TOOLS.items() if other != task]
    return Generated(
        stem=f"{task.format(app=app)}. Какой инструмент для этого подходит?",
        correct=(answer,),
        wrong=tuple(wrong),
    )


# --- pytest и JUnit ----------------------------------------------------------------------------


@generator("qa.pytest_fixture_scope")
def pytest_fixture_scope(rng: random.Random) -> Generated:
    """function — на каждый тест, module — на каждый файл, session — один раз на прогон."""
    scope = rng.choice(["function", "module", "session"])
    fixture = rng.choice(["db", "api_client", "browser"])
    files = [
        ("test_orders.py", ["create", "list", "cancel", "health"]),
        ("test_users.py", ["login", "logout", "profile"]),
    ]
    lines = [
        "# conftest.py",
        f'@pytest.fixture(scope="{scope}")',
        f"def {fixture}():",
        '    print("setup")',
        "    yield Client()",
        "",
    ]
    using_total = 0
    files_using = 0
    for index, (filename, names) in enumerate(files):
        chosen = rng.sample(names, rng.randint(2, len(names)))
        uses = [name for name in chosen if rng.random() < 0.6]
        if index == 0 and not uses:
            uses = [chosen[0]]
        using_total += len(uses)
        files_using += 1 if uses else 0
        lines.append(f"# {filename}")
        for name in chosen:
            args = fixture if name in uses else ""
            lines.append(f"def test_{name}({args}): ...")
        lines.append("")
    answer = {"function": using_total, "module": files_using, "session": 1}[scope]
    return Generated(
        stem=(
            "Запускается pytest для обоих файлов, все тесты проходят. Сколько раз выполнится код "
            "фикстуры до yield (вывод «setup»)?"
        ),
        code="\n".join(lines).rstrip(),
        code_language="python",
        number=float(answer),
    )


@generator("qa.pytest_parametrize")
def pytest_parametrize(rng: random.Random) -> Generated:
    """Несколько декораторов parametrize дают декартово произведение наборов."""
    browsers = rng.sample(["chromium", "firefox", "webkit", "edge"], rng.randint(2, 3))
    roles = rng.sample(["admin", "user", "guest", "manager"], rng.randint(2, 3))
    cases = rng.randint(2, 4)
    amounts = rng.sample(range(0, 10001, 100), cases)
    plain = rng.randint(1, 2)
    lines = [
        f'@pytest.mark.parametrize("browser", {browsers})',
        f'@pytest.mark.parametrize("role", {roles})',
        "def test_login(browser, role): ...",
        "",
        '@pytest.mark.parametrize("amount, allowed", ['
        + ", ".join(f"({a}, {a <= 5000})" for a in amounts)
        + "])",
        "def test_limit(amount, allowed): ...",
        "",
    ]
    lines += [f"def test_smoke_{index + 1}(): ..." for index in range(plain)]
    return Generated(
        stem="Сколько тестов соберёт pytest из этого файла?",
        code="\n".join(lines).replace("'", '"'),
        code_language="python",
        number=float(len(browsers) * len(roles) + cases + plain),
    )


@generator("qa.junit_before_each")
def junit_before_each(rng: random.Random) -> Generated:
    """@BeforeEach выполняется перед каждым вызовом: каждый параметр и каждое повторение — отдельный вызов."""
    cls = rng.choice(["CartTest", "OrderServiceTest", "PaymentTest"])
    plain = rng.randint(1, 3)
    values = rng.sample(range(1, 50), rng.randint(2, 4))
    repeats = rng.randint(2, 4)
    lines = [f"class {cls} {{", "    @BeforeEach", '    void setUp() { System.out.println("setup"); }', ""]
    for index in range(plain):
        lines += ["    @Test", f"    void case{index + 1}() {{ }}", ""]
    lines += ["    @Disabled", "    @Test", "    void legacy() { }", ""]
    lines += [
        "    @ParameterizedTest",
        f"    @ValueSource(ints = {{{', '.join(map(str, values))}}})",
        "    void acceptsQuantity(int quantity) { }",
        "",
        f"    @RepeatedTest({repeats})",
        "    void isStable() { }",
        "}",
    ]
    return Generated(
        stem="Класс запускается целиком в JUnit 5. Сколько раз выполнится метод setUp()?",
        code="\n".join(lines),
        code_language="java",
        number=float(plain + len(values) + repeats),
    )
