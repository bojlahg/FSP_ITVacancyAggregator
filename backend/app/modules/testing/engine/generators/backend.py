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


def _choice(stem: str, code: str, language: str, correct: object, wrong: list) -> Generated:
    """Один верный ответ и уникальные дистракторы в стабильном порядке.

    set не используется: порядок его обхода зависит от хеш-сида процесса, а рендер должен быть детерминирован.
    """
    right = str(correct)
    distractors = tuple(dict.fromkeys(str(value) for value in wrong if str(value) != right))
    return Generated(stem=stem, code=code, code_language=language, correct=(right,), wrong=distractors)


def _bool_triples(rng: random.Random) -> list[str]:
    combos = [" ".join("true" if mask >> bit & 1 else "false" for bit in range(3)) for mask in range(8)]
    rng.shuffle(combos)
    return combos


# --- SQL на маленьких сгенерированных таблицах ---

SQL_PAIRS = [
    ("users", "orders", "user_id"),
    ("authors", "books", "author_id"),
    ("customers", "payments", "customer_id"),
    ("departments", "employees", "department_id"),
    ("projects", "tasks", "project_id"),
]


@generator("backend.sql_left_join_rows")
def sql_left_join_rows(rng: random.Random) -> Generated:
    """LEFT JOIN: родитель без детей даёт одну строку с NULL, родитель с k детьми — k строк."""
    parent, child, fk = rng.choice(SQL_PAIRS)
    parents = list(range(1, rng.randint(3, 5) + 1))
    counts = dict.fromkeys(parents, 0)
    lonely, busy = rng.sample(parents, 2)
    counts[busy] = rng.randint(2, 3)
    for pid in parents:
        if pid not in (lonely, busy):
            counts[pid] = rng.randint(0, 2)
    fk_values: list[str] = []
    for pid in parents:
        fk_values += [str(pid)] * counts[pid]
    fk_values += ["NULL"] * rng.randint(0, 2)
    rng.shuffle(fk_values)
    start = 100 + rng.randint(1, 50)
    child_rows = ", ".join(f"({start + 10 * i}, {value})" for i, value in enumerate(fk_values))
    parent_rows = ", ".join(f"({pid})" for pid in parents)
    a, b = parent[0], child[0]
    code = (
        f"-- {parent}(id): {parent_rows}\n"
        f"-- {child}(id, {fk}): {child_rows}\n\n"
        f"SELECT {a}.id, {b}.id\n"
        f"FROM {parent} {a}\n"
        f"LEFT JOIN {child} {b} ON {b}.{fk} = {a}.id;"
    )
    answer = sum(max(1, count) for count in counts.values())
    inner = sum(counts.values())
    wrong = [inner, len(fk_values), len(parents), len(parents) * len(fk_values), answer + 1, answer - 1]
    stem = rng.choice(["Сколько строк вернёт запрос?", "Сколько строк будет в результате этого запроса?"])
    return _choice(stem, code, "sql", answer, wrong)


SQL_NULL_COLUMNS = [
    ("clients", "city", ["'Москва'", "'Казань'", "'Пермь'", "'Омск'", "'Тула'"]),
    ("tickets", "priority", ["1", "2", "3", "4"]),
    ("employees", "manager_id", ["7", "12", "15", "21"]),
    ("orders", "promo_code", ["'SALE'", "'NEW'", "'VIP'", "'BF'"]),
]


@generator("backend.sql_count_nulls")
def sql_count_nulls(rng: random.Random) -> Generated:
    """COUNT(*) считает строки, COUNT(col) пропускает NULL, COUNT(DISTINCT col) — уникальные не-NULL."""
    table, column, pool = rng.choice(SQL_NULL_COLUMNS)
    distinct = rng.sample(pool, rng.randint(2, 3))
    values = distinct + [rng.choice(distinct) for _ in range(rng.randint(1, 2))]
    nulls = rng.randint(1, 3)
    values += ["NULL"] * nulls
    rng.shuffle(values)
    total, non_null, uniq = len(values), len(values) - nulls, len(distinct)
    code = (
        f"-- значения {table}.{column}: " + ", ".join(values) + "\n\n"
        f"SELECT COUNT(*), COUNT({column}), COUNT(DISTINCT {column})\nFROM {table};"
    )
    wrong = [
        f"{total}, {total}, {uniq}",
        f"{total}, {non_null}, {uniq + 1}",
        f"{non_null}, {non_null}, {uniq}",
        f"{total}, {total}, {uniq + 1}",
        f"{total}, {non_null}, {non_null}",
    ]
    return _choice("Что вернёт запрос?", code, "sql", f"{total}, {non_null}, {uniq}", wrong)


def _group_sizes(rows: list[tuple[str, int]]) -> dict[str, int]:
    sizes: dict[str, int] = {}
    for name, _ in rows:
        sizes[name] = sizes.get(name, 0) + 1
    return sizes


