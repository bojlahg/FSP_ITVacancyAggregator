"""Генераторы заданий QA: тест-дизайн, SQL на сгенерированных данных, API, нагрузка, pytest и JUnit."""

import json
import math
import random
from collections.abc import Iterable

from app.modules.testing.engine.expressions import plural
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
    while True:
        cuts = sorted(rng.sample(range(3, 60), ranges))
        # соседние пороги не ближе 3: иначе выходит вырожденный диапазон «23–23»
        if all(right - left >= 3 for left, right in zip(cuts, cuts[1:], strict=False)):
            break
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


# единица после «до N»: формы родительного падежа для 1, 2–4 и 5+ (до 21 года, до 43 лет)
BOUNDARY_FIELDS = [
    ("Возраст клиента", ("года", "лет", "лет")),
    ("Количество билетов в заказе", ("шт.", "шт.", "шт.")),
    ("Длина пароля", ("символа", "символов", "символов")),
    ("Срок аренды", ("дня", "дней", "дней")),
]


@generator("qa.boundary_values_inclusive")
def boundary_values_inclusive(rng: random.Random) -> Generated:
    field, forms = rng.choice(BOUNDARY_FIELDS)
    low = rng.randint(2, 20)
    high = low + rng.randint(10, 80)
    unit = plural(high, *forms)
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
            ("Доставлен", "отменить", "Отменён"),
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
            ("Одобрена", "отклонить", "Отклонена"),
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
            ("Отменена", "возобновить", "Активна"),
        ],
    ),
    (
        "Тикет поддержки",
        ["Открыт", "В работе", "Ждёт ответа", "Решён", "Закрыт"],
        ["взять", "запросить", "ответить", "решить", "закрыть"],
        [
            ("Открыт", "взять", "В работе"),
            ("В работе", "решить", "Решён"),
            ("Решён", "закрыть", "Закрыт"),
        ],
        [
            ("В работе", "запросить", "Ждёт ответа"),
            ("Ждёт ответа", "ответить", "В работе"),
            ("Открыт", "закрыть", "Закрыт"),
            ("Решён", "ответить", "В работе"),
        ],
    ),
    (
        "Бронирование номера",
        ["Ожидает оплаты", "Подтверждено", "Заселение", "Завершено", "Отменено"],
        ["оплатить", "заселить", "выселить", "отменить"],
        [
            ("Ожидает оплаты", "оплатить", "Подтверждено"),
            ("Подтверждено", "заселить", "Заселение"),
            ("Заселение", "выселить", "Завершено"),
        ],
        [
            ("Ожидает оплаты", "отменить", "Отменено"),
            ("Подтверждено", "отменить", "Отменено"),
            ("Заселение", "отменить", "Завершено"),
        ],
    ),
]


@generator("qa.state_transition_invalid")
def state_transition_invalid(rng: random.Random) -> Generated:
    """Недопустимые пары = |состояния| × |события| − число допустимых переходов."""
    entity, states, events, core, optional = rng.choice(STATE_DOMAINS)
    extra = rng.sample(optional, rng.randint(1, len(optional)))
    valid = [t for t in core + optional if t in core or t in extra]
    rng.shuffle(valid)
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
    ("Поле «{field}» принимает целые числа от {a} до {b}; важнее всего проверить значения у пределов", "bva"),
    (
        "Размер скидки зависит от сочетания трёх условий: статус "
        "клиента, сумма заказа больше {b} ₽, наличие промокода",
        "decision",
    ),
    (
        "Решение об одобрении заявки на кредит зависит от комбинации "
        "условий: возраст, наличие долга, подтверждённый доход",
        "decision",
    ),
    (
        "Документ проходит статусы «черновик → на проверке → "
        "опубликован → в архиве», часть переходов запрещена",
        "state",
    ),
    (
        "Объект «{entity}» меняет статусы по событиям, и нужно проверить "
        "допустимые и запрещённые переходы между ними",
        "state",
    ),
    (
        "В настройках отчёта {a} выпадающих списков по 4–6 значений; полный перебор комбинаций невозможен",
        "pairwise",
    ),
    (
        "Форму «{form}» нужно проверить в {a} браузерах, нескольких ОС и языках; "
        "все комбинации не успеть, но каждая пара значений должна встретиться",
        "pairwise",
    ),
    (
        "Опытный тестировщик целенаправленно проверяет места, где в "
        "похожих формах раньше часто находились дефекты",
        "guess",
    ),
    (
        "По опыту прошлых релизов тестировщик составляет список типичных "
        "ошибок (пустые строки, спецсимволы, двойной клик) и проверяет форму «{form}» по нему",
        "guess",
    ),
]
# поле, форма и объект со статусами — из одной предметной области
TECHNIQUE_SUBJECTS = [
    ("Сумма кредита", "Заявка на кредит", "Заявка на кредит"),
    ("Возраст", "Регистрация", "Учётная запись"),
    ("Срок доставки", "Доставка", "Доставка"),
    ("Количество гостей", "Бронирование", "Бронирование"),
]


@generator("qa.technique_choice")
def technique_choice(rng: random.Random) -> Generated:
    text, answer = rng.choice(TECHNIQUE_SCENARIOS)
    a, b = rng.randint(5, 8), rng.randrange(1000, 10001, 500)
    field, form, entity = rng.choice(TECHNIQUE_SUBJECTS)
    question = rng.choice(
        ["Какая техника тест-дизайна подходит лучше всего?", "Какую технику тест-дизайна выбрать?"]
    )
    return Generated(
        stem=f"{text.format(a=a, b=b, field=field, form=form, entity=entity)}. {question}",
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
        "Логотип {product} на главной странице отображается чужим цветом за день до рекламной кампании",
        (False, True),
    ),
    ("На кнопке «Оформить заказ» на главной странице {product} грубая опечатка", (False, True)),
    (
        "Приложение {product} падает при экспорте отчёта в устаревший формат, которым пользуются единицы",
        (True, False),
    ),
    (
        "Приложение {product} аварийно завершается на версии ОС, доля которой меньше 0,1% и которую "
        "решено перестать поддерживать",
        (True, False),
    ),
    (
        "Приложение {product} аварийно завершается, если вставить в поле комментария 50 000 символов — "
        "реальные пользователи так не делают",
        (True, False),
    ),
    ("Ни один пользователь {product} не может оплатить заказ", (True, True)),
    ("После обновления {product} пользователи не могут войти в аккаунт", (True, True)),
    ("Данные карт пользователей {product} пишутся в открытом виде в общедоступный лог", (True, True)),
    ("На редко открываемой странице настроек {product} иконка смещена на 2 пикселя", (False, False)),
    ("В подсказке на странице «О компании» {product} лишняя запятая", (False, False)),
    ("Цвет рамки неактивного поля в старом разделе справки {product} отличается от макета", (False, False)),
]
SEVERITY_PRODUCTS = [
    "интернет-магазина",
    "онлайн-банка",
    "сервиса доставки",
    "онлайн-кинотеатра",
    "сервиса бронирования",
    "онлайн-школы",
    "маркетплейса",
    "медицинского портала",
]


