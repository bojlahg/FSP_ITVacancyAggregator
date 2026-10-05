"""Генераторы Data Science-заданий: SQL и pandas на сгенерированных таблицах, метрики, формы массивов.

Результаты запросов и кода вычисляются в чистом Python — код кандидата не исполняется.
"""

import math
import random
import statistics
from collections import Counter

from app.modules.testing.engine.generators import generator
from app.modules.testing.engine.model import Generated

NAMES = ["anna", "boris", "vera", "gleb", "dina", "egor", "zoya", "ivan", "lena", "maks"]
CITIES = ["Kazan", "Omsk", "Perm", "Tomsk", "Sochi", "Tver", "Ufa"]
STATUSES = ["new", "paid", "shipped", "cancelled"]


def _fmt(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def _sql_values(rows: list[tuple]) -> str:
    def literal(value: object) -> str:
        if value is None:
            return "NULL"
        return f"'{value}'" if isinstance(value, str) else str(value)

    return ",\n  ".join("(" + ", ".join(literal(v) for v in row) + ")" for row in rows)


def _sql_result(rows: list[tuple]) -> str:
    return "; ".join(
        " | ".join(_fmt(v) if isinstance(v, int | float) else str(v) for v in row) for row in rows
    )


@generator("data.median")
def median(rng: random.Random) -> Generated:
    """Медиана небольшой неотсортированной выборки."""
    size = rng.choice([7, 8, 9, 10])
    values = [rng.randint(1, 60) for _ in range(size)]
    noun = rng.choice(
        ["время ответа сервиса, мс", "чек покупки, сотни ₽", "возраст клиентов", "длина сессии, мин"]
    )
    return Generated(
        stem=f"Выборка ({noun}): {', '.join(map(str, values))}. Чему равна медиана?",
        number=float(statistics.median(values)),
        tolerance=0.01,
    )


@generator("data.sql_count_null")
def sql_count_null(rng: random.Random) -> Generated:
    """COUNT(*) считает строки, COUNT(col) пропускает NULL, COUNT(DISTINCT col) — ещё и повторы."""
    while True:
        users = rng.sample(NAMES, rng.randint(6, 8))
        domains = rng.sample(["mail.ru", "ya.ru", "gmail.com", "corp.ru"], 3)
        emails = [None if rng.random() < 0.3 else f"info@{rng.choice(domains)}" for _ in users]
        total = len(users)
        non_null = sum(email is not None for email in emails)
        distinct = len({email for email in emails if email is not None})
        if len({total, non_null, distinct}) == 3 and distinct >= 2:
            break
    rows = [(index + 1, name, email) for index, (name, email) in enumerate(zip(users, emails, strict=True))]
    code = (
        "CREATE TABLE users (id int, name text, email text);\n"
        f"INSERT INTO users VALUES\n  {_sql_values(rows)};\n\n"
        "SELECT COUNT(*), COUNT(email), COUNT(DISTINCT email) FROM users;"
    )
    correct = f"{total} | {non_null} | {distinct}"
    wrong = {
        f"{total} | {total} | {distinct}",
        f"{total} | {non_null} | {distinct + 1}",
        f"{non_null} | {non_null} | {distinct}",
        f"{total} | {total} | {distinct + 1}",
        f"{total} | {non_null} | {non_null}",
    }
    wrong.discard(correct)
    return Generated(
        stem="Что вернёт последний запрос (столбцы через |)?",
        code=code,
        code_language="sql",
        correct=(correct,),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_group_having")
def sql_group_having(rng: random.Random) -> Generated:
    """HAVING фильтрует группы по агрегату, а не отдельные строки."""
    while True:
        customers = sorted(rng.sample(NAMES, 4))
        rows = []
        for customer in customers:
            for _ in range(rng.randint(1, 3)):
                rows.append((customer, rng.randrange(100, 900, 50)))
        rng.shuffle(rows)
        threshold = rng.randrange(600, 1200, 100)
        totals = {c: sum(a for name, a in rows if name == c) for c in customers}
        having = [(c, totals[c]) for c in customers if totals[c] > threshold]
        where = {}
        for name, amount in rows:
            if amount > threshold:
                where[name] = where.get(name, 0) + amount
        where_rows = sorted(where.items())
        having_ge = [(c, totals[c]) for c in customers if totals[c] >= threshold]
        all_rows = [(c, totals[c]) for c in customers]
        variants = {_sql_result(r) for r in (having, where_rows, all_rows)}
        if 1 <= len(having) < len(customers) and len(variants) == 3 and having_ge == having:
            break
    data = [(index + 1, name, amount) for index, (name, amount) in enumerate(rows)]
    code = (
        "CREATE TABLE orders (id int, customer text, amount int);\n"
        f"INSERT INTO orders VALUES\n  {_sql_values(data)};\n\n"
        "SELECT customer, SUM(amount) AS total\nFROM orders\nGROUP BY customer\n"
        f"HAVING SUM(amount) > {threshold}\nORDER BY customer;"
    )
    correct = _sql_result(having)
    wrong = {
        _sql_result(where_rows) or "пустой результат",
        _sql_result(all_rows),
        _sql_result([(c, max(a for n, a in rows if n == c)) for c, _ in having]),
        _sql_result([(c, sum(1 for n, _ in rows if n == c)) for c, _ in having]),
    }
    wrong.discard(correct)
    return Generated(
        stem="Что вернёт последний запрос? Строки разделены «;», столбцы — «|».",
        code=code,
        code_language="sql",
        correct=(correct,),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_left_join_count")
def sql_left_join_count(rng: random.Random) -> Generated:
    """LEFT JOIN + COUNT(o.id) даёт 0 для пользователей без заказов, COUNT(*) — 1."""
    while True:
        users = sorted(rng.sample(NAMES, 4))
        orders = [rng.choice(users) for _ in range(rng.randint(3, 6))]
        counts = Counter(orders)
        if 1 <= sum(1 for u in users if counts[u] == 0) <= 2:
            break
    user_rows = [(index + 1, name) for index, name in enumerate(users)]
    ids = {name: index + 1 for index, name in enumerate(users)}
    order_rows = [(100 + index, ids[name]) for index, name in enumerate(orders)]
    count_column = rng.choice(["o.id", "o.user_id"])
    code = (
        "CREATE TABLE users (id int, name text);\n"
        f"INSERT INTO users VALUES\n  {_sql_values(user_rows)};\n"
        "CREATE TABLE orders (id int, user_id int);\n"
        f"INSERT INTO orders VALUES\n  {_sql_values(order_rows)};\n\n"
        f"SELECT u.name, COUNT({count_column}) AS n\nFROM users u\n"
        "LEFT JOIN orders o ON o.user_id = u.id\nGROUP BY u.name\nORDER BY u.name;"
    )
    correct = _sql_result([(u, counts[u]) for u in users])
    wrong = {
        _sql_result([(u, max(counts[u], 1)) for u in users]),
        _sql_result([(u, counts[u]) for u in users if counts[u]]),
        _sql_result([(u, len(orders)) for u in users]),
        _sql_result([(u, 1 if counts[u] else 0) for u in users]),
    }
    wrong.discard(correct)
    return Generated(
        stem="Что вернёт последний запрос? Строки разделены «;», столбцы — «|».",
        code=code,
        code_language="sql",
        correct=(correct,),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_left_join_where")
def sql_left_join_where(rng: random.Random) -> Generated:
    """Условие на правую таблицу в WHERE превращает LEFT JOIN во внутреннее соединение."""
    while True:
        users = rng.sample(NAMES, rng.randint(4, 6))
        orders = [(rng.choice(users), rng.choice(STATUSES)) for _ in range(rng.randint(5, 8))]
        status = rng.choice(STATUSES)
        matched = [o for o in orders if o[1] == status]
        with_status = {u for u, s in orders if s == status}
        where_count = len(matched)
        on_count = where_count + sum(1 for u in users if u not in with_status)
        candidates = {where_count, on_count, len(users), len(orders)}
        if where_count >= 1 and len(candidates) == 4:
            break
    ids = {name: index + 1 for index, name in enumerate(users)}
    user_rows = [(ids[name], name) for name in users]
    order_rows = [(100 + index, ids[name], st) for index, (name, st) in enumerate(orders)]
    code = (
        "CREATE TABLE users (id int, name text);\n"
        f"INSERT INTO users VALUES\n  {_sql_values(user_rows)};\n"
        "CREATE TABLE orders (id int, user_id int, status text);\n"
        f"INSERT INTO orders VALUES\n  {_sql_values(order_rows)};\n\n"
        "SELECT COUNT(*)\nFROM users u\nLEFT JOIN orders o ON o.user_id = u.id\n"
        f"WHERE o.status = '{status}';"
    )
    wrong = {str(on_count), str(len(users)), str(len(orders)), str(where_count + 1)}
    wrong.discard(str(where_count))
    return Generated(
        stem="Что вернёт последний запрос?",
        code=code,
        code_language="sql",
        correct=(str(where_count),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_window_rank")
def sql_window_rank(rng: random.Random) -> Generated:
    """RANK оставляет пропуски после равных значений, DENSE_RANK — нет."""
    while True:
        names = rng.sample(NAMES, 6)
        scores = [rng.choice([70, 75, 80, 85, 90, 95]) for _ in names]
        ordered = sorted(scores, reverse=True)
        # цель — строка без «соседа» с тем же счётом, стоящая после хотя бы одной группы равных
        index = rng.randrange(len(names))
        target_score = scores[index]
        if scores.count(target_score) != 1:
            continue
        rank = 1 + sum(1 for s in scores if s > target_score)
        dense = 1 + len({s for s in scores if s > target_score})
        if rank != dense:
            break
    function = rng.choice(["RANK", "DENSE_RANK"])
    answer = rank if function == "RANK" else dense
    rows = [(name, score) for name, score in zip(names, scores, strict=True)]
    code = (
        "CREATE TABLE results (name text, score int);\n"
        f"INSERT INTO results VALUES\n  {_sql_values(rows)};\n\n"
        f"SELECT name, score, {function}() OVER (ORDER BY score DESC) AS r\nFROM results;"
    )
    position_asc = 1 + sum(1 for s in ordered if s < target_score)
    candidates = {rank, dense, rank + 1, dense - 1, dense + 1, position_asc, len({*scores})}
    wrong = {str(value) for value in candidates if value >= 1 and value != answer}
    return Generated(
        stem=f"Какое значение r будет у строки с name = '{names[index]}'?",
        code=code,
        code_language="sql",
        correct=(str(answer),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_not_equal_null")
def sql_not_equal_null(rng: random.Random) -> Generated:
    """Сравнение с NULL даёт UNKNOWN, поэтому WHERE col <> 'x' не возвращает строки с NULL."""
    while True:
        statuses = [rng.choice(["done", "open", "blocked", None]) for _ in range(rng.randint(7, 10))]
        target = rng.choice(["done", "open"])
        nulls = statuses.count(None)
        answer = sum(1 for s in statuses if s is not None and s != target)
        if nulls >= 2 and answer >= 1:
            break
    rows = [(index + 1, status) for index, status in enumerate(statuses)]
    code = (
        "CREATE TABLE tasks (id int, status text);\n"
        f"INSERT INTO tasks VALUES\n  {_sql_values(rows)};\n\n"
        f"SELECT COUNT(*) FROM tasks WHERE status <> '{target}';"
    )
    return Generated(
        stem="Какое число вернёт последний запрос?",
        code=code,
        code_language="sql",
        number=float(answer),
        tolerance=0,
    )


def _confusion(rng: random.Random) -> tuple[int, int, int, str, str]:
    tp, fn = rng.randint(20, 90), rng.randint(5, 40)
    fp, tn = rng.randint(5, 40), rng.randint(100, 400)
    task = rng.choice(
        ["модели оттока клиентов", "антифрод-модели", "детектора спама", "модели брака на линии"]
    )
    matrix = "\n".join(
        [
            "                Предсказано 1   Предсказано 0",
            f"Факт 1          {tp:<15} {fn}",
            f"Факт 0          {fp:<15} {tn}",
        ]
    )
    return tp, fn, fp, task, matrix


@generator("data.precision_recall")
def precision_recall(rng: random.Random) -> Generated:
    """Precision = TP / (TP + FP), recall = TP / (TP + FN)."""
    tp, fn, fp, task, matrix = _confusion(rng)
    metric = rng.choice(["precision", "recall"])
    value = tp / (tp + fp) if metric == "precision" else tp / (tp + fn)
    return Generated(
        stem=f"По матрице ошибок {task} (положительный класс — 1) посчитайте {metric}. "
        "Ответ — десятичная дробь от 0 до 1, округлите до двух знаков.",
        code=matrix,
        code_language="text",
        number=round(value, 2),
        tolerance=0.01,
    )


@generator("data.f1_score")
def f1_score(rng: random.Random) -> Generated:
    """F1 — гармоническое среднее precision и recall: 2TP / (2TP + FP + FN)."""
    tp, fn, fp, task, matrix = _confusion(rng)
    value = 2 * tp / (2 * tp + fp + fn)
    return Generated(
        stem=f"По матрице ошибок {task} (положительный класс — 1) посчитайте F1-меру. "
        "Ответ — десятичная дробь от 0 до 1, округлите до двух знаков.",
        code=matrix,
        code_language="text",
        number=round(value, 2),
        tolerance=0.01,
    )


@generator("data.metric_choice")
def metric_choice(rng: random.Random) -> Generated:
    """Выбор метрики под цену ошибок."""
    disease = rng.choice(
        ["диабет", "пневмонию", "редкое генетическое заболевание", "туберкулёз", "меланому", "гепатит C"]
    )
    target = rng.choice(
        [
            "время доставки",
            "стоимость ремонта",
            "длительность поездки",
            "время ответа поддержки",
            "цену подержанного автомобиля",
            "срок выполнения заказа",
        ]
    )
    blocked = rng.choice(["аккаунты", "банковские карты", "объявления", "отзывы", "платежи"])
    defect = rng.choice(["двигателей", "микросхем", "сварных швов", "подшипников"])
    goods = rng.choice(["товаров в магазинах", "SKU на складах", "позиций меню в ресторанах"])
    cases = [
        (
            f"Модель для скрининга на {disease}: пропустить больного намного хуже, чем отправить здорового "
            "на дополнительное обследование. Какую метрику важнее всего максимизировать?",
            "Recall (полнота)",
            [
                "Precision (точность)",
                "Accuracy",
                "Specificity (специфичность)",
                "Доля предсказанных положительных",
            ],
        ),
        (
            f"Модель ищет брак {defect} на конвейере; каждую найденную деталь затем проверяет "
            "человек, а пропущенный брак уходит клиенту и стоит очень дорого. Какую метрику "
            "важнее всего максимизировать?",
            "Recall (полнота)",
            ["Precision (точность)", "Accuracy", "Specificity (специфичность)", "ROC AUC"],
        ),
        (
            f"Модель автоматически блокирует {blocked} без ручной проверки. Каждая ошибочная блокировка "
            "очень дорога, а пропуск части нарушителей допустим. Какую метрику важнее всего максимизировать?",
            "Precision (точность)",
            ["Recall (полнота)", "Accuracy", "Доля предсказанных положительных", "F1 на обучающей выборке"],
        ),
        (
            f"Регрессия на {target}: в данных есть редкие выбросы, и крупные ошибки на них не должны "
            "непропорционально влиять на оценку модели. Какую метрику выбрать?",
            "MAE",
            ["RMSE", "MSE", "R²", "Максимальная абсолютная ошибка"],
        ),
        (
            f"Регрессия на {target}: крупные ошибки особенно дороги, их нужно штрафовать сильнее, чем "
            "несколько мелких с той же суммой. Какую метрику выбрать?",
            "RMSE",
            ["MAE", "MAPE", "Медианная абсолютная ошибка", "R²"],
        ),
        (
            f"Прогноз продаж {goods}: объёмы различаются на порядки, и бизнесу важна ошибка в процентах "
            "от факта, а не в штуках. Нулевых продаж в данных нет. Какую метрику выбрать?",
            "MAPE",
            ["MAE", "RMSE", "MSE", "Accuracy"],
        ),
        (
            f"Классификатор для {blocked}: по предсказанной вероятности считают ожидаемые потери в рублях, "
            "поэтому вероятности должны быть хорошо откалиброваны. Какая метрика это оценивает?",
            "Log loss (логистическая функция потерь)",
            ["ROC AUC", "Accuracy", "Recall (полнота)", "Precision (точность)"],
        ),
    ]
    stem, correct, wrong = rng.choice(cases)
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


@generator("data.task_type")
def task_type(rng: random.Random) -> Generated:
    """Тип задачи машинного обучения по постановке."""
    city = rng.choice(CITIES)
    n = rng.choice([50, 100, 300, 500, 1000])
    cases = [
        (f"Предсказать цену квартиры в городе {city} по площади, этажу и району.", "Регрессия"),
        (f"Предсказать, сколько заказов поступит завтра в магазин в городе {city}.", "Регрессия"),
        (f"Оценить, сколько минут займёт доставка заказа в городе {city}.", "Регрессия"),
        ("Определить по тексту письма, спам это или нет, по размеченной выборке.", "Классификация"),
        ("Распознать рукописную цифру от 0 до 9 на изображении по размеченной выборке.", "Классификация"),
        (
            f"По истории платежей клиентов из города {city} предсказать, уйдёт ли клиент в следующем месяце; "
            "есть разметка за прошлые периоды.",
            "Классификация",
        ),
        (
            f"Разбить клиентов магазина в городе {city} на группы со схожим поведением; разметки нет.",
            "Кластеризация",
        ),
        (f"Сгруппировать {n} новостных статей по сходству текста; заранее темы неизвестны.", "Кластеризация"),
        (f"Сжать {n} признаков до 2, чтобы визуализировать данные на плоскости.", "Понижение размерности"),
        (
            "Агент управляет ценой в онлайн-игре, получает награду за выручку и учится на последствиях "
            "своих действий.",
            "Обучение с подкреплением",
        ),
    ]
    stem, answer = rng.choice(cases)
    kinds = [
        "Регрессия",
        "Классификация",
        "Кластеризация",
        "Понижение размерности",
        "Обучение с подкреплением",
    ]
    lead = rng.choice(
        [
            "К какому типу задач машинного обучения относится постановка?",
            "Какой это тип задачи машинного обучения?",
            "Как называется такой тип задачи в машинном обучении?",
        ]
    )
    return Generated(
        stem=f"{lead} {stem}",
        correct=(answer,),
        wrong=tuple(k for k in kinds if k != answer),
    )


BIAS_UP = "Смещение растёт, дисперсия уменьшается"
BIAS_DOWN = "Смещение уменьшается, дисперсия растёт"


@generator("data.bias_variance")
def bias_variance(rng: random.Random) -> Generated:
    """Как изменение сложности модели сдвигает баланс смещения и дисперсии."""
    cases = [
        (f"увеличить max_depth решающего дерева с {rng.randint(3, 5)} до {rng.randint(15, 30)}", BIAS_DOWN),
        (f"увеличить число соседей k в kNN с {rng.randint(1, 3)} до {rng.randint(30, 60)}", BIAS_UP),
        (
            f"увеличить коэффициент L2-регуляризации в ridge-регрессии в {rng.choice([10, 100, 1000])} раз",
            BIAS_UP,
        ),
        (f"добавить в линейную регрессию полиномиальные признаки степени до {rng.randint(8, 15)}", BIAS_DOWN),
        (f"увеличить min_samples_leaf у дерева с 1 до {rng.randint(30, 100)}", BIAS_UP),
    ]
    change, answer = rng.choice(cases)
    options = [BIAS_UP, BIAS_DOWN, "Смещение и дисперсия уменьшаются", "Смещение и дисперсия растут"]
    return Generated(
        stem=f"Как обычно изменятся смещение (bias) и дисперсия (variance) модели, если {change}?",
        correct=(answer,),
        wrong=tuple(o for o in options if o != answer),
    )


def _df_literal(columns: dict[str, list]) -> str:
    def literal(value: object) -> str:
        if value is None:
            return "None"
        return f'"{value}"' if isinstance(value, str) else str(value)

    body = ",\n".join(
        f'    "{name}": [{", ".join(literal(v) for v in values)}]' for name, values in columns.items()
    )
    return "df = pd.DataFrame({\n" + body + ",\n})"


@generator("data.pandas_groupby_agg")
def pandas_groupby_agg(rng: random.Random) -> Generated:
    """groupby + агрегат по группе."""
    while True:
        cities = rng.sample(CITIES, 3)
        city_col = [rng.choice(cities) for _ in range(rng.randint(7, 9))]
        sales = [rng.randrange(10, 100, 5) for _ in city_col]
        city = rng.choice(cities)
        group = [s for c, s in zip(city_col, sales, strict=True) if c == city]
        if len(group) < 2:
            continue
        stats = {"sum": sum(group), "max": max(group), "count": len(group), "min": min(group)}
        op = rng.choice(["sum", "max", "count"])
        answer = stats[op]
        wrong = {str(v) for v in stats.values()} | {str(sum(sales)), str(sales[city_col.index(city)])}
        other = next(c for c in cities if c != city)
        other_group = [s for c, s in zip(city_col, sales, strict=True) if c == other]
        if other_group:
            wrong.add(str({"sum": sum, "max": max, "count": len}[op](other_group)))
        wrong.discard(str(answer))
        if len(wrong) >= 3:
            break
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            _df_literal({"city": city_col, "sales": sales}),
            "",
            f'print(df.groupby("city")["sales"].{op}()["{city}"])',
        ]
    )
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(answer),),
        wrong=tuple(sorted(wrong)),
    )


def _shape(dims: tuple[int, ...]) -> str:
    return "(" + ", ".join(map(str, dims)) + ("," if len(dims) == 1 else "") + ")"


@generator("data.numpy_reduce_shape")
def numpy_reduce_shape(rng: random.Random) -> Generated:
    """Агрегация по оси убирает эту ось из формы."""
    dims = tuple(rng.sample(range(2, 9), 3))
    axis = rng.randrange(3)
    func = rng.choice(["sum", "mean", "max"])
    result = tuple(d for i, d in enumerate(dims) if i != axis)
    keep = tuple(1 if i == axis else d for i, d in enumerate(dims))
    wrong = {_shape(keep), _shape((dims[axis],)), _shape(dims)}
    for other in range(3):
        if other != axis:
            wrong.add(_shape(tuple(d for i, d in enumerate(dims) if i != other)))
    wrong.discard(_shape(result))
    code = "\n".join(
        ["import numpy as np", "", f"x = np.ones({_shape(dims)})", f"print(x.{func}(axis={axis}).shape)"]
    )
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(_shape(result),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.numpy_broadcast")
def numpy_broadcast(rng: random.Random) -> Generated:
    """Broadcasting: оси выравниваются справа, размер 1 растягивается."""
    m, n = rng.sample(range(2, 9), 2)
    if rng.random() < 0.5:
        left, right, result = (m, 1), (n,), (m, n)
    else:
        k = rng.choice([d for d in range(2, 7) if d not in (m, n)])
        left, right, result = (k, m, 1), (1, n), (k, m, n)
    op = rng.choice(["+", "*", "-"])
    code = "\n".join(
        [
            "import numpy as np",
            "",
            f"a = np.ones({_shape(left)})",
            f"b = np.ones({_shape(right)})",
            f"print((a {op} b).shape)",
        ]
    )
    wrong = {
        _shape(left),
        _shape(tuple(reversed(result))),
        "ValueError: operands could not be broadcast together",
        _shape((m,)) if len(left) == 2 else _shape((k, m)),
    }
    wrong.discard(_shape(result))
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(_shape(result),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.loc_iloc_slice")
def loc_iloc_slice(rng: random.Random) -> Generated:
    """loc режет по меткам включительно, iloc — по позициям без правой границы."""
    size = rng.randint(8, 15)
    start = rng.randint(1, 4)
    stop = rng.randint(start + 2, size - 2)
    column = rng.choice(["price", "score", "clicks", "amount"])
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            f'df = pd.DataFrame({{"{column}": range({size})}})',
            f"print(len(df.loc[{start}:{stop}]), len(df.iloc[{start}:{stop}]))",
        ]
    )
    span = stop - start
    correct = f"{span + 1} {span}"
    wrong = [f"{span} {span}", f"{span + 1} {span + 1}", f"{span} {span + 1}", f"{span - 1} {span}"]
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(correct,),
        wrong=tuple(wrong),
    )


@generator("data.pandas_merge_rows")
def pandas_merge_rows(rng: random.Random) -> Generated:
    """Внутреннее соединение по неуникальному ключу даёт произведение совпадений."""
    while True:
        keys = rng.sample(range(1, 10), 4)
        left = [rng.choice(keys) for _ in range(rng.randint(4, 6))]
        right = [rng.choice(keys) for _ in range(rng.randint(4, 6))]
        lc, rc = Counter(left), Counter(right)
        answer = sum(lc[k] * rc[k] for k in lc)
        common = len(set(left) & set(right))
        dup_in_both = any(lc[k] > 1 and rc[k] > 1 for k in lc)
        candidates = {answer, len(left), len(right), common, min(len(left), len(right))}
        if dup_in_both and len({answer, len(left), len(right), common}) == 4:
            break
    left_values = [rng.randrange(100, 1000, 10) for _ in left]
    right_values = [rng.choice(["web", "ios", "android"]) for _ in right]
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            f'orders = pd.DataFrame({{"user_id": {left}, "amount": {left_values}}})',
            f'visits = pd.DataFrame({{"user_id": {right}, "channel": {right_values}}})'.replace("'", '"'),
            "",
            'merged = orders.merge(visits, on="user_id")',
            "print(len(merged))",
        ]
    )
    wrong = {str(v) for v in candidates} | {str(answer + 1), str(len(set(left)))}
    wrong.discard(str(answer))
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(answer),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.pandas_count_nan")
def pandas_count_nan(rng: random.Random) -> Generated:
    """count() в groupby пропускает NaN, size() считает все строки группы."""
    while True:
        segments = rng.sample(["A", "B", "C"], 3)
        segment_col = [rng.choice(segments) for _ in range(rng.randint(8, 10))]
        amount = [None if rng.random() < 0.35 else rng.randrange(10, 90, 10) for _ in segment_col]
        target = rng.choice(segments)
        group = [a for s, a in zip(segment_col, amount, strict=True) if s == target]
        count = sum(a is not None for a in group)
        size = len(group)
        nans = size - count
        if count >= 1 and nans >= 1 and count != nans:
            break
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            _df_literal({"segment": segment_col, "amount": amount}),
            "",
            f'print(df.groupby("segment")["amount"].count()["{target}"])',
        ]
    )
    total_non_null = sum(a is not None for a in amount)
    wrong = {str(size), str(nans), str(total_non_null), str(len(amount)), "nan"}
    wrong.discard(str(count))
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(count),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.numpy_view_copy")
def numpy_view_copy(rng: random.Random) -> Generated:
    """Срез NumPy — представление (view) над теми же данными, fancy indexing — копия."""
    size = rng.randint(6, 10)
    start = rng.randint(1, 3)
    stop = rng.randint(start + 2, size - 1)
    new_value = rng.choice([-1, 42, 99, 100])
    name = rng.choice(["b", "part", "window", "chunk"])
    fancy = rng.random() < 0.5
    picked = list(range(start, stop))
    index_expr = f"[{picked}]" if fancy else f"[{start}:{stop}]"
    code = "\n".join(
        [
            "import numpy as np",
            "",
            f"a = np.arange({size})",
            f"{name} = a{index_expr}",
            f"{name}[0] = {new_value}",
            f"print(a[{start}])",
        ]
    )
    answer = start if fancy else new_value
    other = new_value if fancy else start
    wrong = {str(other), str(start + 1), str(start - 1), "IndexError"}
    wrong.discard(str(answer))
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(answer),),
        wrong=tuple(sorted(wrong)),
    )


