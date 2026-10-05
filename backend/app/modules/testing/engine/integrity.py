"""Сигналы честности попытки (§10.9): person-fit lz*, быстрое угадывание, «быстро и верно на трудном».

Только пометка для человека. В θ̂, грейд, категорию и score подбора не входит (инвариант, 152-ФЗ ст. 16).
Чистые функции без БД и FastAPI: их используют backend и validation/.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, Field

from app.modules.testing.engine.bank import CONTENT_DIR
from app.modules.testing.engine.irt import probability

PERSON_FIT = "person_fit"
RAPID_GUESSING = "rapid_guessing"
FAST_CORRECT_HARD = "fast_correct_hard"
REASONS = (PERSON_FIT, RAPID_GUESSING, FAST_CORRECT_HARD)


class PersonFitRule(BaseModel):
    threshold: float


class RapidRule(BaseModel):
    limit_fraction: float = Field(gt=0, lt=1)
    max_sec: float = Field(gt=0)
    share_threshold: float = Field(ge=0, le=1)


class FastCorrectRule(BaseModel):
    limit_fraction: float = Field(gt=0, lt=1)
    max_sec: float = Field(gt=0)
    b_margin: float
    count_threshold: int = Field(ge=1)


class IntegrityTexts(BaseModel):
    note: str
    clean: str
    insufficient: str
    reasons: dict[str, str]


class IntegrityRules(BaseModel):
    min_items: int = Field(ge=2)
    person_fit: PersonFitRule
    rapid: RapidRule
    fast_correct: FastCorrectRule
    texts: IntegrityTexts


def load_rules(path: Path | None = None) -> IntegrityRules:
    with (path or CONTENT_DIR / "integrity.yaml").open(encoding="utf-8") as file:
        return IntegrityRules.model_validate(yaml.safe_load(file))


@lru_cache
def get_rules() -> IntegrityRules:
    return load_rules()


@dataclass(frozen=True)
class TimedResponse:
    """Оценённый ответ: параметры 3PL, балл 0/1 и серверное время ответа (None — неизвестно)."""

    a: float
    b: float
    c: float
    score: float
    time_sec: float | None
    time_limit_sec: float


@dataclass(frozen=True)
class IntegrityResult:
    items: int
    enough_data: bool
    lz_star: float | None = None
    rapid_share: float | None = None
    fast_correct_hard: int | None = None
    flagged: bool = False
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


def lz_star(responses: Sequence[TimedResponse], theta: float, prior_sd: float | None = 1.0) -> float | None:
    """lz* Снейдерса (2001) для 3PL при оценённой θ̂.

    W = Σ(u−P)·w, w = ln(P/Q); поправка c_n·r₀(θ̂) и дисперсия по w̃ = w − c_n·r, r = P'/(PQ),
    c_n = ΣP'w / ΣP'r. r₀ = −θ̂/σ² для априорного N(0, σ²) (EAP ≈ байесовская мода), None — ML (r₀ = 0).
    См. docs/implementation.md §10.9. None — статистика не определена (нулевая дисперсия).
    """
    if not responses:
        return None
    a = np.array([r.a for r in responses])
    b = np.array([r.b for r in responses])
    c = np.array([r.c for r in responses])
    u = np.array([r.score for r in responses])
    p = np.clip(probability(theta, a, b, c), 1e-9, 1 - 1e-9)
    q = 1.0 - p
    dp = a * (p - c) * q / (1.0 - c)
    w = np.log(p / q)
    r = dp / (p * q)
    denominator = float(np.sum(dp * r))
    if denominator <= 0:
        return None
    c_n = float(np.sum(dp * w)) / denominator
    r0 = 0.0 if prior_sd is None else -theta / prior_sd**2
    w_tilde = w - c_n * r
    variance = float(np.sum(w_tilde**2 * p * q))
    if variance <= 1e-12:
        return None
    return (float(np.sum((u - p) * w)) + c_n * r0) / variance**0.5


def time_threshold(time_limit_sec: float, fraction: float, max_sec: float) -> float:
    """Порог «быстрого» ответа: доля лимита задания, но не больше max_sec (NT10 — 10%, ≤ 10 с)."""
    return min(fraction * time_limit_sec, max_sec)


def rapid_share(responses: Sequence[TimedResponse], rule: RapidRule) -> float | None:
    timed = [r for r in responses if r.time_sec is not None]
    if not timed:
        return None
    rapid = sum(
        r.time_sec < time_threshold(r.time_limit_sec, rule.limit_fraction, rule.max_sec) for r in timed
    )
    return rapid / len(timed)


def fast_correct_hard(responses: Sequence[TimedResponse], theta: float, rule: FastCorrectRule) -> int:
    return sum(
        r.score >= 1.0
        and r.time_sec is not None
        and r.b - theta >= rule.b_margin
        and r.time_sec < time_threshold(r.time_limit_sec, rule.limit_fraction, rule.max_sec)
        for r in responses
    )


def evaluate(responses: Sequence[TimedResponse], theta: float, rules: IntegrityRules) -> IntegrityResult:
    """Все сигналы попытки по оценённым ответам и итоговой θ̂ (EAP с N(0, 1), как в irt.eap)."""
    if len(responses) < rules.min_items:
        return IntegrityResult(items=len(responses), enough_data=False)
    fit = lz_star(responses, theta)
    share = rapid_share(responses, rules.rapid)
    fast = fast_correct_hard(responses, theta, rules.fast_correct)
    reasons = []
    if fit is not None and fit < rules.person_fit.threshold:
        reasons.append(PERSON_FIT)
    if share is not None and share > rules.rapid.share_threshold:
        reasons.append(RAPID_GUESSING)
    if fast >= rules.fast_correct.count_threshold:
        reasons.append(FAST_CORRECT_HARD)
    return IntegrityResult(
        items=len(responses),
        enough_data=True,
        lz_star=round(fit, 4) if fit is not None else None,
        rapid_share=round(share, 4) if share is not None else None,
        fast_correct_hard=fast,
        flagged=bool(reasons),
        reasons=tuple(reasons),
    )