@generator("backend.sql_group_having")
def sql_group_having(rng: random.Random) -> Generated:
    """WHERE фильтрует строки до группировки, HAVING — группы после неё."""
    table, key, value = rng.choice(
        [("orders", "customer", "amount"), ("payments", "merchant", "total"), ("visits", "doctor", "minutes")]
    )
    names = rng.sample(["'anna'", "'boris'", "'vera'", "'gleb'", "'dina'", "'egor'"], 4)
    threshold = rng.choice([100, 200, 300])
    min_count = rng.choice([2, 3])
    amounts = [v for v in range(threshold - 50, threshold + 250, 50) if v != threshold]
    while True:
        rows = [(rng.choice(names), rng.choice(amounts)) for _ in range(rng.randint(8, 10))]
        filtered = _group_sizes([row for row in rows if row[1] > threshold])
        answer = sum(1 for size in filtered.values() if size >= min_count)
        no_where = sum(1 for size in _group_sizes(rows).values() if size >= min_count)
        no_having = len(filtered)
        if len({answer, no_where, no_having}) == 3:
            break
    code = (
        f"-- {table}({key}, {value}):\n-- "
        + ", ".join(f"({name}, {amount})" for name, amount in rows)
        + f"\n\nSELECT {key}, SUM({value})\nFROM {table}\nWHERE {value} > {threshold}\n"
        f"GROUP BY {key}\nHAVING COUNT(*) >= {min_count};"
    )
    wrong = [no_where, no_having, answer + 1, max(answer - 1, 0), answer + 2, len(rows), 0]
    return _choice("Сколько строк вернёт запрос?", code, "sql", answer, wrong)


# --- Алгоритмы и структуры данных ---

STACK_PATTERNS = [
    ["push", "push", "pop", "push", "push", "pop", "push", "pop"],
    ["push", "push", "push", "pop", "push", "pop", "pop", "push"],
    ["push", "pop", "push", "push", "push", "pop", "pop", "push"],
]


@generator("backend.stack_ops")
def stack_ops(rng: random.Random) -> Generated:
    """Стек на list: pop() снимает последний добавленный элемент (LIFO)."""
    name = rng.choice(["stack", "st", "pending", "calls"])
    ops = rng.choice(STACK_PATTERNS)
    values = rng.sample(range(1, 30), ops.count("push"))
    stack: list[int] = []
    queue: list[int] = []
    popped: list[int] = []
    fifo: list[int] = []
    lines = [f"{name} = []", "out = []"]
    pushed = iter(values)
    for op in ops:
        if op == "push":
            value = next(pushed)
            stack.append(value)
            queue.append(value)
            lines.append(f"{name}.append({value})")
        else:
            popped.append(stack.pop())
            fifo.append(queue.pop(0))
            lines.append(f"out.append({name}.pop())")
    lines.append("print(out)")
    wrong = [fifo, list(reversed(popped)), values[:3], values[-3:], sorted(popped), stack]
    return _choice("Что выведет этот код?", "\n".join(lines), "python", popped, wrong)


def _simulate_cache(ops: list[tuple[str, str]], capacity: int, policy: str) -> list[str]:
    order: list[str] = []
    for op, key in ops:
        if key in order:
            if policy == "lru":
                order.remove(key)
                order.append(key)
            continue
        if op == "get":
            continue
        if len(order) == capacity:
            order.pop(-1 if policy == "mru" else 0)
        order.append(key)
    return sorted(order)


@generator("backend.lru_cache_state")
def lru_cache_state(rng: random.Random) -> Generated:
    """LRU вытесняет ключ, к которому дольше всех не обращались; get обновляет «свежесть»."""
    capacity = rng.choice([2, 3])
    keys = rng.sample(list("abcdefgkmp"), capacity + 2)
    while True:
        ops = [("put", key) for key in keys[:capacity]]
        ops.append(("get", keys[0]))
        for key in keys[capacity:] + rng.sample(keys[: capacity + 1], 1):
            if rng.random() < 0.4:
                ops.append(("get", rng.choice(keys[:capacity])))
            ops.append(("put", key))
        lru = _simulate_cache(ops, capacity, "lru")
        fifo = _simulate_cache(ops, capacity, "fifo")
        if lru != fifo:
            break
    mru = _simulate_cache(ops, capacity, "mru")
    others = [sorted(rng.sample(keys, capacity)) for _ in range(8)]
    wrong = [", ".join(combo) for combo in [fifo, mru, *others]]
    return _choice(
        f"LRU-кеш ёмкостью {capacity} изначально пуст. Над ним выполнены операции по порядку (get по "
        "отсутствующему ключу ничего не добавляет, put существующего ключа обновляет значение "
        "и тоже считается обращением). "
        "Какие ключи останутся в кеше?",
        "\n".join(f"{op}({key!r})" for op, key in ops),
        "text",
        ", ".join(lru),
        wrong,
    )


# --- Python ---


@generator("backend.python_slicing")
def python_slicing(rng: random.Random) -> Generated:
    """Срез [i:j] не включает j; [-k:] — последние k элементов."""
    name = rng.choice(["nums", "data", "scores", "ids"])
    values = rng.sample(range(10, 99), rng.randint(7, 9))
    i = rng.randint(1, 3)
    j = rng.randint(i + 2, len(values) - 2)
    k = rng.randint(2, 3)
    code = f"{name} = {values}\nprint({name}[{i}:{j}], {name}[-{k}:])"
    wrong = [
        f"{values[i : j + 1]} {values[-k:]}",
        f"{values[i - 1 : j]} {values[-k:]}",
        f"{values[i:j]} {values[-k - 1 :]}",
        f"{values[i:j]} {values[:k]}",
        f"{values[i - 1 : j - 1]} {values[-k:]}",
        f"{values[i : j + 1]} {values[-k - 1 : -1]}",
    ]
    return _choice("Что выведет этот код?", code, "python", f"{values[i:j]} {values[-k:]}", wrong)