PRODUCTS = ["kettle", "lamp", "chair", "mouse", "phone", "table", "drill", "scale", "radio"]


@generator("data.normal_rule")
def normal_rule(rng: random.Random) -> Generated:
    """Правило 68–95–99,7: доля нормального распределения в пределах 1, 2 и 3 σ от среднего."""
    k, share = rng.choice([(1, 68.0), (2, 95.0), (3, 99.7)])
    mean = rng.randrange(300, 1001, 10)
    sd = rng.randrange(5, 65, 5)
    what = rng.choice(
        [
            "Время ответа сервиса (мс)",
            "Рост взрослых мужчин в выборке (мм)",
            "Вес упаковки на линии фасовки (г)",
            "Дневная выручка кофейни (сотни ₽)",
            "Балл за экзамен",
        ]
    )
    return Generated(
        stem=f"{what} распределено нормально со средним {mean} и стандартным отклонением {sd}. "
        f"Какая доля значений приблизительно лежит в интервале от {mean - k * sd} до {mean + k * sd}? "
        "Ответ в процентах.",
        number=share,
        tolerance=1.0,
    )


@generator("data.sample_variance")
def sample_variance(rng: random.Random) -> Generated:
    """Несмещённая выборочная дисперсия: сумма квадратов отклонений от среднего, делённая на n − 1."""
    size = rng.choice([4, 5, 6])
    values = [rng.randint(1, 20) for _ in range(size)]
    noun = rng.choice(["заказов в день", "минут на задачу", "ошибок в сборке", "звонков в час"])
    return Generated(
        stem=f"Выборка ({noun}): {', '.join(map(str, values))}. Чему равна несмещённая выборочная "
        "дисперсия (с делителем n − 1)? Округлите до сотых.",
        number=round(statistics.variance(values), 2),
        tolerance=0.01,
    )


