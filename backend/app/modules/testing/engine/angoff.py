"""Modified Angoff через IRT (§10.4): оценки экспертов → порог грейда на шкале θ.

Эксперт оценивает p_i — вероятность, что минимально компетентный кандидат грейда решит шаблон i.
Порог — θ, при котором тестовая характеристическая кривая Σ P_i(θ) равна Σ p_i.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.testing.engine.irt import GRID, probability

THETA_MIN = float(GRID[0])
THETA_MAX = float(GRID[-1])


@dataclass(frozen=True)
class AngoffItem:
    a: float
    b: float
    c: float


@dataclass(frozen=True)
class AngoffCut:
    theta: float
    expected: float = 0.0  # Σ p_i — ожидаемый балл минимально компетентного кандидата
    clamped: bool = False  # Σ p_i вне значений TCC на [THETA_MIN, THETA_MAX] — порог прижат к краю шкалы


def tcc(theta: float, items: Sequence[AngoffItem]) -> float:
    """Тестовая характеристическая кривая: ожидаемое число верных ответов при способности θ."""
    return float(sum(probability(theta, item.a, item.b, item.c) for item in items))


def angoff_cut(
    items: Sequence[AngoffItem],
    ratings: Sequence[float],
    theta_min: float = THETA_MIN,
    theta_max: float = THETA_MAX,
    tolerance: float = 1e-6,
) -> AngoffCut:
    """Порог θ: TCC(θ) = Σ p_i. TCC строго растёт по θ, поэтому решение единственно — ищем бисекцией.

    Σ p_i ≤ TCC(theta_min) (в т. ч. ниже Σ c — уровня угадывания) → theta_min;
    Σ p_i ≥ TCC(theta_max) (в т. ч. Σ p_i = n) → theta_max. Оба случая помечаются clamped.
    """
    if not items or len(items) != len(ratings):
        raise ValueError("нужны параметры и оценка для каждого шаблона")
    if any(not 0.0 <= p <= 1.0 for p in ratings):
        raise ValueError("оценки — вероятности в [0, 1]")
    target = float(sum(ratings))
    if target <= tcc(theta_min, items):
        return AngoffCut(theta_min, target, clamped=True)
    if target >= tcc(theta_max, items):
        return AngoffCut(theta_max, target, clamped=True)
    low, high = theta_min, theta_max
    while high - low > tolerance:
        middle = (low + high) / 2
        if tcc(middle, items) < target:
            low = middle
        else:
            high = middle
    return AngoffCut((low + high) / 2, target)