@generator("backend.python_list_multiply_alias")
def python_list_multiply_alias(rng: random.Random) -> Generated:
    """[[0] * c] * r — r ссылок на один и тот же внутренний список."""
    name = rng.choice(["grid", "board", "matrix", "field"])
    rows, cols = rng.sample(range(2, 6), 2)
    value = rng.randint(2, 9)
    r, c = rng.randrange(rows), rng.randrange(cols)
    code = (
        f"{name} = [[0] * {cols}] * {rows}\n"
        f"{name}[{r}][{c}] = {value}\n"
        f"print(sum(sum(row) for row in {name}))"
    )
    wrong = [value, value * cols, value * rows * cols, 0, "IndexError", value * (rows - 1)]
    return _choice("Что выведет этот код?", code, "python", value * rows, wrong)


@generator("backend.python_generator_exhaust")
def python_generator_exhaust(rng: random.Random) -> Generated:
    """Генераторное выражение одноразовое: второй проход по нему пуст."""
    data = rng.sample(range(1, 10), rng.randint(3, 5))
    factor = rng.randint(2, 5)
    var = rng.choice(["gen", "items", "stream", "values"])
    if rng.random() < 0.5:
        expr, total = f"sum({var})", sum(x * factor for x in data)
    else:
        expr, total = f"len(list({var}))", len(data)
    code = f"data = {data}\n{var} = (x * {factor} for x in data)\nprint({expr}, {expr})"
    wrong = [f"{total} {total}", "0 0", f"{total} None", f"0 {total}", f"{total} {total * 2}"]
    return _choice("Что выведет этот код?", code, "python", f"{total} 0", wrong)


@generator("backend.python_late_binding")
def python_late_binding(rng: random.Random) -> Generated:
    """Замыкание захватывает переменную, а не значение: все лямбды видят последнее значение."""
    n = rng.randint(3, 5)
    k = rng.randint(2, 7)
    var = rng.choice(["i", "n", "idx", "step"])
    if rng.random() < 0.5:
        code = (
            f"funcs = []\nfor {var} in range({n}):\n    funcs.append(lambda: {var} * {k})\n\n"
            "print([f() for f in funcs])"
        )
    else:
        code = f"funcs = [lambda: {var} * {k} for {var} in range({n})]\nprint([f() for f in funcs])"
    wrong = [
        [i * k for i in range(n)],
        [n * k] * n,
        [0] * n,
        [i * k for i in range(1, n + 1)],
    ]
    return _choice("Что выведет этот код?", code, "python", [(n - 1) * k] * n, wrong)


@generator("backend.python_context_managers")
def python_context_managers(rng: random.Random) -> Generated:
    """with a, b: — вход слева направо, выход в обратном порядке, finally выполняется всегда."""
    names = rng.sample(["db", "tx", "lock", "file", "cache", "conn"], rng.choice([2, 3]))
    body = rng.choice(["body", "work", "run"])
    code = (
        "from contextlib import contextmanager\n\n\n"
        "@contextmanager\n"
        "def res(name):\n"
        '    print(f"+{name}", end=" ")\n'
        "    try:\n"
        "        yield\n"
        "    finally:\n"
        '        print(f"-{name}", end=" ")\n\n\n'
        "with " + ", ".join(f'res("{n}")' for n in names) + ":\n"
        f'    print("{body}", end=" ")'
    )
    enter = [f"+{n}" for n in names]
    exit_reversed = [f"-{n}" for n in reversed(names)]
    exit_direct = [f"-{n}" for n in names]
    wrong = [
        " ".join([*enter, body, *exit_direct]),
        " ".join([x for n in names for x in (f"+{n}", f"-{n}")] + [body]),
        " ".join([body, *enter, *exit_reversed]),
        " ".join([*reversed(enter), body, *exit_direct]),
        " ".join([*enter, *exit_reversed, body]),
    ]
    return _choice("Что выведет этот код?", code, "python", " ".join([*enter, body, *exit_reversed]), wrong)


# --- Java ---

INT_MIN, INT_MAX = -(2**31), 2**31 - 1


def _java_int(value: int) -> int:
    return (value - INT_MIN) % 2**32 + INT_MIN


@generator("backend.java_int_overflow")
def java_int_overflow(rng: random.Random) -> Generated:
    """int переполняется по модулю 2^32 без исключения: MAX_VALUE + 1 == MIN_VALUE."""
    var = rng.choice(["total", "counter", "sum", "balance"])
    k = rng.randint(1, 50)
    m = k + rng.randint(1, 60)
    exact = INT_MAX - k + m
    correct = _java_int(exact)
    code = f"int {var} = Integer.MAX_VALUE - {k};\n{var} += {m};\nSystem.out.println({var});"
    wrong = [exact, INT_MAX, correct + 1, INT_MIN, "ArithmeticException: integer overflow"]
    return _choice("Что выведет этот фрагмент Java-кода?", code, "java", correct, wrong)


@generator("backend.java_string_identity")
def java_string_identity(rng: random.Random) -> Generated:
    """== сравнивает ссылки: одинаковые литералы — один объект (JLS §3.10.5), new String — новый."""
    word = rng.choice(["itscout", "hello", "order", "java", "token", "admin"])
    a, b, c = rng.sample(["s1", "s2", "s3", "x", "y", "z"], 3)
    exprs = [
        (f"({a} == {b})", True),
        (f"({a} == {c})", False),
        (f"{a}.equals({c})", True),
        (f"({b} == {c})", False),
    ]
    chosen = rng.sample(exprs, 3)
    code = (
        f'String {a} = "{word}";\n'
        f'String {b} = "{word}";\n'
        f'String {c} = new String("{word}");\n'
        "System.out.println(" + ' + " " + '.join(expr for expr, _ in chosen) + ");"
    )
    correct = " ".join(str(value).lower() for _, value in chosen)
    return _choice("Что выведет этот фрагмент Java-кода?", code, "java", correct, _bool_triples(rng))


