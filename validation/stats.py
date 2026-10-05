"""Статистики отчёта: согласие, κ Коэна, корреляции, метрики ранжирования."""

import math
from collections.abc import Sequence

import numpy as np


def mean(values: Sequence[float]) -> float:
    return float(np.mean(values)) if len(values) else float("nan")


def share(flags: Sequence[bool]) -> float:
    return float(np.mean(flags)) if len(flags) else float("nan")


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def rankdata(values: Sequence[float]) -> np.ndarray:
    """Средние ранги при равенстве (как scipy.stats.rankdata)."""
    array = np.asarray(values, dtype=float)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array))
    sorted_values = array[order]
    start = 0
    while start < len(array):
        end = start
        while end + 1 < len(array) and sorted_values[end + 1] == sorted_values[start]:
            end += 1
        ranks[order[start : end + 1]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson(rankdata(x), rankdata(y))


def confusion(truth: Sequence[str], predicted: Sequence[str], labels: Sequence[str]) -> np.ndarray:
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(truth, predicted, strict=True):
        matrix[index[t], index[p]] += 1
    return matrix


def cohen_kappa(
    a: Sequence[str], b: Sequence[str], labels: Sequence[str], weights: str | None = None
) -> float:
    """κ Коэна; weights="quadratic" — взвешенная κ для порядковой шкалы грейдов."""
    matrix = confusion(a, b, labels).astype(float)
    total = matrix.sum()
    if total == 0:
        return float("nan")
    k = len(labels)
    i, j = np.meshgrid(range(k), range(k), indexing="ij")
    w = ((i - j) / max(k - 1, 1)) ** 2 if weights == "quadratic" else (i != j).astype(float)
    expected = np.outer(matrix.sum(axis=1), matrix.sum(axis=0)) / total
    denominator = (w * expected).sum()
    return float(1.0 - (w * matrix).sum() / denominator) if denominator else float("nan")


def precision_at_k(relevances: Sequence[int], k: int, relevant_from: int) -> float:
    top = list(relevances[:k])
    return sum(1 for r in top if r >= relevant_from) / k


def ndcg_at_k(relevances: Sequence[int], all_relevances: Sequence[int], k: int) -> float:
    """nDCG@k с выигрышем 2^rel − 1; идеал — лучшие k из всего пула."""

    def dcg(values: Sequence[int]) -> float:
        return sum((2**rel - 1) / math.log2(position + 2) for position, rel in enumerate(values[:k]))

    ideal = dcg(sorted(all_relevances, reverse=True))
    return dcg(list(relevances)) / ideal if ideal else float("nan")


def bins(start: float, stop: float, step: float) -> list[tuple[float, float]]:
    edges = np.arange(start, stop + 1e-9, step)
    return [(float(lo), float(hi)) for lo, hi in zip(edges[:-1], edges[1:], strict=True)]