@generator("qa.severity_priority")
def severity_priority(rng: random.Random) -> Generated:
    """Severity — влияние дефекта на систему, priority — срочность исправления для бизнеса."""
    text, key = rng.choice(SEVERITY_SCENARIOS)
    product = rng.choice(SEVERITY_PRODUCTS)
    question = rng.choice(
        [
            "Какие серьёзность (severity) и приоритет (priority) у дефекта?",
            "Как оценить серьёзность (severity) и приоритет (priority) этого дефекта?",
        ]
    )
    return Generated(
        stem=f"{text.format(product=product)}. {question}",
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
    table = rng.choice(["customers", "clients", "users", "accounts", "members"])
    column = rng.choice(["city", "country", "segment", "region", "plan"])
    goods, price = rng.choice([("products", "price"), ("items", "cost"), ("tariffs", "monthly_fee")])
    orders, status = rng.choice([("orders", "status"), ("tickets", "state"), ("payments", "status")])
    mail = rng.choice(["email", "phone", "birth_date"])
    limit = rng.choice([3, 5, 10, 20])
    top = plural(limit, "самую дорогую позицию", "самые дорогие позиции", "самых дорогих позиций")
    since = rng.choice(["2025-01-01", "2025-07-01", "2026-03-01", "2026-06-15"])
    tasks = [
        (
            f"Получить список уникальных значений {column} из таблицы {table}",
            f"SELECT DISTINCT {column} FROM {table};",
            [
                f"SELECT {column} FROM {table};",
                f"SELECT COUNT(DISTINCT {column}) FROM {table};",
                f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL;",
                f"SELECT {column}, COUNT(*) FROM {table};",
                f"SELECT * FROM {table} ORDER BY {column};",
            ],
        ),
        (
            f"Получить {limit} {top} из таблицы {goods} (цена — {price})",
            f"SELECT * FROM {goods} ORDER BY {price} DESC LIMIT {limit};",
            [
                f"SELECT * FROM {goods} ORDER BY {price} ASC LIMIT {limit};",
                f"SELECT * FROM {goods} LIMIT {limit};",
                f"SELECT MAX({price}) FROM {goods} LIMIT {limit};",
                f"SELECT * FROM {goods} WHERE {price} > {limit} ORDER BY {price} DESC;",
                f"SELECT * FROM {goods} GROUP BY {price} LIMIT {limit};",
            ],
        ),
        (
            f"Посчитать количество строк в {orders} для каждого значения {status}",
            f"SELECT {status}, COUNT(*) FROM {orders} GROUP BY {status};",
            [
                f"SELECT {status}, COUNT(*) FROM {orders};",
                f"SELECT COUNT(DISTINCT {status}) FROM {orders};",
                f"SELECT {status}, COUNT(*) FROM {orders} ORDER BY {status};",
                f"SELECT DISTINCT {status} FROM {orders};",
                f"SELECT {status}, SUM(1) FROM {orders} WHERE {status} IS NOT NULL;",
            ],
        ),
        (
            f"Найти записи в {table}, у которых не заполнено поле {mail} (значение NULL)",
            f"SELECT * FROM {table} WHERE {mail} IS NULL;",
            [
                f"SELECT * FROM {table} WHERE {mail} = NULL;",
                f"SELECT * FROM {table} WHERE {mail} = '';",
                f"SELECT * FROM {table} WHERE {mail} IS NOT NULL;",
                f"SELECT * FROM {table} WHERE {mail} <> NULL;",
                f"SELECT * FROM {table} WHERE NOT {mail};",
            ],
        ),
        (
            f"Найти строки {orders}, созданные начиная с {since} включительно (столбец created_at — date)",
            f"SELECT * FROM {orders} WHERE created_at >= '{since}';",
            [
                f"SELECT * FROM {orders} WHERE created_at > '{since}';",
                f"SELECT * FROM {orders} WHERE created_at <= '{since}';",
                f"SELECT * FROM {orders} WHERE created_at = '{since}';",
                f"SELECT * FROM {orders} ORDER BY created_at LIMIT 1;",
            ],
        ),
        (
            f"Посчитать, сколько строк в таблице {table}",
            f"SELECT COUNT(*) FROM {table};",
            [
                f"SELECT COUNT({mail}) FROM {table};",
                f"SELECT SUM(id) FROM {table};",
                f"SELECT MAX(id) FROM {table};",
                f"SELECT COUNT(DISTINCT {column}) FROM {table};",
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
    "Network": [
        "посмотреть статус и тело ответа запроса к {api}",
        "проверить, какие заголовки браузер отправил в запросе к {api}",
        "понять, почему после клика по «{button}» запрос к {api} вернул ошибку 500",
        "узнать, сколько времени загружался ответ {api}",
    ],
    "Console": [
        "увидеть текст необработанной JavaScript-ошибки после клика по «{button}»",
        "выполнить JavaScript-выражение на открытой странице и посмотреть результат",
        "найти сообщение console.error, которое выводит скрипт при нажатии «{button}»",
    ],
    "Application": [
        "проверить, какие cookie и данные localStorage сохранил сайт после входа",
        "удалить cookie сессии, чтобы проверить повторный вход",
        "посмотреть содержимое sessionStorage после нажатия «{button}»",
    ],
    "Elements": [
        "посмотреть, какие CSS-правила применились к кнопке «{button}»",
        "проверить, есть ли у кнопки «{button}» атрибут disabled в DOM",
        "временно изменить текст кнопки «{button}» прямо в DOM, чтобы проверить перенос строк",
    ],
    "Performance": [
        "записать профиль, чтобы найти долгие задачи при прокрутке ленты",
        "понять, какие функции JavaScript тормозят интерфейс после нажатия «{button}»",
    ],
    "Sources": [
        "поставить точку останова в JavaScript-обработчике кнопки «{button}»",
        "пошагово выполнить скрипт, который вызывается при нажатии «{button}»",
    ],
}
DEVTOOLS_APIS = ["/api/cart", "/api/login", "/api/search", "/api/orders", "/api/profile", "/api/checkout"]
DEVTOOLS_BUTTONS = ["Купить", "Сохранить", "Отправить", "Войти", "Оформить заказ", "Применить фильтр"]


@generator("qa.devtools_tab")
def devtools_tab(rng: random.Random) -> Generated:
    tab = rng.choice(list(DEVTOOLS))
    task = rng.choice(DEVTOOLS[tab]).format(
        api=rng.choice(DEVTOOLS_APIS), button=rng.choice(DEVTOOLS_BUTTONS)
    )
    question = rng.choice(
        [
            "Какая вкладка Chrome DevTools для этого предназначена?",
            "На какой вкладке Chrome DevTools это делают?",
        ]
    )
    return Generated(
        stem=f"Нужно {task}. {question}",
        correct=(tab,),
        wrong=tuple(other for other in DEVTOOLS if other != tab),
    )


MOBILE_TOOLS = [
    (
        [
            "Посмотреть системный лог Android-устройства во время падения приложения {app}",
            "Найти стек-трейс падения приложения {app} на подключённом Android-телефоне",
        ],
        "adb logcat",
    ),
    (
        [
            "Установить сборку {app}.apk на подключённое Android-устройство",
            "Поставить тестовую сборку {app}.apk на Android-телефон из командной строки",
        ],
        "adb install {app}.apk",
    ),
    (
        [
            "Перехватить и подменить HTTPS-ответ сервера для мобильного приложения {app}",
            "Посмотреть запросы мобильного приложения {app} к API и подменить ответ сервера",
        ],
        "HTTP-прокси (Charles, Proxyman, mitmproxy) с сертификатом, установленным на устройство",
    ),
    (
        [
            "Проверить веб-версию {app} на медленном мобильном интернете в Chrome",
            "Сымитировать медленную сеть 3G для мобильной веб-версии {app} в браузере Chrome",
        ],
        "Throttling на вкладке Network в Chrome DevTools",
    ),
    (
        [
            "Посмотреть иерархию UI-элементов на экране Android-приложения {app}",
            "Выяснить, почему элемент экрана Android-приложения {app} перекрыт другим, по дереву View",
        ],
        "Layout Inspector в Android Studio",
    ),
    (
        [
            "Записать видео экрана Android-устройства с приложением {app} из командной строки",
            "Снять видео воспроизведения дефекта в {app} на Android без сторонних приложений",
        ],
        "adb shell screenrecord",
    ),
    (
        [
            "Раздать бета-сборку iOS-приложения {app} внешним тестировщикам",
            "Получить тестовую iOS-сборку {app} на iPhone до публикации в App Store",
        ],
        "TestFlight",
    ),
]
MOBILE_APPS = ["shop", "bank", "delivery", "app-release", "taxi", "fitness", "tickets"]


@generator("qa.mobile_tool")
def mobile_tool(rng: random.Random) -> Generated:
    app = rng.choice(MOBILE_APPS)
    index = rng.randrange(len(MOBILE_TOOLS))
    tasks, tool = MOBILE_TOOLS[index]
    answer = tool.format(app=app)
    wrong = [other.format(app=app) for i, (_, other) in enumerate(MOBILE_TOOLS) if i != index]
    return Generated(
        stem=f"{rng.choice(tasks).format(app=app)}. Какой инструмент для этого подходит?",
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


# --- Тест-дизайн: дополнительные генераторы ----------------------------------------------------

RANGE_FIELDS = [
    ("Возраст клиента", ("года", "лет", "лет")),
    ("Количество билетов в заказе", ("шт.", "шт.", "шт.")),
    ("Длина логина", ("символа", "символов", "символов")),
    ("Срок аренды", ("дня", "дней", "дней")),
    ("Количество гостей", ("чел.", "чел.", "чел.")),
    ("Срок кредита", ("мес.", "мес.", "мес.")),
    ("Вес посылки", ("кг", "кг", "кг")),
]


def _range_field(rng: random.Random) -> tuple[str, str, int, int]:
    """Поле, единица в форме после «до {high}» и границы диапазона."""
    field, forms = rng.choice(RANGE_FIELDS)
    low = rng.randint(2, 30)
    high = low + rng.randint(15, 90)
    return field, plural(high, *forms), low, high


@generator("qa.td_positive_negative")
def td_positive_negative(rng: random.Random) -> Generated:
    """Негативные значения — вне допустимого диапазона; значения на границах валидны."""
    field, unit, low, high = _range_field(rng)
    invalid = [low - 1, high + 1, rng.randint(high + 5, high * 3), -rng.randint(1, 10), 0]
    valid = [low, high, rng.randint(low + 2, high - 2), rng.randint(low + 2, high - 2)]
    invalid_texts = _distinct_wrong("", (str(v) for v in invalid))
    valid_texts = _distinct_wrong("", (str(v) for v in valid if str(v) not in invalid_texts))
    question = rng.choice(
        [
            "Какие тестовые значения относятся к негативным проверкам (система должна их отклонить)?",
            "Какие значения из списка должны быть отклонены системой?",
        ]
    )
    return Generated(
        stem=f"Поле «{field}» принимает целые значения от {low} до {high} {unit} включительно. {question}",
        correct=invalid_texts,
        wrong=valid_texts,
    )


@generator("qa.td_equivalence_pick")
def td_equivalence_pick(rng: random.Random) -> Generated:
    """Классы: меньше минимума, внутри диапазона, больше максимума — по одному представителю."""
    field, unit, low, high = _range_field(rng)
    below = low - rng.randint(1, min(low, 5))
    above = high + rng.randint(1, 30)
    inner = rng.sample(range(low + 1, high), 2)

    def fmt(values: list[int]) -> str:
        return "; ".join(str(v) for v in sorted(values))

    correct = fmt([below, inner[0], above])
    wrong = [
        fmt([low, inner[0], high]),
        fmt([below, above]),
        fmt([inner[0], inner[1], above]),
        fmt([below, inner[0], inner[1]]),
        fmt([below, low, inner[0], high]),
    ]
    return Generated(
        stem=(
            f"Поле «{field}» принимает целые значения от {low} до {high} {unit} включительно. Какой набор "
            "значений содержит ровно по одному представителю каждого класса эквивалентности "
            "(валидного и невалидных)? Нечисловой ввод не рассматривайте."
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.td_three_point_bva")
def td_three_point_bva(rng: random.Random) -> Generated:
    """Трёхточечный анализ: для каждой границы — она сама и соседние значения с обеих сторон."""
    field, unit, low, high = _range_field(rng)

    def fmt(values: list[int]) -> str:
        return "; ".join(str(v) for v in values)

    correct = fmt([low - 1, low, low + 1, high - 1, high, high + 1])
    wrong = [
        fmt([low - 1, low, high, high + 1]),
        fmt([low, low + 1, high - 1, high]),
        fmt([low - 2, low - 1, low, high, high + 1, high + 2]),
        fmt([low - 1, low + 1, (low + high) // 2, high - 1, high + 1]),
        fmt([low, (low + high) // 2, high]),
    ]
    return Generated(
        stem=(
            f"Поле «{field}» принимает целые значения от {low} до {high} {unit} включительно. Какой набор "
            "значений даёт трёхточечный анализ граничных значений "
            "(каждая граница и оба соседних с ней значения)?"
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


def _money(cents: int) -> str:
    return f"{cents // 100:,}".replace(",", " ") + f",{cents % 100:02d}"


@generator("qa.td_boundary_decimal")
def td_boundary_decimal(rng: random.Random) -> Generated:
    """Шаг значения — 1 копейка, поэтому соседи границы отличаются на 0,01, а не на 1."""
    low = rng.choice([rng.randrange(10, 501, 10), rng.randrange(1000, 10001, 500)]) * 100
    high = low + rng.randrange(5000, 300001, 500) * 100
    operation = rng.choice(["Сумма перевода", "Сумма пополнения", "Сумма заказа", "Сумма платежа"])

    def fmt(values: list[int]) -> str:
        return "; ".join(_money(v) for v in values)

    correct = fmt([low - 1, low, high, high + 1])
    wrong = [
        fmt([low - 100, low, high, high + 100]),
        fmt([low, low + 1, high - 1, high]),
        fmt([low - 10, low, high, high + 10]),
        fmt([low, high]),
        fmt([low - 1, low + 1, high - 1, high + 1]),
    ]
    return Generated(
        stem=(
            f"{operation} — от {_money(low)} до {_money(high)} ₽ включительно, с точностью до копеек. "
            "Какой набор значений (₽) даёт двухточечный анализ граничных значений: граница и ближайшее "
            "значение за ней?"
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


MONTHS_GEN = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


@generator("qa.td_date_boundaries")
def td_date_boundaries(rng: random.Random) -> Generated:
    """Граница по дате: соседние дни зависят от длины месяца и високосного года."""
    import datetime as dt

    year = rng.randint(2025, 2030)
    month = rng.randint(1, 12)
    start = dt.date(year, month, 1)
    span = rng.randint(0, 2)
    end_month = (month - 1 + span) % 12 + 1
    end_year = year + (month - 1 + span) // 12
    next_first = dt.date(end_year + end_month // 12, end_month % 12 + 1, 1)
    end = next_first - dt.timedelta(days=1)
    day = dt.timedelta(days=1)
    prev_start = start - day

    def fmt(dates: list[str]) -> str:
        return "; ".join(dates)

    def d(value: dt.date) -> str:
        return value.strftime("%d.%m.%Y")

    real = prev_start.day
    fake_day = {28: 29, 29: 28, 30: 31, 31: 30}[real]
    fake_prev = f"{fake_day:02d}.{prev_start.month:02d}.{prev_start.year}"
    correct = fmt([d(prev_start), d(start), d(end), d(end + day)])
    wrong = [
        fmt([d(start), d(end)]),
        fmt([d(start), d(start + day), d(end - day), d(end)]),
        fmt([fake_prev, d(start), d(end), d(end + day)]),
        fmt([d(prev_start), d(start), d(end - day), d(end)]),
    ]
    campaign = rng.choice(["Акция", "Промокод", "Льготный тариф", "Бесплатная доставка"])
    return Generated(
        stem=(
            f"{campaign} действует с {start.day} {MONTHS_GEN[start.month - 1]} {start.year} по {end.day} "
            f"{MONTHS_GEN[end.month - 1]} {end.year} включительно. Какие даты даёт двухточечный анализ "
            "граничных значений (граница и ближайший день за ней)?"
        ),
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.td_statement_coverage")
def td_statement_coverage(rng: random.Random) -> Generated:
    """Покрытие операторов: независимые if без else покрываются одним тестом, ветви цепочки — разными."""
    var = rng.choice(["amount", "age", "weight", "days", "distance"])
    conditions = rng.randint(2, 4)
    with_else = rng.random() < 0.5
    thresholds = sorted(rng.sample(range(10, 100, 5), conditions))
    chain = []
    for index, value in enumerate(thresholds):
        keyword = "if" if index == 0 else "} else if"
        chain += [f"  {keyword} ({var} < {value}) {{", f"    fee = {index + 1};"]
    if with_else:
        chain += ["  } else {", f"    fee = {conditions + 1};"]
    chain.append("  }")
    flags = rng.sample(["isVip", "hasCoupon", "isNight", "isHoliday", "isExpress"], rng.randint(1, 2))
    singles = []
    for flag in flags:
        singles += [f"  if ({flag}) {{", f"    fee += {rng.randint(2, 9)};", "  }"]
    blocks = [chain, singles]
    rng.shuffle(blocks)
    code = [f"function calcFee({', '.join([var, *flags])}) {{", "  let fee = 0;"]
    for block in blocks:
        code += block
    code += ["  return fee;", "}"]
    answer = conditions + (1 if with_else else 0)
    return Generated(
        stem=(
            "Параметры функции независимы, любые их сочетания допустимы. Какое минимальное число тестов "
            "даёт 100% покрытие операторов (statement coverage)?"
        ),
        code="\n".join(code),
        code_language="javascript",
        number=float(answer),
    )


def _decision_block(rng: random.Random, var: str, used: set[int]) -> tuple[list[str], int]:
    """Случайная управляющая конструкция и число решений (точек ветвления) в ней."""
    kind = rng.choice(["if", "if_else", "chain", "for", "while"])
    value = rng.choice([v for v in range(5, 100, 5) if v not in used])
    used.add(value)
    if kind == "if":
        return [f"  if ({var} > {value}) {{", "    score += 1;", "  }"], 1
    if kind == "if_else":
        return [f"  if ({var} > {value}) {{", "    score += 2;", "  } else {", "    score -= 1;", "  }"], 1
    if kind == "chain":
        count = rng.randint(2, 3)
        lines = []
        for index in range(count):
            keyword = "if" if index == 0 else "} else if"
            lines += [f"  {keyword} ({var} < {value + index * 10}) {{", f"    score += {index + 1};"]
        if rng.random() < 0.5:
            lines += ["  } else {", "    score = 0;"]
        lines.append("  }")
        return lines, count
    if kind == "for":
        return [f"  for (let i = 0; i < {var}; i++) {{", "    score += i;", "  }"], 1
    return [f"  while (score < {value}) {{", "    score += 7;", "  }"], 1


@generator("qa.td_cyclomatic")
def td_cyclomatic(rng: random.Random) -> Generated:
    """Цикломатическая сложность Маккейба для одной функции: число точек решения + 1."""
    variables = rng.sample(["a", "b", "count", "limit", "total"], 2)
    used: set[int] = set()
    decisions = 0
    code = [f"function score({', '.join(variables)}) {{", "  let score = 0;"]
    for _ in range(rng.randint(2, 4)):
        lines, count = _decision_block(rng, rng.choice(variables), used)
        code += lines
        decisions += count
    code += ["  return score;", "}"]
    return Generated(
        stem=(
            "Какова цикломатическая сложность (по Маккейбу) этой функции? Все условия простые, без && и ||. "
            "Она же — число независимых путей для базисного тестирования путей."
        ),
        code="\n".join(code),
        code_language="javascript",
        number=float(decisions + 1),
    )


@generator("qa.td_path_count")
def td_path_count(rng: random.Random) -> Generated:
    """Полное покрытие путей: исходы независимых последовательных блоков перемножаются (§10.2)."""
    names = rng.sample(["amount", "age", "items", "days", "weight", "distance", "score"], 4)
    code = [f"function price({', '.join(names)}) {{", "  let price = 100;"]
    total = 1
    blocks = rng.randint(2, 4)
    for index in range(blocks):
        var = names[index]
        kind = rng.choice(["if", "if_else", "chain", "chain_else"])
        if kind in {"if", "if_else"}:
            code += [f"  if ({var} > {rng.randrange(5, 100, 5)}) {{", f"    price += {rng.randint(2, 30)};"]
            if kind == "if_else":
                code += ["  } else {", f"    price -= {rng.randint(1, 9)};"]
            code.append("  }")
            total *= 2
        else:
            count = rng.randint(2, 3)
            base = rng.randrange(5, 50, 5)
            for step in range(count):
                keyword = "if" if step == 0 else "} else if"
                code += [f"  {keyword} ({var} < {base + step * 10}) {{", f"    price *= {step + 2};"]
            if kind == "chain_else":
                code += ["  } else {", "    price -= 5;"]
            code.append("  }")
            total *= count + 1
    code += ["  return price;", "}"]
    return Generated(
        stem=(
            "Параметры независимы, любые их сочетания допустимы. Сколько различных путей выполнения "
            "существует в функции, то есть сколько тестов нужно для 100% покрытия путей (path coverage)?"
        ),
        code="\n".join(code),
        code_language="javascript",
        number=float(total),
    )


SWITCH_DOMAINS = [
    ("Заказ", ["Создан", "Оплачен", "Собран", "Отправлен", "Получен"]),
    ("Заявка", ["Черновик", "Проверка", "Доработка", "Одобрена", "Архив"]),
    ("Тикет", ["Открыт", "В работе", "Ждёт ответа", "Решён", "Закрыт"]),
    ("Документ", ["Новый", "Согласование", "Правки", "Подписан", "Отозван"]),
]


@generator("qa.td_one_switch")
def td_one_switch(rng: random.Random) -> Generated:
    """Покрытие 1-switch: пары переходов t1→t2, где t2 начинается в состоянии, куда ведёт t1."""
    entity, all_states = rng.choice(SWITCH_DOMAINS)
    states = all_states[: rng.randint(4, 5)]
    pairs = [(a, b) for a in states for b in states if a != b]
    while True:
        chosen = rng.sample(pairs, rng.randint(5, 7))
        answer = sum(1 for _, dst in chosen for src, _ in chosen if src == dst)
        if answer >= 3:
            break
    listing = "; ".join(f"{src} → {dst}" for src, dst in chosen)
    return Generated(
        stem=(
            f"Объект «{entity}». Допустимые переходы: {listing}. Для покрытия 1-switch (пар переходов) "
            "нужно проверить каждую последовательность из двух допустимых переходов подряд. Сколько таких "
            "последовательностей?"
        ),
        number=float(answer),
    )


# --- API: дополнительные генераторы -------------------------------------------------------------

API_RESOURCES = [
    ("/api/v1/orders", "заказов", "заказ", "status"),
    ("/api/v1/users", "пользователей", "пользователя", "email"),
    ("/api/v1/tickets", "тикетов", "тикет", "priority"),
    ("/api/v1/products", "товаров", "товар", "price"),
    ("/api/v1/invoices", "счетов", "счёт", "due_date"),
    ("/api/v1/bookings", "бронирований", "бронирование", "guests"),
]


@generator("qa.api_method_crud")
def api_method_crud(rng: random.Random) -> Generated:
    path, plural, single, field = rng.choice(API_RESOURCES)
    item = f"{path}/{rng.randint(2, 999)}"
    scenarios = [
        (f"Получить список {plural}", "GET", path),
        (f"Создать новый объект в коллекции {plural} ({single})", "POST", path),
        (f"Полностью заменить {single} новым представлением", "PUT", item),
        (f"Изменить у объекта ({single}) только поле {field}, остальные поля не передавать", "PATCH", item),
        (f"Удалить {single}", "DELETE", item),
    ]
    text, method, target = rng.choice(scenarios)
    wrong = [f"{other} {target}" for other in ["GET", "POST", "PUT", "PATCH", "DELETE"] if other != method]
    return Generated(
        stem=f"{text}. Какой запрос соответствует принятой семантике REST API?",
        correct=(f"{method} {target}",),
        wrong=tuple(wrong),
    )


STATUS_CLASSES = {
    1: "1xx — информационный ответ",
    2: "2xx — успешная обработка",
    3: "3xx — перенаправление",
    4: "4xx — ошибка клиента",
    5: "5xx — ошибка сервера",
}
STATUS_CODES = [
    (100, "Continue"),
    (200, "OK"),
    (201, "Created"),
    (202, "Accepted"),
    (204, "No Content"),
    (301, "Moved Permanently"),
    (302, "Found"),
    (304, "Not Modified"),
    (307, "Temporary Redirect"),
    (400, "Bad Request"),
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (405, "Method Not Allowed"),
    (409, "Conflict"),
    (422, "Unprocessable Content"),
    (429, "Too Many Requests"),
    (500, "Internal Server Error"),
    (502, "Bad Gateway"),
    (503, "Service Unavailable"),
    (504, "Gateway Timeout"),
]


@generator("qa.api_status_class")
def api_status_class(rng: random.Random) -> Generated:
    code, _ = rng.choice(STATUS_CODES)
    path = rng.choice(API_RESOURCES)[0]
    stem = rng.choice(
        [
            f"Запрос к {path} вернул HTTP {code}. К какому классу относится этот код ответа?",
            f"В логе автотеста: «{path} → {code}». Что означает класс этого кода ответа?",
        ]
    )
    correct = STATUS_CLASSES[code // 100]
    return Generated(
        stem=stem,
        correct=(correct,),
        wrong=tuple(label for key, label in STATUS_CLASSES.items() if key != code // 100),
    )


API_HEADERS = [
    ("Сообщить серверу, что тело запроса к {path} передаётся в JSON", "Content-Type"),
    ("Указать, в каком формате клиент хочет получить ответ от {path}", "Accept"),
    ("Передать токен доступа при запросе к {path}", "Authorization"),
    ("Узнать из ответа 201 на POST {path}, по какому адресу доступен созданный ресурс", "Location"),
    ("Узнать из ответа 429 от {path}, через сколько секунд можно повторить запрос", "Retry-After"),
    ("Запретить промежуточным узлам и браузеру кешировать ответ {path}", "Cache-Control"),
    ("Передать серверу cookie сессии вместе с запросом к {path}", "Cookie"),
    ("Сохранить в браузере cookie, которую сервер выдал в ответе {path}", "Set-Cookie"),
]


@generator("qa.api_header_purpose")
def api_header_purpose(rng: random.Random) -> Generated:
    index = rng.randrange(len(API_HEADERS))
    text, header = API_HEADERS[index]
    path = rng.choice(API_RESOURCES)[0]
    return Generated(
        stem=f"{text.format(path=path)}. Какой HTTP-заголовок для этого используется?",
        correct=(header,),
        wrong=tuple(other for i, (_, other) in enumerate(API_HEADERS) if i != index),
    )


@generator("qa.api_pagination")
def api_pagination(rng: random.Random) -> Generated:
    path, items, _, _ = rng.choice(API_RESOURCES)
    size = rng.choice([10, 20, 25, 50])
    full = rng.randint(3, 40)
    rest = rng.randint(1, size - 1)
    total = full * size + rest
    if rng.random() < 0.5:
        stem = (
            f"GET {path}?limit={size}&offset=0 возвращает поле total = {total}. "
            f"Сколько запросов с limit={size} "
            f"понадобится, чтобы получить всю коллекцию {items}?"
        )
        answer = full + 1
    else:
        stem = (
            f"Всего {items}: {total}, API отдаёт их страницами по {size} (page=1, 2, …). Сколько записей "
            "вернётся на последней странице?"
        )
        answer = rest
    return Generated(stem=stem, number=float(answer))


# --- pytest и JUnit: дополнительные генераторы -------------------------------------------------

PYTEST_SUBJECTS = ["login", "cart", "search", "payment", "profile", "checkout", "export", "filter"]


@generator("qa.pytest_discovery")
def pytest_discovery(rng: random.Random) -> Generated:
    """Правила сбора по умолчанию: функции test*, методы test* в классах Test* без __init__."""
    subjects = rng.sample(PYTEST_SUBJECTS, 6)
    cls = rng.choice(["Cart", "Api", "Order", "User"])
    collected = [
        f"test_{subjects[0]}",
        f"test_{subjects[1]}_negative",
        f"Test{cls}.test_{subjects[2]}",
        f"Test{cls}.test_{subjects[3]}_empty",
    ]
    skipped = [
        f"check_{subjects[4]}",
        f"{subjects[5]}_test",
        f"{cls}Tests.test_{subjects[2]}",
        f"Test{cls}.verify_{subjects[4]}",
        f"helper_{subjects[0]}",
    ]
    module = f"test_{rng.choice(['api', 'ui', 'orders', 'smoke'])}.py"
    return Generated(
        stem=(
            f"В файле {module} объявлены функции и методы классов (в вариантах — «Класс.метод»), "
            "у классов нет "
            "__init__, настройки pytest по умолчанию. Какие из перечисленных pytest соберёт как тесты?"
        ),
        correct=tuple(collected),
        wrong=tuple(skipped),
    )


@generator("qa.requests_ok")
def requests_ok(rng: random.Random) -> Generated:
    """requests не бросает исключение на 4xx/5xx; response.ok — True при коде < 400."""
    code = rng.choice([200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503])
    method = rng.choice(["get", "post", "delete"])
    path = rng.choice(["orders/7", "users/me", "cart", "tickets/42", "invoices"])
    ok = code < 400
    if rng.random() < 0.5:
        line = "print(r.status_code, r.ok)"
        correct = f"{code} {ok}"
        wrong = [f"{code} {not ok}", "Исключение requests.exceptions.HTTPError", f"{code} None"]
    else:
        line = "print(r.ok)"
        correct = str(ok)
        wrong = [str(not ok), "Исключение requests.exceptions.HTTPError", f"{code}"]
    code_text = "\n".join(
        ["import requests", "", f'r = requests.{method}("https://api.example.com/{path}")', line]
    )
    return Generated(
        stem=f"Сервер отвечает на этот запрос кодом {code}. Что выведет код?",
        code=code_text,
        code_language="python",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.pytest_outcomes")
def pytest_outcomes(rng: random.Random) -> Generated:
    """Не-strict xfail: падение — xfailed, успех — xpassed; strict=True делает XPASS провалом."""
    markers = [
        "",
        '@pytest.mark.skip(reason="TODO")',
        "@pytest.mark.xfail",
        "@pytest.mark.xfail(strict=True)",
    ]
    while True:
        tests = [(rng.choice(markers), rng.random() < 0.5) for _ in range(rng.randint(5, 7))]
        if any(m == "@pytest.mark.xfail" and passes for m, passes in tests) and any(
            m.startswith("@pytest.mark.xfail") and not passes for m, passes in tests
        ):
            break
    lines = ["import pytest", ""]
    failed = passed = 0
    for index, (marker, passes) in enumerate(tests):
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        expected = a + b if passes else a + b + 1
        if marker:
            lines.append(marker)
        lines += [f"def test_case_{index + 1}():", f"    assert {a} + {b} == {expected}", ""]
        if marker.startswith("@pytest.mark.skip"):
            continue
        if marker == "":
            failed += not passes
            passed += passes
        elif marker == "@pytest.mark.xfail(strict=True)" and passes:
            failed += 1
    ask_failed = rng.random() < 0.5
    word = "failed" if ask_failed else "passed"
    return Generated(
        stem=(
            "Файл запускается командой pytest, конфигурация по умолчанию (xfail_strict не задан). "
            f"Какое число будет у {word} в итоговой строке отчёта?"
        ),
        code="\n".join(lines).rstrip(),
        code_language="python",
        number=float(failed if ask_failed else passed),
    )


@generator("qa.pytest_fixture_override")
def pytest_fixture_override(rng: random.Random) -> Generated:
    """Фикстура с тем же именем ближе к тесту переопределяет внешнюю: модуль > conftest пакета > корень."""
    name = rng.choice(["user", "base_url", "client", "config"])
    values = rng.sample(["root", "api", "ui", "local", "stage", "prod", "mock"], 3)
    root, nested, module_value = values
    sub = rng.choice(["api", "web", "mobile"])
    other = rng.choice(["admin", "reports", "smoke"])
    scenario = rng.choice(["nested", "sibling", "module"])
    lines = [
        "# tests/conftest.py",
        "@pytest.fixture",
        f'def {name}(): return "{root}"',
        "",
        f"# tests/{sub}/conftest.py",
        "@pytest.fixture",
        f'def {name}(): return "{nested}"',
        "",
    ]
    if scenario == "nested":
        target = f"tests/{sub}/test_main.py"
        lines += [f"# {target}", f"def test_it({name}): print({name})"]
        answer = nested
    elif scenario == "sibling":
        target = f"tests/{other}/test_main.py"
        lines += [f"# {target}", f"def test_it({name}): print({name})"]
        answer = root
    else:
        target = f"tests/{sub}/test_main.py"
        lines += [
            f"# {target}",
            "@pytest.fixture",
            f'def {name}(): return "{module_value}"',
            "",
            f"def test_it({name}): print({name})",
        ]
        answer = module_value
    wrong = [v for v in values if v != answer] + [
        f"Ошибка: фикстура {name} определена несколько раз",
    ]
    return Generated(
        stem=f"Что выведет тест из {target} при запуске pytest -s из корня проекта?",
        code="\n".join(lines),
        code_language="python",
        correct=(answer,),
        wrong=tuple(wrong),
    )


@generator("qa.junit_assert_message")
def junit_assert_message(rng: random.Random) -> Generated:
    """assertEquals(expected, actual): первым аргументом идёт ожидаемое значение."""
    getter = rng.choice(["cart.size()", "order.getTotal()", "page.count()", "report.rows()"])
    expected, actual = rng.sample(range(1, 60), 2)
    reversed_args = rng.random() < 0.5
    call = f"assertEquals({getter}, {expected});" if reversed_args else f"assertEquals({expected}, {getter});"
    first, second = (actual, expected) if reversed_args else (expected, actual)
    correct = f"expected: <{first}> but was: <{second}>"
    wrong = [
        f"expected: <{second}> but was: <{first}>",
        f"expected: <{first}> but was: <{first}>",
        "Тест пройдёт: assertEquals сравнивает значения без учёта порядка аргументов",
        f"expected: <{getter}> but was: <{second}>",
    ]
    test = rng.choice(["countsItems", "calculatesTotal", "returnsPage", "keepsState"])
    code = "\n".join(["@Test", f"void {test}() {{", f"    {call}", "}"])
    return Generated(
        stem=f"{getter} возвращает {actual}. Какое сообщение об ошибке покажет JUnit 5?",
        code=code,
        code_language="java",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.junit_assert_all")
def junit_assert_all(rng: random.Random) -> Generated:
    """Обычные assert* останавливают тест на первом провале; assertAll выполняет все и сообщает о всех."""
    order_id = rng.randint(1, 999)
    status = rng.choice(["PAID", "NEW", "SHIPPED"])
    total = rng.randrange(500, 9001, 100)
    items = rng.randint(1, 9)
    fields = [
        ("order.getId()", str(order_id), str(order_id + rng.randint(1, 5))),
        (
            "order.getStatus()",
            f'"{status}"',
            f'"{rng.choice([s for s in ["PAID", "NEW", "SHIPPED"] if s != status])}"',
        ),
        ("order.getTotal()", str(total), str(total + 100)),
        ("order.getItems()", str(items), str(items + 1)),
    ]
    while True:
        fails = [rng.random() < 0.5 for _ in fields]
        if sum(fails) >= 2:
            break
    checks = [
        f"assertEquals({bad if fail else good}, {getter})"
        for (getter, good, bad), fail in zip(fields, fails, strict=True)
    ]
    grouped = rng.random() < 0.5
    lines = [
        "@Test",
        "void orderIsCorrect() {",
        f'    Order order = new Order({order_id}, "{status}", {total}, {items});',
    ]
    if grouped:
        lines.append("    assertAll(")
        lines += [
            f"        () -> {check}{',' if i < len(checks) - 1 else ''}" for i, check in enumerate(checks)
        ]
        lines.append("    );")
        answer = sum(fails)
    else:
        lines += [f"    {check};" for check in checks]
        answer = 1
    lines.append("}")
    return Generated(
        stem=(
            "Конструктор Order(id, status, total, items) сохраняет значения, геттеры их возвращают. Сколько "
            "несовпадений значений JUnit 5 сообщит в отчёте об этом тесте?"
        ),
        code="\n".join(lines),
        code_language="java",
        number=float(answer),
    )


JUNIT_MIGRATION = [
    ("@Before", "@BeforeEach"),
    ("@After", "@AfterEach"),
    ("@BeforeClass", "@BeforeAll"),
    ("@AfterClass", "@AfterAll"),
    ("@Ignore", "@Disabled"),
    ("@Test(expected = IllegalStateException.class)", "assertThrows(IllegalStateException.class, () -> ...)"),
    ("@RunWith(MockitoJUnitRunner.class)", "@ExtendWith(MockitoExtension.class)"),
    ("@Category(SlowTests.class)", '@Tag("slow")'),
]


@generator("qa.junit_migration")
def junit_migration(rng: random.Random) -> Generated:
    index = rng.randrange(len(JUNIT_MIGRATION))
    old, new = JUNIT_MIGRATION[index]
    cls = rng.choice(["CartTest", "LoginTest", "PaymentApiTest", "SearchTest", "ProfileTest", "OrderDaoTest"])
    return Generated(
        stem=f"Класс {cls} переводят с JUnit 4 на JUnit 5. Чем заменить {old}?",
        correct=(new,),
        wrong=tuple(other for i, (_, other) in enumerate(JUNIT_MIGRATION) if i != index),
    )


# --- SQL: дополнительные генераторы -------------------------------------------------------------

PRODUCT_NAMES = ["Чайник", "Лампа", "Кресло", "Плед", "Кружка", "Термос", "Рюкзак", "Зонт", "Коврик", "Часы"]


@generator("qa.sql_order_limit")
def sql_order_limit(rng: random.Random) -> Generated:
    names = rng.sample(PRODUCT_NAMES, rng.randint(6, 7))
    prices = rng.sample(range(300, 9001, 100), len(names))
    rows = [[i + 1, n, p] for i, (n, p) in enumerate(zip(names, prices, strict=True))]
    limit = rng.randint(2, 3)
    direction = rng.choice(["DESC", "ASC"])
    by_price = sorted(rows, key=lambda r: r[2], reverse=direction == "DESC")
    opposite = sorted(rows, key=lambda r: r[2], reverse=direction != "DESC")

    def names_of(selected: list[list[object]]) -> str:
        return ", ".join(str(r[1]) for r in selected)

    correct = names_of(by_price[:limit])
    wrong = [
        names_of(opposite[:limit]),
        names_of(rows[:limit]),
        names_of(by_price[: limit + 1]),
        names_of(list(reversed(by_price[:limit]))),
        names_of(by_price[-limit:]),
    ]
    code = _table("products", ["id", "name", "price"], rows)
    code += f"\n\nSELECT name FROM products ORDER BY price {direction} LIMIT {limit};"
    return Generated(
        stem="Что вернёт запрос (строки по порядку)?",
        code=code,
        code_language="sql",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.sql_count_distinct")
def sql_count_distinct(rng: random.Random) -> Generated:
    """COUNT(DISTINCT col) считает различные значения, NULL не учитывается."""
    column, values = rng.choice(
        [("city", ["Казань", "Омск", "Тула", "Пермь", "Сочи"]), ("plan", ["free", "pro", "team", "business"])]
    )
    while True:
        rows = [
            [i + 1, None if rng.random() < 0.25 else rng.choice(values[: rng.randint(2, len(values))])]
            for i in range(rng.randint(7, 9))
        ]
        present = [r[1] for r in rows if r[1] is not None]
        if any(r[1] is None for r in rows) and len(present) > len(set(present)) and len(set(present)) >= 2:
            break
    code = _table("customers", ["id", column], rows)
    code += f"\n\nSELECT COUNT(DISTINCT {column}) FROM customers;"
    return Generated(
        stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(len(set(present)))
    )


@generator("qa.sql_inner_join_count")
def sql_inner_join_count(rng: random.Random) -> Generated:
    """INNER JOIN оставляет только пары с совпадением ключа; строки без пары отбрасываются с обеих сторон."""
    while True:
        users = _users(rng)
        ids = [row[0] for row in users]
        orders = _orders(rng, rng.randint(6, 8), ids + [len(ids) + 1, len(ids) + 2])
        matched = sum(1 for o in orders if o[1] in ids)
        if matched < len(orders) and any(all(o[1] != uid for o in orders) for uid in ids):
            break
    code = _table("users", ["id", "name"], users) + "\n\n"
    code += _table("orders", ["id", "user_id", "status", "amount"], orders)
    code += "\n\nSELECT u.name, o.amount\nFROM users u\nJOIN orders o ON o.user_id = u.id;"
    return Generated(
        stem="Сколько строк вернёт запрос?", code=code, code_language="sql", number=float(matched)
    )


@generator("qa.sql_not_in_null")
def sql_not_in_null(rng: random.Random) -> Generated:
    """x NOT IN (…, NULL) никогда не TRUE: при NULL в подзапросе результат пуст."""
    while True:
        users = _users(rng)
        ids = [row[0] for row in users]
        orders = []
        for index in range(rng.randint(5, 7)):
            user = None if index == 0 else rng.choice(ids)
            orders.append([index + 1, user, rng.choice(["paid", "new", "cancelled"])])
        rng.shuffle(orders)
        for index, row in enumerate(orders):
            row[0] = index + 1
        status = rng.choice(["paid", "new", "cancelled"])
        selected = [o for o in orders if o[2] == status]
        null_inside = any(o[1] is None for o in selected)
        without = sum(1 for uid in ids if all(o[1] != uid for o in selected))
        if selected and without >= 1:
            break
    answer = 0 if null_inside else without
    code = _table("users", ["id", "name"], users) + "\n\n"
    code += _table("orders", ["id", "user_id", "status"], orders)
    code += (
        "\n\nSELECT COUNT(*)\nFROM users\nWHERE id NOT IN (\n"
        f"  SELECT user_id FROM orders WHERE status = '{status}'\n);"
    )
    return Generated(stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(answer))


# --- Процессы: дополнительные генераторы --------------------------------------------------------

TEST_LEVELS = {
    "unit": "Модульное (компонентное, unit)",
    "integration": "Интеграционное",
    "system": "Системное",
    "acceptance": "Приёмочное",
}
TEST_LEVEL_SCENARIOS = [
    (
        "Разработчик проверяет функцию {func}() отдельно от остального кода, зависимости заменены заглушками",
        "unit",
    ),
    ("Тесты вызывают метод класса {cls} напрямую и проверяют результат без запуска приложения", "unit"),
    (
        "Проверяется, что сервис {service} корректно обменивается данными с сервисом {other} через API",
        "integration",
    ),
    (
        "Проверяется, что модуль {service} правильно сохраняет данные в базу и читает их обратно",
        "integration",
    ),
    (
        "Полностью собранная система {product} проверяется на стенде, близком к продакшену, на соответствие "
        "требованиям",
        "system",
    ),
    ("Команда QA проверяет сквозные сценарии {product} целиком, от регистрации до оплаты", "system"),
    ("Заказчик проверяет, решает ли {product} его бизнес-задачи, и решает, принимать ли релиз", "acceptance"),
    (
        "Будущие пользователи {product} проверяют систему в реальных сценариях перед вводом в эксплуатацию",
        "acceptance",
    ),
]


@generator("qa.test_level")
def test_level(rng: random.Random) -> Generated:
    text, answer = rng.choice(TEST_LEVEL_SCENARIOS)
    services = rng.sample(["заказов", "оплаты", "доставки", "уведомлений", "каталога", "авторизации"], 2)
    stem = text.format(
        func=rng.choice(["calc_discount", "parse_date", "validate_email", "round_price"]),
        cls=rng.choice(["PriceCalculator", "DateParser", "CartService", "TaxRules"]),
        service=services[0],
        other=services[1],
        product=rng.choice(["CRM-системы", "интернет-магазина", "мобильного банка", "сервиса бронирования"]),
    )
    wrong = [label for key, label in TEST_LEVELS.items() if key != answer] + [
        "Регрессионное",
        "Дымовое (smoke)",
    ]
    return Generated(
        stem=f"{stem}. Какой это уровень тестирования?",
        correct=(TEST_LEVELS[answer],),
        wrong=tuple(wrong),
    )


TEST_ARTIFACTS = [
    ("Пошаговое описание проверки {feature}: предусловия, шаги, ожидаемый результат", "Тест-кейс"),
    ("Список коротких пунктов «что проверить» для {feature} без детальных шагов", "Чек-лист"),
    (
        "Документ с объёмом, подходом, ресурсами, графиком и критериями начала "
        "и окончания тестирования {feature}",
        "Тест-план",
    ),
    (
        "Описание проблемы, найденной в функции {feature}: шаги воспроизведения, ожидаемый и фактический "
        "результат",
        "Баг-репорт",
    ),
    ("Набор тест-кейсов {feature}, сгруппированных для совместного запуска", "Тестовый набор (test suite)"),
    (
        "Таблица связи требований к функции {feature} с тест-кейсами, которые их проверяют",
        "Матрица трассируемости",
    ),
    (
        "Итоговый документ о результатах тестирования {feature}: что проверено, найденные дефекты, риски",
        "Отчёт о тестировании",
    ),
]


@generator("qa.test_artifact")
def test_artifact(rng: random.Random) -> Generated:
    index = rng.randrange(len(TEST_ARTIFACTS))
    text, name = TEST_ARTIFACTS[index]
    feature = rng.choice(
        ["оплаты", "регистрации", "поиска", "корзины", "личного кабинета", "экспорта отчётов"]
    )
    return Generated(
        stem=f"{text.format(feature=feature)}. Как называется этот артефакт тестирования?",
        correct=(name,),
        wrong=tuple(other for i, (_, other) in enumerate(TEST_ARTIFACTS) if i != index),
    )


# --- Нагрузка: дополнительные генераторы --------------------------------------------------------

PERF_TERMS = [
    ("Число запросов, которые {nom} обрабатывает за секунду", "Пропускная способность (throughput, RPS)"),
    ("Время от отправки запроса к {dat} до получения полного ответа", "Время отклика (response time)"),
    ("Доля запросов к {dat}, завершившихся ошибкой", "Процент ошибок (error rate)"),
    (
        "Значение, быстрее которого обработаны 95% запросов к {dat}",
        "95-й перцентиль времени отклика (p95)",
    ),
    ("Пауза между действиями виртуального пользователя {gen}, имитирующая чтение страницы", "Think time"),
    ("Постепенное увеличение числа виртуальных пользователей {gen} в начале теста", "Ramp-up"),
    (
        "Число пользователей, одновременно выполняющих запросы к {dat}",
        "Конкурентность (concurrent users)",
    ),
]
# сервис в именительном, родительном и дательном падежах
PERF_SERVICES = [
    ("сервис поиска", "сервиса поиска", "сервису поиска"),
    ("API каталога", "API каталога", "API каталога"),
    ("сервис оплаты", "сервиса оплаты", "сервису оплаты"),
    ("сайт магазина", "сайта магазина", "сайту магазина"),
    ("сервис авторизации", "сервиса авторизации", "сервису авторизации"),
]


@generator("qa.perf_metric_term")
def perf_metric_term(rng: random.Random) -> Generated:
    index = rng.randrange(len(PERF_TERMS))
    text, term = PERF_TERMS[index]
    nom, gen, dat = rng.choice(PERF_SERVICES)
    filled = text.format(nom=nom, gen=gen, dat=dat)
    return Generated(
        stem=f"{filled}. Как называется эта характеристика нагрузочного теста?",
        correct=(term,),
        wrong=tuple(other for i, (_, other) in enumerate(PERF_TERMS) if i != index),
    )


@generator("qa.perf_throughput")
def perf_throughput(rng: random.Random) -> Generated:
    rps = rng.randrange(20, 1501, 10)
    minutes = rng.choice([2, 5, 10, 15, 20, 30])
    total = rps * minutes * 60
    service = rng.choice(["поиска", "каталога", "авторизации", "корзины"])
    if rng.random() < 0.5:
        stem = (
            f"За {minutes} мин нагрузочного теста сервис {service} обработал {total} запросов с равномерной "
            "интенсивностью. Какова пропускная способность в запросах в секунду (RPS)?"
        )
        answer = rps
    else:
        stem = (
            f"Сервис {service} стабильно обрабатывает {rps} запросов в секунду. "
            "Сколько запросов он обработает "
            f"за {minutes} мин теста?"
        )
        answer = total
    return Generated(stem=stem, number=float(answer))


@generator("qa.perf_error_budget")
def perf_error_budget(rng: random.Random) -> Generated:
    """Бюджет ошибок = число запросов × (100% − SLO); unit = 1 / (100% − SLO)."""
    slo, unit = rng.choice([("99", 100), ("99,5", 200), ("99,9", 1000), ("99,95", 2000)])
    total = unit * rng.randint(5, 400) * 10
    budget = total // unit
    service = rng.choice(["API оплаты", "сервиса поиска", "личного кабинета", "API каталога"])
    return Generated(
        stem=(
            f"SLO {service}: не менее {slo}% успешных запросов за месяц. Ожидается {total} запросов. Какое "
            "максимальное число запросов может завершиться ошибкой, чтобы SLO был выполнен?"
        ),
        number=float(budget),
    )


@generator("qa.perf_apdex")
def perf_apdex(rng: random.Random) -> Generated:
    """Apdex = (довольные + терпящие / 2) / все; довольные ≤ T, терпящие ≤ 4T."""
    threshold = rng.choice([200, 300, 500])
    values: list[int] = []
    for _ in range(rng.choice([10, 12, 16, 20])):
        zone = rng.choices(["s", "t", "f"], weights=[5, 3, 2])[0]
        if zone == "s":
            values.append(rng.randrange(40, threshold + 1, 10))
        elif zone == "t":
            values.append(rng.randrange(threshold + 10, 4 * threshold + 1, 10))
        else:
            values.append(rng.randrange(4 * threshold + 10, 6 * threshold + 1, 10))
    satisfied = sum(v <= threshold for v in values)
    tolerating = sum(threshold < v <= 4 * threshold for v in values)
    answer = round((satisfied + tolerating / 2) / len(values), 2)
    return Generated(
        stem=(
            f"Время ответа {len(values)} запросов (мс): {', '.join(map(str, values))}. Посчитайте Apdex с "
            f"порогом T = {threshold} мс: довольные — ответ не дольше T, "
            "терпящие — дольше T, но не дольше 4T, "
            "остальные — недовольные; Apdex = (довольные + терпящие / 2) / всего. Округлите до сотых."
        ),
        number=float(answer),
        tolerance=0.01,
    )


# --- Веб и мобильные: дополнительные генераторы -------------------------------------------------

MOBILE_BASICS = [
    ("Формат установочного файла Android-приложения {app} для ручной установки сборки", ".apk"),
    ("Формат файла сборки iOS-приложения {app}", ".ipa"),
    (
        "Формат, в котором Android-приложение {app} загружают в Google Play для публикации",
        ".aab (Android App Bundle)",
    ),
    ("Сервис Apple для раздачи бета-сборок приложения {app} тестировщикам", "TestFlight"),
    ("Консольная утилита для установки сборок приложения {app} и чтения логов на Android-устройстве", "adb"),
    ("Среда разработки Apple, в состав которой входит симулятор iOS для запуска приложения {app}", "Xcode"),
    (
        "Виртуальное Android-устройство из Android Studio для запуска приложения {app}",
        "AVD (Android Virtual Device)",
    ),
]


@generator("qa.mobile_basics")
def mobile_basics(rng: random.Random) -> Generated:
    index = rng.randrange(len(MOBILE_BASICS))
    text, answer = MOBILE_BASICS[index]
    app = rng.choice(["сервиса такси", "банка", "службы доставки", "фитнес-трекера"])
    return Generated(
        stem=f"{text.format(app=app)}. Что это?",
        correct=(answer,),
        wrong=tuple(other for i, (_, other) in enumerate(MOBILE_BASICS) if i != index),
    )


WEB_STORAGE = [
    ("Данные {site} удаляются, когда пользователь закрывает вкладку", "sessionStorage"),
    (
        "Данные {site} сохраняются после перезапуска браузера и не отправляются на сервер автоматически",
        "localStorage",
    ),
    ("Значение автоматически отправляется на сервер {site} с каждым запросом к его домену", "Cookie"),
    ("Чтение значения из JavaScript на страницах {site} можно запретить флагом HttpOnly", "Cookie"),
    ("Асинхронное хранилище {site} для больших объёмов структурированных данных с индексами", "IndexedDB"),
]


@generator("qa.web_storage")
def web_storage(rng: random.Random) -> Generated:
    text, answer = rng.choice(WEB_STORAGE)
    site = rng.choice(
        ["интернет-магазина", "онлайн-банка", "новостного сайта", "сервиса бронирования", "онлайн-школы"]
    )
    options = ["sessionStorage", "localStorage", "Cookie", "IndexedDB", "Cache Storage"]
    return Generated(
        stem=f"{text.format(site=site)}. О каком механизме хранения в браузере речь?",
        correct=(answer,),
        wrong=tuple(o for o in options if o != answer),
    )


# --- Базовые задания уровня Intern: открытый числовой ответ без угадывания ---

BUG_SEVERITIES = ["critical", "major", "minor"]
BUG_TITLES = ["login", "cart", "search", "payment", "profile", "export", "upload", "filter", "logout"]


@generator("qa.sql_severity_count")
def sql_severity_count(rng: random.Random) -> Generated:
    """COUNT(*) с одним условием равенства на маленькой таблице."""
    while True:
        titles = rng.sample(BUG_TITLES, rng.randint(6, 8))
        rows = [[i + 1, title, rng.choice(BUG_SEVERITIES)] for i, title in enumerate(titles)]
        severity = rng.choice(BUG_SEVERITIES)
        answer = sum(1 for row in rows if row[2] == severity)
        if 2 <= answer <= len(rows) - 2:
            break
    code = _table("bugs", ["id", "module", "severity"], rows)
    code += f"\n\nSELECT COUNT(*) FROM bugs WHERE severity = '{severity}';"
    return Generated(stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(answer))


API_FLAGS = [
    ("users", "active", "name", ["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Зоя", "Илья", "Лена"]),
    ("users", "verified", "name", ["Анна", "Борис", "Вера", "Глеб", "Дина", "Егор", "Зоя", "Илья", "Лена"]),
    (
        "products",
        "available",
        "title",
        ["Чайник", "Лампа", "Стул", "Мышь", "Кресло", "Плед", "Кружка", "Полка"],
    ),
    (
        "tasks",
        "completed",
        "title",
        ["Ревью", "Деплой", "Тесты", "Отчёт", "Макет", "Релиз", "Миграция", "Звонок"],
    ),
]


@generator("qa.json_flag_count")
def json_flag_count(rng: random.Random) -> Generated:
    """Считаем объекты массива с полем, равным true."""
    resource, flag, label, values = rng.choice(API_FLAGS)
    names = rng.sample(values, rng.randint(5, 7))
    truthy = rng.randint(2, len(names) - 2)
    flags = [True] * truthy + [False] * (len(names) - truthy)
    rng.shuffle(flags)
    data = [
        {"id": rng.randint(10, 99) * 10 + i, label: name, flag: value}
        for i, (name, value) in enumerate(zip(names, flags, strict=True))
    ]
    code = json.dumps({"data": data}, ensure_ascii=False, indent=2)
    stem = (
        f"Запрос GET /api/{resource} вернул 200 OK с таким телом. "
        f'Сколько объектов в массиве data имеют "{flag}": true?'
    )
    return Generated(stem=stem, code=code, code_language="json", number=float(truthy))


# --- Senior: метаморфное тестирование, условные запросы, rate limit, фикстуры, JUnit, SQL ---------

METAMORPHIC_DOMAINS = [
    (
        "поиска товаров с фильтрами",
        [
            "Добавление ещё одного фильтра к запросу не увеличивает число найденных товаров",
            "Перестановка порядка применения фильтров не меняет набор результатов",
            "Повторный запрос с теми же параметрами при неизменном каталоге возвращает тот же набор товаров",
        ],
        [
            "Ослабление фильтра (расширение диапазона цены) уменьшает число результатов",
            "Смена сортировки с цены на рейтинг меняет число найденных товаров",
            "Результаты с фильтром «цена ≤ X» совпадают с результатами без фильтра",
        ],
    ),
    (
        "сервиса кратчайших маршрутов по дорожному графу",
        [
            "Расстояние A→B не больше суммы расстояний A→C и C→B",
            "Добавление новой дороги не увеличивает длину кратчайшего пути A→B",
            "Если каждая дорога двусторонняя и одной длины в обе стороны, расстояние A→B равно B→A",
        ],
        [
            "Удаление любой дороги не меняет длину кратчайшего пути A→B",
            "Увеличение длины любой дороги увеличивает длину кратчайшего пути A→B",
            "Расстояние A→B всегда меньше расстояния A→C, если C дальше от A по прямой",
        ],
    ),
    (
        "функции сортировки списка чисел",
        [
            "Сортировка любой перестановки входа даёт тот же результат",
            "Повторная сортировка результата не меняет его",
            "Результат содержит те же элементы с теми же кратностями, что и вход",
        ],
        [
            "Сортировка входа, записанного в обратном порядке, даёт результат в обратном порядке",
            "Первый элемент результата совпадает с первым элементом входа",
            "Добавление нового элемента не меняет позицию прежнего максимума",
        ],
    ),
    (
        "калькулятора аннуитетного платежа по кредиту со ставкой больше нуля",
        [
            "Увеличение суммы кредита при прочих равных не уменьшает ежемесячный платёж",
            "Увеличение ставки при прочих равных не уменьшает ежемесячный платёж",
            "Удвоение суммы кредита при прочих равных удваивает ежемесячный платёж",
        ],
        [
            "Увеличение срока кредита увеличивает ежемесячный платёж",
            "Удвоение срока кредита ровно вдвое уменьшает ежемесячный платёж",
            "При сроке больше года платёж не зависит от ставки",
        ],
    ),
]


@generator("qa.metamorphic_relations")
def metamorphic_relations(rng: random.Random) -> Generated:
    """Метаморфное тестирование: проверяются отношения между выходами связанных входов, когда оракула нет."""
    domain, correct, wrong = rng.choice(METAMORPHIC_DOMAINS)
    stem = rng.choice(
        [
            f"Для {domain} нет эталонных ожидаемых значений на больших входах (проблема тестового оракула). "
            "Какие метаморфные отношения корректны и годятся для автоматической проверки?",
            f"Тестируете реализацию {domain}: ожидаемый результат для случайных входов неизвестен, "
            "поэтому применяют метаморфное тестирование. Какие отношения между запусками верны всегда?",
        ]
    )
    return Generated(stem=stem, correct=tuple(correct), wrong=tuple(wrong))


def _etag(rng: random.Random) -> str:
    return '"' + "".join(rng.choice("0123456789abcdef") for _ in range(6)) + '"'


@generator("qa.etag_sequence")
def etag_sequence(rng: random.Random) -> Generated:
    """Условные запросы: If-None-Match совпал → 304; If-Match не совпал → 412; запись без условия на сервере,
    требующем условные запросы, → 428 (RFC 9110, RFC 6585)."""
    resource = rng.choice(["/orders/17", "/profiles/me", "/carts/42", "/documents/9", "/tariffs/3"])
    versions = [_etag(rng)]
    known = {"A": versions[0], "B": versions[0]}
    lines = [
        f"Ресурс {resource}, текущий ETag {versions[0]}. Оба клиента уже прочитали его и знают этот ETag.",
        "Сервер требует условные запросы для изменений (иначе 428).",
    ]
    statuses: list[int] = []
    naive: list[int] = []
    conflict: list[int] = []
    gets: set[int] = set()
    while True:
        lines, statuses, naive, conflict, gets = lines[:2], [], [], [], set()
        versions = versions[:1]
        known = {"A": versions[0], "B": versions[0]}
        current = versions[0]
        for step in range(5):
            client = rng.choice("AB")
            action = rng.choice(["put", "put", "get", "get", "put_plain"]) if step else "put"
            tag = known[client]
            if action == "put":
                lines.append(f"{step + 1}) {client}: PUT {resource}, If-Match: {tag}")
                if tag == current:
                    current = _etag(rng)
                    versions.append(current)
                    known[client] = current
                    statuses.append(200)
                    lines[-1] += f" → новый ETag {current}"
                    naive.append(200)
                    conflict.append(200)
                else:
                    statuses.append(412)
                    naive.append(200)
                    conflict.append(409)
            elif action == "get":
                gets.add(step)
                lines.append(f"{step + 1}) {client}: GET {resource}, If-None-Match: {tag}")
                if tag == current:
                    statuses.append(304)
                    naive.append(304)
                    conflict.append(304)
                else:
                    statuses.append(200)
                    known[client] = current
                    naive.append(304)
                    conflict.append(200)
            else:
                lines.append(f"{step + 1}) {client}: PUT {resource} без заголовков условия")
                statuses.append(428)
                naive.append(200)
                conflict.append(400)
        if 412 in statuses and len(set(statuses)) >= 3:
            break
    correct = " ".join(map(str, statuses))
    swapped = [{304: 200, 200: 304}.get(s, s) if i in gets else s for i, s in enumerate(statuses)]
    wrong = [" ".join(map(str, v)) for v in (naive, conflict, swapped)]
    wrong.append(" ".join(str(409 if s == 412 else 412 if s == 428 else s) for s in statuses))
    wrong.append(" ".join(str(s if s != 412 else 200) for s in statuses))
    return Generated(
        stem="Запросы выполняются по порядку. Какие коды ответа вернёт сервер на шаги 1–5 (через пробел)?",
        code="\n".join(lines),
        code_language="text",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.token_bucket")
def token_bucket(rng: random.Random) -> Generated:
    """Token bucket: ёмкость — допустимый всплеск, пополнение — средняя скорость; ответ считаем симуляцией."""
    capacity = rng.choice([5, 8, 10, 12, 20])
    rate = rng.choice([1, 2, 4, 5])
    bursts: list[tuple[int, int]] = []
    moment = 0
    for index in range(4):
        if index:
            moment += rng.randint(1, 4)
        bursts.append((moment, rng.randint(capacity // 2, capacity + rate * 3)))
    tokens, last, rejected, accepted = float(capacity), 0, 0, 0
    for at, count in bursts:
        tokens = min(capacity, tokens + (at - last) * rate)
        last = at
        allowed = min(count, int(tokens))
        tokens -= allowed
        accepted += allowed
        rejected += count - allowed
    ask_rejected = rng.random() < 0.5
    listing = "; ".join(f"t = {at} с — запросов: {count}" for at, count in bursts)
    question = (
        "Сколько запросов получат 429 Too Many Requests?"
        if ask_rejected
        else "Сколько запросов будет пропущено?"
    )
    stem = (
        f"Лимит API реализован как token bucket: ёмкость {capacity} токенов, скорость пополнения — {rate} "
        "в секунду (равномерно), в момент 0 корзина полная. Каждый запрос забирает 1 токен, при отсутствии "
        "целого токена — "
        f"429. Запросы одного клиента приходят пачками (внутри пачки — мгновенно): {listing}. {question}"
    )
    return Generated(stem=stem, number=float(rejected if ask_rejected else accepted), tolerance=0)


def _fixture_run(
    tests: list[tuple[str, list[str]]],
    scopes: dict[str, str],
    deps: dict[str, list[str]],
    autouse: str | None,
    fifo: bool = False,
) -> list[str]:
    """Порядок setup/teardown в pytest для одного модуля: сначала более широкий scope, затем autouse,
    затем запрошенные фикстуры с зависимостями; teardown — в обратном порядке."""
    out: list[str] = []
    active_module: list[str] = []
    for test, args in tests:
        order: list[str] = []

        def need(name: str, order: list[str] = order) -> None:
            for dep in deps.get(name, []):
                need(dep, order)
            if name not in order:
                order.append(name)

        for name in ([autouse] if autouse else []) + args:
            need(name)
        module_first = [n for n in order if scopes[n] == "module"] + [
            n for n in order if scopes[n] == "function"
        ]
        function_active: list[str] = []
        for name in module_first:
            if scopes[name] == "module":
                if name not in active_module:
                    active_module.append(name)
                    out.append(f"{name}+")
            else:
                function_active.append(name)
                out.append(f"{name}+")
        out.append(test)
        out += [f"{name}-" for name in (function_active if fifo else reversed(function_active))]
    out += [f"{name}-" for name in (active_module if fifo else reversed(active_module))]
    return out


@generator("qa.pytest_fixture_order")
def pytest_fixture_order(rng: random.Random) -> Generated:
    """Широкий scope создаётся раньше, autouse — раньше запрошенных в своём scope, teardown — в обратном
    порядке."""
    db, user = rng.choice([("db", "user"), ("conn", "account"), ("server", "client"), ("browser", "page")])
    db_scope = rng.choice(["module", "function"])
    with_autouse = rng.random() < 0.6
    log = rng.choice(["log", "trace", "clock"])
    scopes = {db: db_scope, user: "function", log: "function"}
    deps = {user: [db]}
    names = rng.sample(["a", "b", "c", "d", "e"], 3)
    patterns = rng.choice(
        [[[user], [db], [user]], [[db], [user], []], [[user], [], [db, user]], [[], [user], [db]]]
    )
    tests = [(f"t_{name}", args) for name, args in zip(names, patterns, strict=True)]
    correct = _fixture_run(tests, scopes, deps, log if with_autouse else None)
    lines = ["import pytest", ""]
    if with_autouse:
        lines += [
            "@pytest.fixture(autouse=True)",
            f"def {log}():",
            f'    print("{log}+", end=" ")',
            "    yield",
            f'    print("{log}-", end=" ")',
            "",
        ]
    scope_arg = '(scope="module")' if db_scope == "module" else ""
    lines += [
        f"@pytest.fixture{scope_arg}",
        f"def {db}():",
        f'    print("{db}+", end=" ")',
        "    yield",
        f'    print("{db}-", end=" ")',
        "",
        "@pytest.fixture",
        f"def {user}({db}):",
        f'    print("{user}+", end=" ")',
        "    yield",
        f'    print("{user}-", end=" ")',
        "",
    ]
    for test, args in tests:
        lines.append(f'def test_{test[2:]}({", ".join(args)}): print("{test}", end=" ")')
    other_scope = "function" if db_scope == "module" else "module"
    auto = log if with_autouse else None
    wrong_runs = [
        _fixture_run(tests, {**scopes, db: other_scope}, deps, auto),
        _fixture_run(tests, dict.fromkeys(scopes, "module"), deps, auto),
        _fixture_run(tests, scopes, deps, auto, fifo=True),
    ]
    if with_autouse:
        wrong_runs.append(_fixture_run(tests, scopes, deps, None))
    wrong = [" ".join(run) for run in wrong_runs]
    joined = " ".join(correct)
    wrong.append(joined.replace(f"{db}+ {user}+", f"{user}+ {db}+"))
    wrong.append(" ".join(correct[:-1]) if correct[-1].endswith("-") else joined + f" {db}-")
    answer = " ".join(correct)
    return Generated(
        stem="Запуск: pytest -s, все тесты проходят. Что выведут print (без вывода pytest)?",
        code="\n".join(lines),
        code_language="python",
        correct=(answer,),
        wrong=_distinct_wrong(answer, wrong),
    )


@generator("qa.junit_instance_lifecycle")
def junit_instance_lifecycle(rng: random.Random) -> Generated:
    """JUnit 5: по умолчанию новый экземпляр класса на каждый тест (PER_METHOD); PER_CLASS — один на класс."""
    cls = rng.choice(["CartTest", "OrderServiceTest", "LoginTest", "PaymentTest"])
    per_class = rng.random() < 0.5
    tests = rng.randint(2, 4)
    repeated = rng.random() < 0.4
    step = rng.randint(1, 3)
    runs = tests - 1 + (2 if repeated else 1)
    names = rng.sample(["add", "remove", "total", "clear", "apply", "checkout"], tests)
    lines = ["import org.junit.jupiter.api.*;", ""]
    if per_class:
        lines.append("@TestInstance(TestInstance.Lifecycle.PER_CLASS)")
    lines += [
        f"class {cls} {{",
        "    static int created = 0;",
        "    int calls = 0;",
        "",
        f"    {cls}() {{ created++; }}",
        "",
        f"    @BeforeEach void setUp() {{ calls += {step}; }}",
        "",
    ]
    for index, name in enumerate(names):
        annotation = "@RepeatedTest(2)" if repeated and index == 0 else "@Test"
        lines.append(f'    {annotation} void {name}() {{ System.out.print(calls + " "); }}')
    lines += ["", '    @AfterAll static void done() { System.out.print("| " + created); }', "}"]
    if per_class:
        values, created = [step * (i + 1) for i in range(runs)], 1
    else:
        values, created = [step] * runs, runs
    correct = " ".join(map(str, values)) + f" | {created}"
    alt_values = [step] * runs if per_class else [step * (i + 1) for i in range(runs)]
    wrong = [
        " ".join(map(str, alt_values)) + f" | {runs if per_class else 1}",
        " ".join(map(str, values)) + f" | {runs if per_class else 1}",
        " ".join(map(str, alt_values)) + f" | {created}",
        " ".join(map(str, values[:tests])) + f" | {tests if not per_class else 1}",
        " ".join(["0"] * runs) + f" | {created}",
    ]
    return Generated(
        stem="Что выведет запуск всех тестов класса (JUnit 5, все тесты проходят)?",
        code="\n".join(lines),
        code_language="java",
        correct=(correct,),
        wrong=_distinct_wrong(correct, wrong),
    )


@generator("qa.sql_join_fanout")
def sql_join_fanout(rng: random.Random) -> Generated:
    """JOIN один-ко-многим размножает строки родителя: SUM по его полю после JOIN завышается."""
    order_ids = rng.sample(range(10, 60), rng.randint(4, 5))
    amounts = {oid: rng.randrange(100, 1000, 50) for oid in order_ids}
    items: list[tuple[int, str]] = []
    skus = ["pen", "cup", "bag", "hat", "map", "box", "tea"]
    for oid in order_ids:
        for _ in range(rng.choice([0, 1, 2, 3])):
            items.append((oid, rng.choice(skus)))
    if not any(sum(1 for o, _ in items if o == oid) >= 2 for oid in order_ids):
        items += [(order_ids[0], "pen"), (order_ids[0], "cup")]
    rng.shuffle(items)
    join = rng.choice(["JOIN", "LEFT JOIN"])
    total = 0
    for oid in order_ids:
        count = sum(1 for o, _ in items if o == oid)
        total += amounts[oid] * (count if join == "JOIN" else max(count, 1))
    orders_rows = ", ".join(f"({oid}, {amounts[oid]})" for oid in order_ids)
    items_rows = ", ".join(f"({oid}, '{sku}')" for oid, sku in items)
    code = (
        f"-- orders(id, amount): {orders_rows}\n"
        f"-- order_items(order_id, sku): {items_rows}\n\n"
        f"SELECT SUM(o.amount)\nFROM orders o\n{join} order_items i ON i.order_id = o.id;"
    )
    return Generated(
        stem="Какое число вернёт запрос?", code=code, code_language="sql", number=float(total), tolerance=0
    )


NAMES_QA = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "ivan", "lena", "maks", "olga", "petr"]


@generator("qa.sql_rank_top_n")
def sql_rank_top_n(rng: random.Random) -> Generated:
    """ROW_NUMBER режет ничьи, RANK оставляет ничьи и пропускает места, DENSE_RANK не пропускает места."""
    while True:
        depts = rng.sample(["sales", "it", "hr", "ops", "legal"], 2)
        people = iter(rng.sample(NAMES_QA, 12))
        rows = []
        for dept in depts:
            for _ in range(rng.randint(4, 6)):
                rows.append((next(people), dept, rng.choice([90, 100, 110, 120, 130])))
        top = rng.choice([2, 3])
        function = rng.choice(["ROW_NUMBER", "RANK", "DENSE_RANK"])
        results = {f: _rank_count(rows, depts, top, f) for f in ("ROW_NUMBER", "RANK", "DENSE_RANK")}
        if len(set(results.values())) == 3:
            break
    literals = [f"('{name}', '{dept}', {salary})" for name, dept, salary in rows]
    values = "\n".join("--   " + ", ".join(literals[i : i + 4]) for i in range(0, len(literals), 4))
    code = (
        f"-- employees(name, dept, salary):\n{values}\n\n"
        f"SELECT * FROM (\n  SELECT name, dept, salary,\n         {function}() OVER (PARTITION BY dept "
        "ORDER BY "
        f"salary DESC) AS r\n  FROM employees\n) t\nWHERE r <= {top};"
    )
    return Generated(
        stem="Сколько строк вернёт запрос?",
        code=code,
        code_language="sql",
        number=float(results[function]),
        tolerance=0,
    )


def _rank_count(rows: list[tuple[str, str, int]], depts: list[str], top: int, function: str) -> int:
    total = 0
    for dept in depts:
        salaries = sorted((s for _, d, s in rows if d == dept), reverse=True)
        if function == "ROW_NUMBER":
            total += min(top, len(salaries))
        elif function == "RANK":
            total += sum(1 for s in salaries if 1 + sum(1 for x in salaries if x > s) <= top)
        else:
            total += sum(1 for s in salaries if 1 + len({x for x in salaries if x > s}) <= top)
    return total