@generator("backend.java_division_negative")
def java_division_negative(rng: random.Random) -> Generated:
    """В Java целочисленное деление округляет к нулю, знак остатка совпадает со знаком делимого."""
    x = rng.randint(7, 40)
    y = rng.randint(2, 6)
    while x % y == 0:
        x += 1
    a, b = (-x, y) if rng.random() < 0.5 else (x, -y)
    q = abs(a) // abs(b) * (1 if (a > 0) == (b > 0) else -1)
    r = a - b * q
    fq, fr = a // b, a % b
    left, right = rng.choice([("a", "b"), ("x", "y"), ("m", "n")])
    code = (
        f"int {left} = {a};\nint {right} = {b};\n"
        f'System.out.println({left} / {right} + " " + {left} % {right});'
    )
    wrong = [f"{fq} {fr}", f"{q} {-r}", f"{fq} {r}", f"{q} {fr}", f"{-q} {r}"]
    return _choice("Что выведет этот фрагмент Java-кода?", code, "java", f"{q} {r}", wrong)


@generator("backend.java_stream_short_circuit")
def java_stream_short_circuit(rng: random.Random) -> Generated:
    """Stream ленивый и поэлементный: findFirst останавливает конвейер на первом подходящем элементе."""
    threshold = rng.choice([10, 20, 50])
    small = rng.sample(range(1, threshold), 4)
    big = rng.sample(range(threshold + 1, threshold * 3), 2)
    pos = rng.randint(1, 3)
    values = small[:pos] + [big[0]] + small[pos : pos + 1] + [big[1]] + small[pos + 1 : pos + 2]
    first = values.index(big[0])
    code = (
        f"List<Integer> xs = List.of({', '.join(map(str, values))});\n"
        "Optional<Integer> r = xs.stream()\n"
        "    .filter(x -> {\n"
        '        System.out.print(x + " ");\n'
        f"        return x > {threshold};\n"
        "    })\n"
        "    .findFirst();"
    )

    def show(items: list[int]) -> str:
        return " ".join(map(str, items))

    wrong = [
        show(values),
        show([big[0]]),
        show(values[:first]),
        show([v for v in values if v > threshold]),
        "(ничего не выведет)",
    ]
    return _choice(
        "Что выведет этот фрагмент Java-кода (пробелы в конце строки не важны)?",
        code,
        "java",
        show(values[: first + 1]),
        wrong,
    )


# --- Go ---


@generator("backend.go_defer_order")
def go_defer_order(rng: random.Random) -> Generated:
    """defer выполняется в порядке LIFO при выходе из функции; аргументы вычисляются в момент defer."""
    n = rng.randint(3, 4)
    k = rng.randint(2, 5)
    word = rng.choice(["end", "done", "main", "exit"])
    code = (
        'package main\n\nimport "fmt"\n\nfunc main() {\n'
        f"\tfor i := 1; i <= {n}; i++ {{\n"
        f'\t\tdefer fmt.Print(i*{k}, ";")\n'
        "\t}\n"
        f'\tfmt.Print("{word};")\n'
        "}"
    )
    vals = [str(i * k) for i in range(1, n + 1)]
    wrong = [
        ";".join([*vals, word]) + ";",
        ";".join([word, *vals]) + ";",
        ";".join([*vals[::-1], word]) + ";",
        ";".join([word] + [str((n + 1) * k)] * n) + ";",
    ]
    return _choice("Что выведет программа на Go?", code, "go", ";".join([word, *vals[::-1]]) + ";", wrong)


GO_FIELDS = [
    ("Name", "string", "", ['""', "<nil>"]),
    ("Age", "int", "0", ["<nil>"]),
    ("Active", "bool", "false", ["0", "<nil>"]),
    ("Score", "float64", "0", ["0.0", "<nil>"]),
    ("Tags", "[]string", "[]", ["<nil>", "nil"]),
    ("Meta", "map[string]int", "map[]", ["<nil>", "nil"]),
]


@generator("backend.go_zero_values")
def go_zero_values(rng: random.Random) -> Generated:
    """Нулевые значения Go и их печать через %+v: nil-срез — [], nil-map — map[]."""
    type_name = rng.choice(["User", "Order", "Config", "Job"])
    fields = rng.sample(GO_FIELDS, 3)
    width = max(len(field[0]) for field in fields)
    body = "\n".join(f"\t{name.ljust(width)} {typ}" for name, typ, _, _ in fields)
    var = type_name[0].lower()
    code = (
        'package main\n\nimport "fmt"\n\n'
        f"type {type_name} struct {{\n{body}\n}}\n\n"
        f'func main() {{\n\tvar {var} {type_name}\n\tfmt.Printf("%+v\\n", {var})\n}}'
    )

    def show(renders: list[str]) -> str:
        return "{" + " ".join(f"{f[0]}:{r}" for f, r in zip(fields, renders, strict=True)) + "}"

    right = [field[2] for field in fields]
    wrong: list[str] = []
    for index, field in enumerate(fields):
        for alt in field[3]:
            changed = right[:]
            changed[index] = alt
            wrong.append(show(changed))
    wrong += [show(["<nil>"] * 3), "panic: nil pointer dereference"]
    rng.shuffle(wrong)
    return _choice("Что выведет программа на Go?", code, "go", show(right), wrong)


