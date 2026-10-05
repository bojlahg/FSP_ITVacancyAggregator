"""Уверенность в грейде (§10.4.1): вероятности грейдов по θ̂ и SE и индексы Руднера.

Только объяснение: грейд по-прежнему выставляет правило §10.4 (θ̂ против порога), эти числа его не меняют.
Чистые функции без БД и FastAPI: их используют backend и validation/.
"""

import math
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.modules.testing.engine.bank import CONTENT_DIR

BELOW = "none"  # полоса ниже самого нижнего порога: категория не присваивается


class ConfidenceLevel(BaseModel):
    code: str
    min: float = Field(ge=0, le=1, description="Нижняя граница P(θ ≥ cut) для этого уровня")
    label: str


class ConfidenceTexts(BaseModel):
    statement: str
    candidate: str
    note: str
    below: str


class ConfidenceRules(BaseModel):
    levels: list[ConfidenceLevel] = Field(min_length=1)
    display_min: float = Field(gt=0, lt=0.5)
    display_max: float = Field(gt=0.5, lt=1)
    texts: ConfidenceTexts
    how_it_works_path: str
    validation_url: str


def load_rules(path: Path | None = None) -> ConfidenceRules:
    with (path or CONTENT_DIR / "confidence.yaml").open(encoding="utf-8") as file:
        return ConfidenceRules.model_validate(yaml.safe_load(file))


@lru_cache
def get_rules() -> ConfidenceRules:
    return load_rules()


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _below(theta: float, se: float, cut: float) -> float:
    """P(θ < cut) при θ ~ N(θ̂, SE²); при SE = 0 — точечная оценка."""
    if se <= 1e-12:
        return 0.0 if theta >= cut else 1.0
    return normal_cdf((cut - theta) / se)


def probability_at_least(theta: float, se: float, cut: float) -> float:
    """P(θ ≥ cut_G): насколько вероятно, что истинный уровень не ниже грейда G."""
    return 1.0 - _below(theta, se, cut)


def _ordered(cuts: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(cuts.items(), key=lambda item: item[1])


def band_probabilities(theta: float, se: float, cuts: Mapping[str, float]) -> dict[str, float]:
    """Вероятность каждой полосы грейда по Руднеру (2001, 2005), см. docs/implementation.md §10.4.1.

    P(грейд = k) = Φ((cut_{k+1} − θ̂)/SE) − Φ((cut_k − θ̂)/SE); BELOW — ниже нижнего порога,
    у старшего грейда верхней границы нет. Сумма по полосам равна 1.
    """
    ordered = _ordered(cuts)
    lower = [_below(theta, se, cut) for _, cut in ordered]
    probabilities = {BELOW: lower[0]}
    for index, (grade, _) in enumerate(ordered):
        upper = lower[index + 1] if index + 1 < len(ordered) else 1.0
        probabilities[grade] = max(upper - lower[index], 0.0)
    return probabilities


def band_of(theta: float, cuts: Mapping[str, float]) -> str:
    """Полоса точечной оценки: старший грейд, чей порог не выше θ (как правило §10.4 для одного теста)."""
    band = BELOW
    for grade, cut in _ordered(cuts):
        if theta >= cut:
            band = grade
    return band


def rudner_indices(theta: float, se: float, cuts: Mapping[str, float]) -> tuple[float, float]:
    """Ожидаемые точность и согласованность классификации одного кандидата (Rudner 2001/2005; Lee 2010).

    Точность — P(истинная полоса = полоса θ̂); согласованность — Σ_k P_k², вероятность, что независимое
    повторное измерение с той же SE даст ту же полосу. Средние по популяции — индексы теста.
    """
    probabilities = band_probabilities(theta, se, cuts)
    return probabilities[band_of(theta, cuts)], sum(p * p for p in probabilities.values())


def level_for(probability: float, rules: ConfidenceRules) -> ConfidenceLevel:
    """Словесный уровень по P(θ ≥ cut): первый уровень, чей min не выше вероятности."""
    for level in sorted(rules.levels, key=lambda item: item.min, reverse=True):
        if probability >= level.min:
            return level
    return min(rules.levels, key=lambda item: item.min)


def display_percent(probability: float, rules: ConfidenceRules) -> int:
    """Проценты для текста без «0%» и «100%»: при конечной SE полной уверенности не бывает."""
    clamped = min(max(probability, rules.display_min), rules.display_max)
    return round(clamped * 100)