SIMPSON_RIGHT = (
    "В каждом сегменте B лучше, а в сумме хуже из-за разного состава групп по сегментам (парадокс "
    "Симпсона): сравнивать нужно внутри сегментов и выяснить, почему при рандомизации состав групп разошёлся",
    "Это парадокс Симпсона: в группе B больше доля сегмента с низкой конверсией, поэтому общий итог "
    "искажён; выводы делать по сегментам и проверить сплит",
)
SIMPSON_WRONG = (
    "B хуже: для решения важна только общая конверсия, сегменты не имеют значения",
    "В таблице ошибка: если B лучше в каждом сегменте, то в сумме B тоже обязательно лучше",
    "B лучше только для одного сегмента, поэтому эффект нужно считать незначимым",
    "Надо сложить разницы конверсий по сегментам и сравнить сумму с общей разницей",
    "Результат объясняется малым размером выборки в каждом сегменте, а не составом групп",
)


@generator("data.simpson")
def simpson(rng: random.Random) -> Generated:
    """Парадокс Симпсона: эффект внутри каждого сегмента противоположен эффекту в сумме."""
    segments = rng.choice([("desktop", "mobile"), ("новые", "вернувшиеся"), ("Москва", "регионы")])
    while True:
        high = rng.uniform(0.10, 0.16)
        low = rng.uniform(0.02, 0.05)
        lift = rng.uniform(0.004, 0.012)
        big, small = rng.randrange(6000, 9001, 100), rng.randrange(1000, 2501, 100)
        groups = {"A": (big, small), "B": (small, big)}
        table = {}
        for group, (n_high, n_low) in groups.items():
            delta = lift if group == "B" else 0.0
            table[group] = [
                (n_high, round(n_high * (high + delta))),
                (n_low, round(n_low * (low + delta))),
            ]
        rate = {g: [c / n for n, c in rows] for g, rows in table.items()}
        total = {g: sum(c for _, c in rows) / sum(n for n, _ in rows) for g, rows in table.items()}
        if all(rate["B"][i] > rate["A"][i] for i in range(2)) and total["B"] < total["A"]:
            break
    lines = ["Группа  Сегмент        Пользователей  Покупок  Конверсия"]
    for group, rows in table.items():
        for segment, (n, c) in zip(segments, rows, strict=True):
            lines.append(f"{group:<7} {segment:<14} {n:<14} {c:<8} {100 * c / n:.1f}%")
    for group, rows in table.items():
        n, c = sum(r[0] for r in rows), sum(r[1] for r in rows)
        lines.append(f"{group:<7} {'всего':<14} {n:<14} {c:<8} {100 * c / n:.1f}%")
    return Generated(
        stem="Результаты A/B-теста по сегментам и в сумме приведены в таблице. Какой вывод верный?",
        code="\n".join(lines),
        code_language="text",
        correct=(rng.choice(SIMPSON_RIGHT),),
        wrong=SIMPSON_WRONG,
    )