GO_WORDS = ["привет", "кот", "go-код", "ёжик", "мир42", "data-база", "тест", "api-ключ", "сервер1"]


@generator("backend.go_string_len")
def go_string_len(rng: random.Random) -> Generated:
    """len(string) в Go — длина в байтах UTF-8; кириллица занимает 2 байта на символ."""
    word = rng.choice(GO_WORDS)
    var = rng.choice(["s", "word", "title", "msg"])
    code = (
        'package main\n\nimport (\n\t"fmt"\n\t"unicode/utf8"\n)\n\n'
        f'func main() {{\n\t{var} := "{word}"\n\tfmt.Println(len({var}), utf8.RuneCountInString({var}))\n}}'
    )
    nbytes, runes = len(word.encode("utf-8")), len(word)
    wrong = [
        f"{runes} {runes}",
        f"{runes} {nbytes}",
        f"{nbytes} {nbytes}",
        f"{runes * 2} {runes}",
        f"{runes * 4} {runes}",
    ]
    return _choice(
        "Исходный файл сохранён в UTF-8. Что выведет программа?", code, "go", f"{nbytes} {runes}", wrong
    )


@generator("backend.go_slice_append_shared")
def go_slice_append_shared(rng: random.Random) -> Generated:
    """append в пределах cap пишет в общий массив: два append от одного среза перетирают друг друга"""
    n = rng.randint(2, 4)
    cap = n + rng.randint(2, 4)
    x, y = rng.sample(range(10, 99), 2)
    a, b, c = rng.choice([("a", "b", "c"), ("base", "left", "right"), ("s", "s1", "s2")])
    code = (
        'package main\n\nimport "fmt"\n\nfunc main() {\n'
        f"\t{a} := make([]int, {n}, {cap})\n"
        f"\t{b} := append({a}, {x})\n"
        f"\t{c} := append({a}, {y})\n"
        f"\tfmt.Println({b}[{n}], {c}[{n}], len({a}))\n"
        "}"
    )
    wrong = [
        f"{x} {y} {n}",
        f"{x} {x} {n}",
        f"{x} {y} {n + 2}",
        f"{y} {y} {n + 2}",
        "panic: runtime error: index out of range",
    ]
    return _choice("Что выведет программа на Go?", code, "go", f"{y} {y} {n}", wrong)


@generator("backend.go_errors_is")
def go_errors_is(rng: random.Random) -> Generated:
    """%w оборачивает ошибку: errors.Is и errors.Unwrap видят исходную, а == сравнивает сами значения."""
    err_name, message = rng.choice(
        [
            ("ErrNotFound", "not found"),
            ("ErrTimeout", "timeout"),
            ("ErrForbidden", "forbidden"),
            ("ErrConflict", "conflict"),
        ]
    )
    context = rng.choice(["load user %d", "get order %d", "fetch item %d"])
    ident = rng.randint(2, 999)
    exprs = [
        (f"errors.Is(err, {err_name})", True),
        (f"err == {err_name}", False),
        (f"errors.Unwrap(err) == {err_name}", True),
        (f'errors.Is(err, errors.New("{message}"))', False),
    ]
    chosen = rng.sample(exprs, 3)
    code = (
        'package main\n\nimport (\n\t"errors"\n\t"fmt"\n)\n\n'
        f'var {err_name} = errors.New("{message}")\n\n'
        f'func find() error {{\n\treturn fmt.Errorf("{context}: %w", {ident}, {err_name})\n}}\n\n'
        "func main() {\n\terr := find()\n\tfmt.Println(" + ", ".join(e for e, _ in chosen) + ")\n}"
    )
    correct = " ".join(str(value).lower() for _, value in chosen)
    return _choice("Что выведет программа на Go?", code, "go", correct, _bool_triples(rng))


# --- C# ---


@generator("backend.csharp_linq_deferred")
def csharp_linq_deferred(rng: random.Random) -> Generated:
    """LINQ Where — отложенное выполнение: запрос считается при перечислении и видит изменения списка."""
    threshold = rng.choice([10, 20, 50])
    values = rng.sample(range(1, threshold * 2), rng.randint(5, 7))
    added = rng.randint(threshold + 1, threshold * 3)
    var = rng.choice(["big", "selected", "query", "filtered"])
    code = (
        f"var nums = new List<int> {{ {', '.join(map(str, values))} }};\n"
        f"var {var} = nums.Where(x => x > {threshold});\n"
        f"nums.Add({added});\n"
        f"Console.WriteLine({var}.Count());"
    )
    before = sum(1 for v in values if v > threshold)
    wrong = [before, len(values) + 1, len(values), before + 2, max(before - 1, 0)]
    return _choice("Что выведет этот код на C#?", code, "csharp", before + 1, wrong)


