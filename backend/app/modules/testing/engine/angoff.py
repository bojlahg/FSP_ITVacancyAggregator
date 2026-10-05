"""Modified Angoff через IRT (§10.4): оценки экспертов → порог грейда на шкале θ.

Эксперт оценивает p_i — вероятность, что минимально компетентный кандидат грейда решит шаблон i.
Порог — θ, при котором тестовая характеристическая кривая Σ P_i(θ) равна Σ p_i.
"""

from collections.abc import Callable, Sequence
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


def share_to_theta(items: Sequence[AngoffItem], share: float) -> float:
    """Доля верных по набору → θ: та же TCC, что у порога Angoff (все p_i = share)."""
    return angoff_cut(items, [share] * len(items)).theta


def theta_to_share(items: Sequence[AngoffItem], theta: float) -> float:
    """θ → ожидаемая доля верных по набору: TCC(θ) / n."""
    return tcc(theta, items) / len(items)


def fail_rate(thetas: Sequence[float], cut: float) -> float:
    """Доля кандидатов ниже порога θ: «не дотягивают» до грейда."""
    return sum(theta < cut for theta in thetas) / len(thetas) if thetas else float("nan")


@dataclass(frozen=True)
class HofsteeBox:
    """Ответы эксперта по Hofstee: допустимые пороги (доля верных) и доли не дотягивающих, всё в [0, 1]."""

    min_cut: float
    max_cut: float
    min_fail: float
    max_fail: float


@dataclass(frozen=True)
class HofsteeResult:
    cut: float  # доля верных; при пересечении — точка пересечения, без него — ближний край окна
    fail: float  # доля не дотягивающих при этом пороге по фактической кривой
    intersects: bool  # кривая пересекает диагональ окна внутри окна


def hofstee(box: HofsteeBox, fail_curve: Callable[[float], float], tolerance: float = 1e-6) -> HofsteeResult:
    """Компромисс Hofstee (1983), docs/implementation.md §12.4.

    Диагональ окна идёт из (min_cut, max_fail) в (max_cut, min_fail); fail_curve(k) — фактическая доля
    не дотягивающих при пороге k, не убывает по k. Порог — пересечение кривой с диагональю: разность
    кривая − диагональ не убывает, поэтому корень единственный — ищем бисекцией. Если кривая выше
    диагонали уже в min_cut (или ниже ещё в max_cut), пересечения в окне нет — берём ближний край.
    """
    if not (0.0 <= box.min_cut <= box.max_cut <= 1.0 and 0.0 <= box.min_fail <= box.max_fail <= 1.0):
        raise ValueError("границы окна Hofstee — доли в [0, 1], min ≤ max")
    width = box.max_cut - box.min_cut

    def diagonal(k: float) -> float:
        if width == 0:
            return box.max_fail
        return box.max_fail - (box.max_fail - box.min_fail) * (k - box.min_cut) / width

    if width == 0:
        fail = fail_curve(box.min_cut)
        return HofsteeResult(box.min_cut, fail, box.min_fail <= fail <= box.max_fail)
    if fail_curve(box.min_cut) > diagonal(box.min_cut):
        return HofsteeResult(box.min_cut, fail_curve(box.min_cut), False)
    if fail_curve(box.max_cut) < diagonal(box.max_cut):
        return HofsteeResult(box.max_cut, fail_curve(box.max_cut), False)
    low, high = box.min_cut, box.max_cut
    while high - low > tolerance:
        middle = (low + high) / 2
        if fail_curve(middle) < diagonal(middle):
            low = middle
        else:
            high = middle
    cut = (low + high) / 2
    # У ступенчатой эмпирической кривой пересечение может прийтись на скачок — берём точку на диагонали
    return HofsteeResult(cut, diagonal(cut), True)


def in_hofstee_box(box: HofsteeBox, cut: float, fail: float) -> bool:
    """Порог Angoff (доля верных и доля не дотягивающих при нём) внутри окна экспертов."""
    return box.min_cut <= cut <= box.max_cut and box.min_fail <= fail <= box.max_fail