@generator("data.knn_regression")
def knn_regression(rng: random.Random) -> Generated:
    """kNN-регрессия: среднее целевой переменной у k ближайших соседей."""
    k = rng.choice([3, 4, 5])
    size = rng.randint(k + 3, k + 5)
    distances = sorted(rng.sample(range(5, 100), size))
    targets = [rng.randrange(10, 200, 5) for _ in range(size)]
    order = list(range(size))
    rng.shuffle(order)
    target_name, unit = rng.choice(
        [("время доставки", "мин"), ("выручка точки", "тыс. ₽"), ("расход топлива", "л на 1000 км")]
    )
    lines = ["Сосед  Расстояние  Цель"] + [
        f"{i + 1:<6} {distances[j] / 10:<11} {targets[j]}" for i, j in enumerate(order)
    ]
    value = sum(targets[:k]) / k
    return Generated(
        stem=f"kNN-регрессия (k = {k}, равные веса) предсказывает «{target_name}» ({unit}). Для нового "
        "объекта посчитаны расстояния до объектов обучающей выборки. Какое значение предскажет модель? "
        "Округлите до сотых.",
        code="\n".join(lines),
        code_language="text",
        number=round(value, 2),
        tolerance=0.01,
    )


@generator("data.pca_variance")
def pca_variance(rng: random.Random) -> Generated:
    """Доля объяснённой дисперсии первых k компонент = сумма их собственных значений / сумма всех."""
    values = sorted(rng.sample(range(1, 60), 5), reverse=True)
    k = rng.choice([2, 3])
    share = 100 * sum(values[:k]) / sum(values)
    data = rng.choice(["анкет клиентов", "сенсоров станка", "показателей магазинов", "метрик серверов"])
    return Generated(
        stem=f"PCA по стандартизованным данным {data}: собственные значения ковариационной матрицы "
        f"(дисперсии вдоль главных компонент) — {', '.join(map(str, values))}. Какую долю общей дисперсии "
        f"объясняют первые {k} компоненты? Ответ в процентах, округлите до десятых.",
        number=round(share, 1),
        tolerance=0.2,
    )