@generator("backend.csharp_struct_vs_class")
def csharp_struct_vs_class(rng: random.Random) -> Generated:
    """struct копируется при присваивании, у class копируется ссылка."""
    s_name, c_name = rng.choice([("PointS", "PointC"), ("MoneyV", "MoneyR"), ("SizeS", "SizeC")])
    a, b = rng.sample(range(1, 50), 2)
    # top-level statements в C# должны идти до объявлений типов
    code = (
        f"var s1 = new {s_name} {{ X = {a} }};\n"
        "var s2 = s1;\n"
        f"s2.X = {b};\n"
        f"var c1 = new {c_name} {{ X = {a} }};\n"
        "var c2 = c1;\n"
        f"c2.X = {b};\n"
        'Console.WriteLine($"{s1.X} {c1.X}");\n\n'
        f"struct {s_name} {{ public int X; }}\n"
        f"class {c_name} {{ public int X; }}"
    )
    wrong = [f"{b} {b}", f"{a} {a}", f"{b} {a}"]
    return _choice("Что выведет этот код на C#?", code, "csharp", f"{a} {b}", wrong)


# --- Node.js ---


@generator("backend.node_event_loop_order")
def node_event_loop_order(rng: random.Random) -> Generated:
    """Сначала синхронный код, затем все микрозадачи (then, queueMicrotask) по очереди, затем таймеры."""
    letters = rng.sample(list("ABCDEFGHKMPRSTXZ"), 6)
    kinds = ["sync", "sync", "timer", "micro", "micro", rng.choice(["timer", "micro", "sync"])]
    rng.shuffle(kinds)
    lines = []
    for letter, kind in zip(letters, kinds, strict=True):
        if kind == "sync":
            lines.append(f"console.log('{letter}');")
        elif kind == "timer":
            lines.append(f"setTimeout(() => console.log('{letter}'), 0);")
        elif rng.random() < 0.5:
            lines.append(f"Promise.resolve().then(() => console.log('{letter}'));")
        else:
            lines.append(f"queueMicrotask(() => console.log('{letter}'));")
    by_kind = {
        kind: [letter for letter, k in zip(letters, kinds, strict=True) if k == kind]
        for kind in ("sync", "micro", "timer")
    }
    sync, micro, timer = by_kind["sync"], by_kind["micro"], by_kind["timer"]
    wrong = [
        " ".join(letters),
        " ".join(sync + timer + micro),
        " ".join(sync + [x for x in letters if x not in sync]),
        " ".join(micro + sync + timer),
        " ".join(sync + micro[::-1] + timer),
    ]
    return _choice(
        "В каком порядке Node.js выведет буквы?",
        "\n".join(lines),
        "javascript",
        " ".join(sync + micro + timer),
        wrong,
    )


# --- HTTP ---

HTTP_CODES = {
    "success": [
        "200 OK",
        "201 Created",
        "202 Accepted",
        "204 No Content",
        "206 Partial Content",
    ],
    "redirect": [
        "301 Moved Permanently",
        "302 Found",
        "303 See Other",
        "304 Not Modified",
        "307 Temporary Redirect",
        "308 Permanent Redirect",
    ],
    "client": [
        "400 Bad Request",
        "401 Unauthorized",
        "403 Forbidden",
        "404 Not Found",
        "405 Method Not Allowed",
        "409 Conflict",
        "410 Gone",
        "413 Content Too Large",
        "415 Unsupported Media Type",
        "422 Unprocessable Content",
        "429 Too Many Requests",
    ],
    "server": [
        "500 Internal Server Error",
        "501 Not Implemented",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "504 Gateway Timeout",
    ],
}
HTTP_CLASS_TEXT = {
    "success": [
        "Запрос успешно получен и обработан (класс 2xx)",
        "Успешный ответ: сервер выполнил запрос (класс 2xx)",
    ],
    "redirect": [
        "Перенаправление: для завершения запроса клиенту нужно действие, например перейти"
        " по другому адресу (класс 3xx)",
        "Перенаправление или ответ из кеша клиента (класс 3xx)",
    ],
    "client": [
        "Ошибка клиента: запрос некорректен или не может быть выполнен для этого клиента (класс 4xx)",
        "Ошибка на стороне клиента (класс 4xx)",
    ],
    "server": [
        "Ошибка сервера: запрос корректен, но сервер или вышестоящий сервис"
        " не смог его выполнить (класс 5xx)",
        "Ошибка на стороне сервера (класс 5xx)",
    ],
    "info": [
        "Информационный промежуточный ответ: обработка продолжается (класс 1xx)",
    ],
}


@generator("backend.http_status_class")
def http_status_class(rng: random.Random) -> Generated:
    """Класс ответа — первая цифра кода: 2xx успех, 3xx перенаправление, 4xx клиент, 5xx сервер."""
    kind = rng.choice(list(HTTP_CODES))
    code = rng.choice(HTTP_CODES[kind])
    number = code.split()[0]
    method, path = rng.choice(
        [
            ("GET", "/api/orders"),
            ("POST", "/api/payments"),
            ("PUT", "/api/profile"),
            ("DELETE", "/api/sessions/current"),
            ("GET", "/static/app.js"),
            ("PATCH", "/api/tasks/17"),
        ]
    )
    stem = rng.choice(
        [
            f"На запрос {method} {path} сервер вернул статус {number}. "
            "К какому классу ответов по RFC 9110 он относится?",
            f"В логах балансировщика у запроса {method} {path} код ответа {number}. "
            "Что означает ответ с таким кодом?",
            f"Клиент получил на {method} {path} HTTP-ответ с кодом {number}. "
            "Какое описание класса этого ответа верно?",
        ]
    )
    correct = rng.choice(HTTP_CLASS_TEXT[kind])
    wrong = [rng.choice(texts) for other, texts in HTTP_CLASS_TEXT.items() if other != kind]
    rng.shuffle(wrong)
    return Generated(stem=stem, correct=(correct,), wrong=tuple(wrong))


