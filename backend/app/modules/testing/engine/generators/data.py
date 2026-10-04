"""Генераторы Data Science-заданий: SQL и pandas на сгенерированных таблицах, метрики, формы массивов.

Результаты запросов и кода вычисляются в чистом Python — код кандидата не исполняется.
"""

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
    disease = rng.choice(["диабет", "пневмонию", "редкое генетическое заболевание"])
    target = rng.choice(["время доставки", "стоимость ремонта", "длительность поездки"])
    cases = [
        (
            f"Модель для скрининга на {disease}: пропустить больного намного хуже, чем отправить здорового "
            "на дополнительное обследование. Какую метрику важнее всего максимизировать?",
            "Recall (полнота)",
            ["Precision (точность)", "Accuracy", "Specificity (специфичность)"],
        ),
        (
            "Модель автоматически блокирует аккаунты подозрительных пользователей. Каждая ошибочная "
            "блокировка честного пользователя очень дорога, а пропуск части нарушителей допустим. Какую "
            "метрику важнее всего максимизировать?",
            "Precision (точность)",
            ["Recall (полнота)", "Accuracy", "Доля предсказанных положительных"],
        ),
        (
            f"Регрессия на {target}: в данных есть редкие выбросы, и крупные ошибки на них не должны "
            "непропорционально влиять на оценку модели. Какую метрику выбрать?",
            "MAE",
            ["RMSE", "MSE", "R²"],
        ),
        (
            f"Регрессия на {target}: крупные ошибки особенно дороги, их нужно штрафовать сильнее, чем "
            "несколько мелких с той же суммой. Какую метрику выбрать?",
            "RMSE",
            ["MAE", "MAPE", "Медианная абсолютная ошибка"],
        ),
    ]
    stem, correct, wrong = rng.choice(cases)
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


@generator("data.task_type")
def task_type(rng: random.Random) -> Generated:
    """Тип задачи машинного обучения по постановке."""
    city = rng.choice(CITIES)
    cases = [
        (f"Предсказать цену квартиры в городе {city} по площади, этажу и району.", "Регрессия"),
        (f"Предсказать, сколько заказов поступит завтра в магазин в городе {city}.", "Регрессия"),
        ("Определить по тексту письма, спам это или нет, по размеченной выборке.", "Классификация"),
        ("Распознать рукописную цифру от 0 до 9 на изображении по размеченной выборке.", "Классификация"),
        (
            f"Разбить клиентов магазина в городе {city} на группы со схожим поведением; разметки нет.",
            "Кластеризация",
        ),
        ("Сжать 300 признаков до 2, чтобы визуализировать данные на плоскости.", "Понижение размерности"),
    ]
    stem, answer = rng.choice(cases)
    kinds = [
        "Регрессия",
        "Классификация",
        "Кластеризация",
        "Понижение размерности",
        "Обучение с подкреплением",
    ]
    return Generated(
        stem=f"К какому типу задач машинного обучения относится постановка? {stem}",
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