@generator("data.pandas_shape")
def pandas_shape(rng: random.Random) -> Generated:
    """df.shape — кортеж (число строк, число столбцов)."""
    columns = rng.sample(["city", "price", "qty", "age", "score", "clicks", "segment"], rng.randint(2, 5))
    rows = rng.choice([n for n in range(3, 8) if n != len(columns)])
    data = {column: [rng.randint(1, 99) for _ in range(rows)] for column in columns}
    code = "\n".join(["import pandas as pd", "", _df_literal(data), "", "print(df.shape)"])
    n, m = rows, len(columns)
    wrong = {f"({m}, {n})", f"({n},)", str(n * m), f"({n + 1}, {m})", f"({n}, {m + 1})"}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(f"({n}, {m})",),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.pandas_value_counts")
def pandas_value_counts(rng: random.Random) -> Generated:
    """value_counts считает, сколько раз встречается каждое значение."""
    labels = rng.choice([["web", "ios", "android"], ["A", "B", "C"], ["new", "paid", "cancelled"]])
    while True:
        values = [rng.choice(labels) for _ in range(rng.randint(7, 10))]
        counts = Counter(values)
        if len(counts) == 3 and len(set(counts.values())) == 3:
            break
    target = rng.choice(labels)
    name = rng.choice(["channel", "status", "group", "s"])
    literal = "[" + ", ".join(f'"{v}"' for v in values) + "]"
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            f"{name} = pd.Series({literal})",
            f'print({name}.value_counts()["{target}"])',
        ]
    )
    answer = counts[target]
    wrong = {str(c) for c in counts.values()} | {str(len(values)), str(len(counts)), str(answer + 1)}
    wrong.discard(str(answer))
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(answer),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.pandas_bool_filter")
def pandas_bool_filter(rng: random.Random) -> Generated:
    """Булева маска df[df[col] > t] оставляет только строки, где условие истинно (строго больше)."""
    column = rng.choice(["price", "age", "score", "amount"])
    while True:
        values = [rng.randrange(10, 100, 5) for _ in range(rng.randint(7, 10))]
        threshold = rng.choice(values)
        gt = sum(v > threshold for v in values)
        ge = sum(v >= threshold for v in values)
        le = len(values) - gt
        if gt >= 1 and le >= 2 and len({gt, ge, le, le - 1, len(values)}) == 5:
            break
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            _df_literal({column: values}),
            "",
            f'print(len(df[df["{column}"] > {threshold}]))',
        ]
    )
    wrong = {str(ge), str(le), str(len(values)), str(le - 1)}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(gt),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.pandas_dropna")