# --- Сложность простых циклов ---

LOOP_PATTERNS = [
    (
        "O(n)",
        "def {fn}({arr}):\n    total = 0\n    for x in {arr}:\n        total += x\n    return total",
    ),
    (
        "O(n)",
        "def {fn}({arr}):\n    best = {arr}[0]\n    for x in {arr}:\n"
        "        if x > best:\n            best = x\n"
        "    for x in {arr}:\n        print(x - best)\n    return best",
    ),
    (
        "O(n²)",
        "def {fn}({arr}):\n    count = 0\n    for a in {arr}:\n"
        "        for b in {arr}:\n            if a == b:\n"
        "                count += 1\n    return count",
    ),
    (
        "O(log n)",
        "def {fn}(n):\n    steps = 0\n    while n > 1:\n"
        "        n //= 2\n        steps += 1\n    return steps",
    ),
    (
        "O(1)",
        "def {fn}({arr}):\n    return {arr}[0] + {arr}[-1]",
    ),
    (
        "O(n)",
        "def {fn}({arr}):\n    for x in {arr}:\n        for k in range(10):\n            print(x * k)",
    ),
]
COMPLEXITIES = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n²)", "O(2ⁿ)"]


@generator("backend.algo_loop_complexity")
def algo_loop_complexity(rng: random.Random) -> Generated:
    """Асимптотика простого кода: один проход — O(n), вложенный по n — O(n²), деление пополам — O(log n)."""
    answer, template = rng.choice(LOOP_PATTERNS)
    fn = rng.choice(["process", "check", "summarize", "scan", "analyze", "count_items"])
    arr = rng.choice(["items", "values", "prices", "scores", "ids"])
    code = template.format(fn=fn, arr=arr)
    size = "n — длина списка" if "{arr}" in template else "n — значение аргумента"
    stem = rng.choice(
        [
            f"Какова временная сложность функции {fn} ({size})?",
            f"Оцените время работы {fn} в нотации O-большое ({size}).",
        ]
    )
    wrong = [c for c in COMPLEXITIES if c != answer]
    return Generated(stem=stem, code=code, code_language="python", correct=(answer,), wrong=tuple(wrong))


# --- Python: dict.get ---

DICT_DATA = [
    ("prices", ["apple", "pear", "plum", "kiwi", "lime"]),
    ("stock", ["pens", "cups", "bags", "hats", "maps"]),
    ("ages", ["anna", "boris", "vera", "gleb", "dina"]),
    ("ports", ["http", "https", "ssh", "smtp", "dns"]),
]


@generator("backend.python_dict_get")
def python_dict_get(rng: random.Random) -> Generated:
    """dict.get(k, d) без ключа даёт d, get(k) без default — None; KeyError бывает только у d[k]."""
    name, keys = rng.choice(DICT_DATA)
    present = rng.sample(keys, 2)
    missing = [k for k in keys if k not in present]
    absent_a, absent_b = rng.sample(missing, 2)
    values = rng.sample(range(5, 99), 2)
    default = rng.choice([0, -1, 1])
    data = ", ".join(f'"{k}": {v}' for k, v in zip(present, values, strict=True))
    code = (
        f"{name} = {{{data}}}\n"
        f'print({name}.get("{absent_a}", {default}), {name}.get("{present[1]}", {default}), '
        f'{name}.get("{absent_b}"))'
    )
    right = f"{default} {values[1]} None"
    wrong = [
        "KeyError",
        f"{default} {values[1]} {default}",
        f"None {values[1]} None",
        f"{default} {default} None",
        f"{default} {values[1]} KeyError",
        f"{default} {values[0]} None",
    ]
    return _choice("Что выведет этот код?", code, "python", right, wrong)


# --- C#: целочисленное деление ---


@generator("backend.csharp_int_division")
def csharp_int_division(rng: random.Random) -> Generated:
    """int / int в C# — целочисленное деление; присваивание в double дробную часть не вернёт."""
    a = rng.randint(7, 60)
    b = rng.randint(2, 9)
    while a % b == 0:
        a += 1
    x, y, r = rng.choice(
        [("a", "b", "r"), ("total", "count", "avg"), ("sum", "n", "mean"), ("items", "pages", "ratio")]
    )
    code = f"int {x} = {a};\nint {y} = {b};\ndouble {r} = {x} / {y};\nConsole.WriteLine({r});"
    q = a // b
    exact = round(a / b, 2)
    wrong = [
        f"{exact:g}",
        f"{q}.0",
        q + 1,
        f"{q} (остаток {a % b})",
        "Ошибка компиляции: нельзя присвоить int переменной double",
    ]
    return _choice(
        "Что выведет этот код на C#? (Культура вывода не влияет на ответ.)", code, "csharp", q, wrong
    )


# --- Node.js ---


