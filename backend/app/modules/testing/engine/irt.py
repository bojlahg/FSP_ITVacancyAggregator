"""IRT: 3PL-вероятность, EAP-оценка способности и информация задания (§10.4)."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

GRID = np.linspace(-4.0, 4.0, 81)
PRIOR = np.exp(-0.5 * GRID**2)  # N(0, 1) без нормировки — нормируется в posterior


@dataclass(frozen=True)
class ItemResponse:
    a: float
    b: float
    c: float
    score: float


def probability(theta: np.ndarray | float, a: float, b: float, c: float = 0.0) -> np.ndarray:
    return c + (1.0 - c) / (1.0 + np.exp(-a * (np.asarray(theta) - b)))


def information(theta: np.ndarray | float, a: float, b: float, c: float = 0.0) -> np.ndarray:
    """Информация Фишера 3PL: чем выше у порога грейда, тем точнее решение о грейде."""
    p = probability(theta, a, b, c)
    return (a**2) * ((p - c) ** 2 / (1.0 - c) ** 2) * ((1.0 - p) / p)


def eap(responses: Sequence[ItemResponse]) -> tuple[float, float]:
    """EAP с априорным N(0,1) на квадратурной сетке; SE — апостериорное стандартное отклонение."""
    log_posterior = np.log(PRIOR)
    for item in responses:
        p = np.clip(probability(GRID, item.a, item.b, item.c), 1e-9, 1 - 1e-9)
        log_posterior += item.score * np.log(p) + (1.0 - item.score) * np.log(1.0 - p)
    weights = np.exp(log_posterior - log_posterior.max())
    weights /= weights.sum()
    theta = float(np.sum(GRID * weights))
    se = float(np.sqrt(np.sum((GRID - theta) ** 2 * weights)))
    return theta, se