def pandas_dropna(rng: random.Random) -> Generated:
    """dropna() по умолчанию (how='any') удаляет строку, если NaN есть хотя бы в одном столбце."""
    first, second = rng.sample(["age", "income", "city_id", "score", "visits"], 2)
    while True:
        size = rng.randint(6, 9)
        a = [None if rng.random() < 0.3 else rng.randint(1, 99) for _ in range(size)]
        b = [None if rng.random() < 0.3 else rng.randint(1, 99) for _ in range(size)]
        both = sum(x is not None and y is not None for x, y in zip(a, b, strict=True))
        any_value = sum(x is not None or y is not None for x, y in zip(a, b, strict=True))
        a_ok = sum(x is not None for x in a)
        b_ok = sum(y is not None for y in b)
        if len({both, any_value, a_ok, b_ok, size}) == 5:
            break
    code = "\n".join(
        ["import pandas as pd", "", _df_literal({first: a, second: b}), "", "print(len(df.dropna()))"]
    )
    wrong = {str(any_value), str(a_ok), str(b_ok), str(size)}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(both),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.split_sizes")
def split_sizes(rng: random.Random) -> Generated:
    """train_test_split с долей test_size: в тест уходит ceil(test_size · n) строк, остальное — в train."""
    while True:
        n = rng.randrange(100, 2001, 20)
        test = rng.choice([0.1, 0.2, 0.25, 0.3])
        n_test = math.ceil(test * n)
        # берём только n, где test_size · n — целое и в float, чтобы не было неоднозначности округления
        if n_test * 1.0 == test * n:
            break
    n_train = n - n_test
    x = rng.choice(["X", "features", "X_all"])
    code = "\n".join(
        [
            "from sklearn.model_selection import train_test_split",
            "",
            f"# {x}.shape == ({n}, {rng.randint(5, 40)})",
            f"X_train, X_test, y_train, y_test = train_test_split({x}, y, test_size={test}, random_state=0)",
            "print(len(X_train), len(X_test))",
        ]
    )
    wrong = {f"{n_test} {n_train}", f"{n} {n_test}", f"{n_train} {n}", f"{n_train + 1} {n_test - 1}"}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(f"{n_train} {n_test}",),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.groupby_transform")