@generator("backend.node_await_loop_time")
def node_await_loop_time(rng: random.Random) -> Generated:
    """await в цикле выполняет операции последовательно (n · t), Promise.all — параллельно (≈ t)."""
    fn = rng.choice(["fetchUser", "loadPrice", "getStock", "readProfile", "sendPing"])
    n = rng.randint(3, 12)
    ms = rng.choice([50, 80, 100, 120, 150, 200, 250, 300])
    sequential = rng.random() < 0.6
    if sequential:
        body = (
            "  const out = [];\n"
            "  for (const id of ids) {\n"
            f"    out.push(await {fn}(id));\n"
            "  }\n"
            "  return out;"
        )
        answer = n * ms
    else:
        body = f"  return Promise.all(ids.map((id) => {fn}(id)));"
        answer = ms
    code = f"async function loadAll(ids) {{\n{body}\n}}\n\nawait loadAll(ids); // ids.length === {n}"
    stem = (
        f"Каждый вызов {fn}() — сетевой запрос, который всегда занимает ровно {ms} мс и не нагружает CPU; "
        f"сервер обрабатывает любое число запросов одновременно. Массив ids содержит {n} элементов. "
        "Сколько миллисекунд займёт loadAll(ids)? Накладными расходами пренебречь."
    )
    return Generated(stem=stem, code=code, code_language="javascript", number=float(answer), tolerance=0)


@generator("backend.node_module_cache")
def node_module_cache(rng: random.Random) -> Generated:
    """require кеширует модуль: все импортирующие файлы получают один и тот же объект и общее состояние."""
    mod = rng.choice(["counter", "registry", "store", "metrics"])
    fn = rng.choice(["inc", "next", "track", "bump"])
    a_calls = rng.randint(1, 4)
    b_calls = rng.randint(1, 3)
    start = rng.choice([0, 10, 100])
    code = (
        f"// {mod}.js\nlet n = {start};\nmodule.exports = {{ {fn}: () => ++n }};\n\n"
        f"// a.js\nconst m = require('./{mod}');\n" + f"m.{fn}();\n" * a_calls + "\n"
        f"// b.js\nconst m = require('./{mod}');\n"
        + f"m.{fn}();\n"
        * (b_calls - 1)
        + f"console.log(m.{fn}());\n\n"
        "// main.js\nrequire('./a');\nrequire('./b');"
    )
    right = start + a_calls + b_calls
    wrong = [start + b_calls, start + 1, start + a_calls, right + 1, start, "undefined"]
    return _choice(
        "Проект на Node.js (CommonJS). Что выведет node main.js?", code, "javascript", right, wrong
    )


# --- Базовые задания уровня Intern: открытый числовой ответ без угадывания ---

ACCESS_PATHS = ["/api/users", "/api/orders", "/api/cart", "/login", "/api/items/7", "/health", "/api/search"]
ACCESS_METHODS = ["GET", "GET", "POST", "PUT", "DELETE"]


@generator("backend.http_count_client_errors")
def http_count_client_errors(rng: random.Random) -> Generated:
    """Класс ответа — первая цифра кода: 4xx — ошибки клиента."""
    total = rng.randint(7, 9)
    client = rng.randint(2, 4)
    server = rng.randint(1, 2)
    kinds = ["client"] * client + ["server"] * server
    kinds += [rng.choice(["success", "success", "redirect"]) for _ in range(total - len(kinds))]
    rng.shuffle(kinds)
    lines = []
    for kind in kinds:
        code = rng.choice(HTTP_CODES[kind]).split()[0]
        lines.append(f"{rng.choice(ACCESS_METHODS):<6} {rng.choice(ACCESS_PATHS):<14} {code}")
    stem = rng.choice(
        [
            "Фрагмент лога доступа сервиса: метод, путь, код ответа. "
            "Сколько ответов относятся к ошибкам клиента (4xx)?",
            "В логе API за минуту записаны запросы и коды ответов. "
            "Сколько из них — ошибки клиента (класс 4xx)?",
        ]
    )
    return Generated(stem=stem, code="\n".join(lines), code_language="text", number=float(client))


TASK_STATUSES = ["todo", "in_progress", "done"]
TASK_TITLES = ["login", "signup", "cart", "search", "profile", "payment", "export", "logout", "billing"]


@generator("backend.sql_where_equals_rows")
def sql_where_equals_rows(rng: random.Random) -> Generated:
    """WHERE с одним условием равенства: считаем подходящие строки маленькой таблицы."""
    while True:
        titles = rng.sample(TASK_TITLES, rng.randint(6, 8))
        rows = [(i + 1, title, rng.choice(TASK_STATUSES)) for i, title in enumerate(titles)]
        status = rng.choice(TASK_STATUSES)
        answer = sum(1 for row in rows if row[2] == status)
        if 2 <= answer <= len(rows) - 2:
            break
    values = ",\n  ".join(f"({row[0]}, '{row[1]}', '{row[2]}')" for row in rows)
    code = (
        "CREATE TABLE tasks (id int, title text, status text);\n"
        f"INSERT INTO tasks VALUES\n  {values};\n\n"
        f"SELECT * FROM tasks WHERE status = '{status}';"
    )
    return Generated(
        stem="Сколько строк вернёт последний запрос?", code=code, code_language="sql", number=float(answer)
    )


LIST_WORDS = ["'a'", "'b'", "'c'", "'x'", "'y'", "1", "2", "3", "5", "8", "None", "True"]


@generator("backend.python_list_append_len")
def python_list_append_len(rng: random.Random) -> Generated:
    """Каждый append добавляет в конец списка ровно один элемент."""
    name = rng.choice(NAMES)
    initial = rng.sample(LIST_WORDS, rng.randint(2, 5))
    appends = rng.sample(LIST_WORDS, rng.randint(1, 3))
    code = f"{name} = [{', '.join(initial)}]\n"
    code += "".join(f"{name}.append({value})\n" for value in appends)
    code += f"print(len({name}))"
    return Generated(
        stem="Что выведет этот код на Python?",
        code=code,
        code_language="python",
        number=float(len(initial) + len(appends)),
    )
