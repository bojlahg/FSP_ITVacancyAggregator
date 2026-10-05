"""Статистика экспертной разметки (§12.4): доверительные интервалы, парное сравнение, согласие экспертов.

Чистые функции без БД — их же вызывает отчёт валидации (validation/matching_eval.py). Bootstrap
детерминирован по seed. Методика — docs/research/matching.md §4 (Sakai; Landis & Koch, 1977).
"""

import math
from collections.abc import Callable, Sequence

import numpy as np
from scipy.stats import binomtest, norm


def bootstrap_ci(
    values: Sequence[float], resamples: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float] | None:
    """Перцентильный bootstrap-интервал для среднего по потребностям; меньше двух значений — None."""
    data = np.asarray(values, dtype=float)
    if len(data) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = data[rng.integers(0, len(data), size=(resamples, len(data)))].mean(axis=1)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(low), float(high)


def bootstrap_statistic_ci[T](
    items: Sequence[T],
    statistic: Callable[[list[T]], float | None],
    resamples: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Перцентильный bootstrap-интервал произвольной статистики (например, κ по парам оценок)."""
    if len(items) < 2:
        return None
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        value = statistic([items[i] for i in rng.integers(0, len(items), size=len(items))])
        if value is not None and not math.isnan(value):
            values.append(value)
    if not values:
        return None
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(values, [tail, 100 - tail])
    return float(low), float(high)


def paired_bootstrap(
    a: Sequence[float], b: Sequence[float], resamples: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float, float] | None:
    """Разница средних a − b по одним и тем же потребностям: (разница, низ, верх ДИ, p двустороннее).

    p — доля bootstrap-разниц, сдвинутых к нулевой гипотезе, по модулю не меньше наблюдаемой
    (Efron & Tibshirani, 1993, §16.4).
    """
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if len(diff) < 2:
        return None
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), size=(resamples, len(diff)))].mean(axis=1)
    observed = float(diff.mean())
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    p_value = float(np.mean(np.abs(means - observed) >= abs(observed) - 1e-12)) if observed else 1.0
    return observed, float(low), float(high), p_value


def sign_test(a: Sequence[float], b: Sequence[float]) -> tuple[int, int, int, float | None]:
    """Знаковый тест по потребностям: (побед a, поражений, ничьих, p двустороннее, точный биномиальный)."""
    wins = sum(x > y for x, y in zip(a, b, strict=True))
    losses = sum(x < y for x, y in zip(a, b, strict=True))
    ties = len(a) - wins - losses
    if wins + losses == 0:
        return wins, losses, ties, None
    return wins, losses, ties, float(binomtest(wins, wins + losses, 0.5).pvalue)


def needs_for_power(sd_diff: float, delta: float, alpha: float = 0.05, power: float = 0.8) -> int | None:
    """Сколько потребностей нужно, чтобы парный тест заметил разницу delta (Sakai, topic set size design)."""
    if sd_diff <= 0 or delta <= 0:
        return None
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return math.ceil((z * sd_diff / delta) ** 2)


def ndcg(gains: Sequence[float], ideal_pool: Sequence[float], k: int) -> float | None:
    """nDCG@k с выигрышем 2^g − 1 (g — средняя оценка 0–3); идеал — лучшие k размеченных пар потребности."""

    def dcg(values: Sequence[float]) -> float:
        return sum((2**g - 1) / math.log2(position + 2) for position, g in enumerate(values[:k]))

    ideal = dcg(sorted(ideal_pool, reverse=True))
    return dcg(list(gains)) / ideal if ideal else None


def weighted_kappa(pairs: Sequence[tuple[int, int]], categories: int = 4) -> float | None:
    """Квадратично взвешенная κ Коэна по парам оценок двух экспертов (симметризованная)."""
    if len(pairs) < 2:
        return None
    observed = np.zeros((categories, categories))
    for a, b in pairs:
        observed[a, b] += 0.5
        observed[b, a] += 0.5
    observed /= len(pairs)
    marginal = observed.sum(axis=1)
    i, j = np.meshgrid(range(categories), range(categories), indexing="ij")
    weight = (i - j) ** 2 / (categories - 1) ** 2
    expected = float((weight * np.outer(marginal, marginal)).sum())
    if not expected:
        return None
    return round(1 - float((weight * observed).sum()) / expected, 3)


def krippendorff_alpha(units: Sequence[Sequence[int]]) -> float | None:
    """α Криппендорфа с интервальной метрикой: любое число экспертов на пару, пропуски допустимы."""
    pairable = [list(values) for values in units if len(values) >= 2]
    total = sum(len(values) for values in pairable)
    if total < 2:
        return None
    observed = sum(
        sum((x - y) ** 2 for x in values for y in values) / (len(values) - 1) for values in pairable
    )
    flat = np.asarray([x for values in pairable for x in values], dtype=float)
    expected = float(((flat[:, None] - flat[None, :]) ** 2).sum()) / (total - 1)
    if not expected:
        return None
    return round(1 - observed / expected, 3)


def landis_koch(kappa: float | None) -> str | None:
    """Интерпретация согласия по Landis & Koch (1977)."""
    if kappa is None:
        return None
    for bound, name in (
        (0.0, "хуже случайного"),
        (0.20, "незначительное"),
        (0.40, "слабое"),
        (0.60, "умеренное"),
        (0.80, "существенное"),
    ):
        if kappa < bound or (bound and kappa <= bound):
            return name
    return "почти полное"