def groupby_transform(rng: random.Random) -> Generated:
    """transform возвращает значение для каждой строки исходного DataFrame, агрегат — по одному на группу."""
    groups = rng.sample(["A", "B", "C", "D"], rng.randint(2, 4))
    while True:
        column = [rng.choice(groups) for _ in range(rng.randint(6, 10))]
        if len(set(column)) == len(groups):
            break
    values = [rng.randrange(10, 100, 10) for _ in column]
    func = rng.choice(["mean", "sum", "max"])
    key, val = rng.choice([("segment", "amount"), ("city", "sales"), ("team", "score")])
    code = "\n".join(
        [
            "import pandas as pd",
            "",
            _df_literal({key: column, val: values}),
            "",
            f't = df.groupby("{key}")["{val}"].transform("{func}")',
            f'a = df.groupby("{key}")["{val}"].{func}()',
            "print(len(t), len(a))",
        ]
    )
    n, k = len(column), len(groups)
    wrong = {f"{k} {k}", f"{n} {n}", f"{k} {n}", f"{n} {k + 1}"}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(f"{n} {k}",),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.numpy_int_assign")
def numpy_int_assign(rng: random.Random) -> Generated:
    """Присваивание float в целочисленный массив отбрасывает дробную часть: dtype массива не меняется."""
    values = [rng.randint(1, 30) for _ in range(rng.randint(4, 6))]
    index = rng.randrange(len(values))
    whole = rng.randint(2, 40)
    new = f"{whole}.{rng.choice([5, 6, 7, 8, 9])}"
    name = rng.choice(["a", "arr", "counts", "x"])
    code = "\n".join(
        [
            "import numpy as np",
            "",
            f"{name} = np.array({values})",
            f"{name}[{index}] = {new}",
            f"print({name}[{index}])",
        ]
    )
    wrong = {new, str(whole + 1), f"{whole}.0", "TypeError"}
    return Generated(
        stem="Что выведет этот код?",
        code=code,
        code_language="python",
        correct=(str(whole),),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_where_count")
def sql_where_count(rng: random.Random) -> Generated:
    """WHERE price > t — строгое сравнение: строки с ценой ровно t не попадают."""
    while True:
        names = rng.sample(PRODUCTS, rng.randint(6, 8))
        prices = [rng.randrange(100, 1000, 50) for _ in names]
        threshold = rng.choice(prices)
        gt = sum(p > threshold for p in prices)
        ge = sum(p >= threshold for p in prices)
        lt = sum(p < threshold for p in prices)
        if gt >= 1 and len({gt, ge, lt, lt + 1, len(prices)}) == 5:
            break
    rows = [(i + 1, n, p) for i, (n, p) in enumerate(zip(names, prices, strict=True))]
    code = (
        "CREATE TABLE products (id int, name text, price int);\n"
        f"INSERT INTO products VALUES\n  {_sql_values(rows)};\n\n"
        f"SELECT COUNT(*) FROM products WHERE price > {threshold};"
    )
    wrong = {str(ge), str(lt), str(len(prices)), str(lt + 1)}
    return Generated(
        stem="Что вернёт последний запрос?",
        code=code,
        code_language="sql",
        correct=(str(gt),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.sql_order_limit")
def sql_order_limit(rng: random.Random) -> Generated:
    """ORDER BY ... DESC/ASC LIMIT n возвращает n первых строк после сортировки."""
    names = rng.sample(NAMES, rng.randint(5, 7))
    scores = rng.sample(range(40, 100), len(names))
    rows = list(zip(names, scores, strict=True))
    direction = rng.choice(["DESC", "ASC"])
    limit = rng.choice([1, 2])
    ranked = sorted(rows, key=lambda r: r[1], reverse=direction == "DESC")

    def show(part: list[tuple[str, int]]) -> str:
        return "; ".join(name for name, _ in part)

    correct = show(ranked[:limit])
    wrong = {
        show(ranked[::-1][:limit]),
        show(rows[:limit]),
        show(ranked[1 : limit + 1]),
        show(ranked[: limit + 1]),
        show(ranked[-1:]),
    }
    wrong.discard(correct)
    code = (
        "CREATE TABLE results (name text, score int);\n"
        f"INSERT INTO results VALUES\n  {_sql_values(rows)};\n\n"
        f"SELECT name FROM results\nORDER BY score {direction}\nLIMIT {limit};"
    )
    return Generated(
        stem="Что вернёт последний запрос? Строки разделены «;».",
        code=code,
        code_language="sql",
        correct=(correct,),
        wrong=tuple(sorted(wrong)),
    )


@generator("data.sql_group_rows")
def sql_group_rows(rng: random.Random) -> Generated:
    """GROUP BY возвращает по одной строке на каждое различное значение ключа группировки."""
    while True:
        cities = rng.sample(CITIES, rng.randint(2, 5))
        column = [rng.choice(cities) for _ in range(rng.randint(6, 10))]
        if len(set(column)) == len(cities):
            break
    rows = [(i + 1, rng.choice(NAMES), city) for i, city in enumerate(column)]
    code = (
        "CREATE TABLE customers (id int, name text, city text);\n"
        f"INSERT INTO customers VALUES\n  {_sql_values(rows)};\n\n"
        "SELECT city, COUNT(*) AS n\nFROM customers\nGROUP BY city;"
    )
    return Generated(
        stem="Сколько строк вернёт последний запрос?",
        code=code,
        code_language="sql",
        number=float(len(cities)),
        tolerance=0,
    )


@generator("data.sql_avg_null")
def sql_avg_null(rng: random.Random) -> Generated:
    """AVG пропускает NULL: делит сумму на число непустых значений, а не на число строк."""
    while True:
        values = [None if rng.random() < 0.3 else rng.randrange(2, 20) for _ in range(rng.randint(6, 9))]
        known = [v for v in values if v is not None]
        if len(known) >= 3 and len(values) - len(known) >= 2:
            break
    column, table = rng.choice([("rating", "reviews"), ("score", "exams"), ("delay_min", "flights")])
    rows = [(i + 1, v) for i, v in enumerate(values)]
    code = (
        f"CREATE TABLE {table} (id int, {column} int);\n"
        f"INSERT INTO {table} VALUES\n  {_sql_values(rows)};\n\n"
        f"SELECT AVG({column}) FROM {table};"
    )
    return Generated(
        stem="Какое число вернёт последний запрос (PostgreSQL)? Округлите до сотых.",
        code=code,
        code_language="sql",
        number=round(sum(known) / len(known), 2),
        tolerance=0.01,
    )


@generator("data.sql_union")
def sql_union(rng: random.Random) -> Generated:
    """UNION убирает все дубликаты результата, в том числе повторы внутри одной таблицы; UNION ALL — нет."""
    pool = [f"{n}@mail.ru" for n in NAMES]
    while True:
        a = [rng.choice(pool[:7]) for _ in range(rng.randint(3, 5))]
        b = [rng.choice(pool[3:]) for _ in range(rng.randint(3, 5))]
        union = len(set(a) | set(b))
        union_all = len(a) + len(b)
        naive = len(a) + len(b) - len(set(a) & set(b))
        if len(set(a)) < len(a) and len({union, union_all, naive}) == 3:
            break
    first, second = rng.choice([("subscribers", "customers"), ("leads", "clients"), ("newsletter", "buyers")])
    code = (
        f"CREATE TABLE {first} (email text);\n"
        f"INSERT INTO {first} VALUES\n  {_sql_values([(e,) for e in a])};\n"
        f"CREATE TABLE {second} (email text);\n"
        f"INSERT INTO {second} VALUES\n  {_sql_values([(e,) for e in b])};\n\n"
        f"SELECT COUNT(*) FROM (\n  SELECT email FROM {first}\n  UNION\n  SELECT email FROM {second}\n) t;"
    )
    wrong = {str(union_all), str(naive), str(len(set(a)) + len(set(b))), str(union + 1), str(union - 1)}
    wrong.discard(str(union))
    return Generated(
        stem="Что вернёт последний запрос?",
        code=code,
        code_language="sql",
        correct=(str(union),),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.sql_not_in_null")
def sql_not_in_null(rng: random.Random) -> Generated:
    """x NOT IN (..., NULL) никогда не даёт TRUE: результат FALSE или UNKNOWN, строки отбрасываются."""
    users = rng.sample(NAMES, rng.randint(5, 7))
    banned: list[int | None] = list(rng.sample(range(1, len(users) + 1), rng.randint(1, 2)))
    banned.insert(rng.randrange(len(banned) + 1), None)
    ban_rows = [(i + 1, uid) for i, uid in enumerate(banned)]
    user_rows = [(i + 1, name) for i, name in enumerate(users)]
    table, column = rng.choice([("bans", "user_id"), ("blocked", "user_id"), ("complaints", "author_id")])
    code = (
        "CREATE TABLE users (id int, name text);\n"
        f"INSERT INTO users VALUES\n  {_sql_values(user_rows)};\n"
        f"CREATE TABLE {table} (id int, {column} int);\n"
        f"INSERT INTO {table} VALUES\n  {_sql_values(ban_rows)};\n\n"
        f"SELECT COUNT(*) FROM users\nWHERE id NOT IN (SELECT {column} FROM {table});"
    )
    expected = len(users) - (len(banned) - 1)
    wrong = {str(expected), str(expected - 1), str(len(users)), str(len(banned) - 1)}
    return Generated(
        stem="Что вернёт последний запрос (PostgreSQL)?",
        code=code,
        code_language="sql",
        correct=("0",),
        wrong=tuple(sorted(wrong, key=int)),
    )


@generator("data.accuracy")
def accuracy(rng: random.Random) -> Generated:
    """Accuracy = (TP + TN) / все объекты."""
    tp, fn, fp, task, matrix = _confusion(rng)
    tn = int(matrix.splitlines()[2].split()[-1])
    value = (tp + tn) / (tp + tn + fp + fn)
    return Generated(
        stem=f"По матрице ошибок {task} (положительный класс — 1) посчитайте accuracy. "
        "Ответ — десятичная дробь от 0 до 1, округлите до двух знаков.",
        code=matrix,
        code_language="text",
        number=round(value, 2),
        tolerance=0.01,
    )


@generator("data.mae")
def mae(rng: random.Random) -> Generated:
    """MAE — среднее модулей ошибок |y − ŷ|."""
    size = rng.choice([4, 5, 6])
    y_true = [rng.randint(10, 90) for _ in range(size)]
    y_pred = [y + rng.choice([-1, 1]) * rng.randint(1, 15) for y in y_true]
    what = rng.choice(["время доставки, мин", "спрос, шт.", "число звонков в час", "цена, тыс. ₽"])
    value = sum(abs(t - p) for t, p in zip(y_true, y_pred, strict=True)) / size
    code = "\n".join([f"y_true = {y_true}", f"y_pred = {y_pred}"])
    return Generated(
        stem=f"Регрессионная модель ({what}) дала прогнозы y_pred. Чему равна MAE? Округлите до сотых.",
        code=code,
        code_language="python",
        number=round(value, 2),
        tolerance=0.01,
    )


# --- Базовые задания уровня Intern: открытый числовой ответ без угадывания ---

MEAN_CONTEXTS = [
    "Время ответа сервиса в пяти замерах, мс",
    "Число заказов за дни недели",
    "Число ошибок в логах по дням",
    "Длительность сессий, мин",
    "Возраст участников опроса",
]


@generator("data.mean_small")
def mean_small(rng: random.Random) -> Generated:
    """Среднее — сумма, делённая на число значений; выборка подобрана так, чтобы ответ был целым."""
    size = rng.choice([3, 4, 5])
    mean = rng.randint(4, 40)
    while True:
        values = [rng.randint(max(1, mean - 9), mean + 9) for _ in range(size - 1)]
        last = mean * size - sum(values)
        if last >= 1 and abs(last - mean) <= 12:
            break
    values.append(last)
    rng.shuffle(values)
    context = rng.choice(MEAN_CONTEXTS).replace("пяти", {3: "трёх", 4: "четырёх", 5: "пяти"}[size])
    return Generated(
        stem=f"{context}: {', '.join(map(str, values))}. Чему равно среднее арифметическое?",
        number=float(mean),
    )


ONEHOT_FEATURES = [
    ("city", CITIES),
    ("color", ["red", "green", "blue", "black", "white", "grey"]),
    ("device", ["ios", "android", "web", "tv", "desktop"]),
    ("payment", ["card", "cash", "sbp", "credit", "bonus"]),
]


@generator("data.onehot_columns")
def onehot_columns(rng: random.Random) -> Generated:
    """One-hot кодирование создаёт по столбцу на каждое уникальное значение категории."""
    feature, pool = rng.choice(ONEHOT_FEATURES)
    unique = rng.sample(pool, rng.randint(3, min(5, len(pool))))
    size = rng.randint(len(unique) + 2, len(unique) + 4)
    values = unique + [rng.choice(unique) for _ in range(size - len(unique))]
    rng.shuffle(values)
    stem = (
        f"Категориальный признак {feature} в обучающей выборке принимает значения: {', '.join(values)}. "
        "Его закодировали one-hot (по столбцу на каждое значение, без удаления одного из столбцов). "
        "Сколько столбцов получится из этого признака?"
    )
    return Generated(stem=stem, number=float(len(unique)))
