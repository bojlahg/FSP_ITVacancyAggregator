"""Сигналы честности попытки (§10.9): golden-кейсы формул и инвариант «на грейд не влияет»."""

import random

import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.testing.engine import integrity
from app.modules.testing.engine.integrity import (
    FAST_CORRECT_HARD,
    PERSON_FIT,
    RAPID_GUESSING,
    FastCorrectRule,
    RapidRule,
    TimedResponse,
    evaluate,
    fast_correct_hard,
    get_rules,
    lz_star,
    rapid_share,
    time_threshold,
)
from app.modules.testing.engine.irt import ItemResponse, eap, probability
from app.modules.testing.models import TestAttempt as Attempt

API = "/api/v1"


def item(a: float, b: float, c: float, score: float, time_sec: float | None = 60.0, limit: float = 120.0):
    return TimedResponse(a, b, c, score, time_sec, limit)


# ---------- lz* ----------


def test_lz_star_golden_two_items_at_zero():
    """θ̂ = 0: r₀ = 0, c_n = 0 → lz* = lz = W/√Var: (1, 0) → 0,5379/√0,3932; (0, 1) → −1,4622/√0,3932."""
    responses = [item(1.0, -1.0, 0.0, 1.0), item(1.0, 1.0, 0.0, 0.0)]
    assert lz_star(responses, 0.0) == pytest.approx(0.857764, abs=1e-5)
    flipped = [item(1.0, -1.0, 0.0, 0.0), item(1.0, 1.0, 0.0, 1.0)]
    assert lz_star(flipped, 0.0) == pytest.approx(-2.331644, abs=1e-5)


def test_lz_star_golden_3pl_with_prior_correction():
    """Независимый расчёт по формулам Snijders (2001) на чистом math (scratch-скрипт, см. §10.9)."""
    params = [(1.2, -0.5, 0.25), (0.8, 0.3, 0.0), (1.5, 1.0, 0.25), (1.0, -1.2, 0.0)]
    aberrant = [item(a, b, c, s) for (a, b, c), s in zip(params, [1, 0, 1, 0], strict=True)]
    regular = [item(a, b, c, s) for (a, b, c), s in zip(params, [1, 1, 0, 1], strict=True)]
    assert lz_star(aberrant, 0.4) == pytest.approx(-2.281146, abs=1e-5)
    assert lz_star(aberrant, 0.4, prior_sd=None) == pytest.approx(-1.866666, abs=1e-5)
    assert lz_star(regular, 0.4) == pytest.approx(0.615819, abs=1e-5)


def test_lz_star_undefined_without_information():
    assert lz_star([], 0.0) is None
    # P = 0,5 у единственного задания: w = 0, дисперсия после поправки нулевая
    assert lz_star([item(1.0, 0.0, 0.0, 1.0)], 0.0) is None


def test_lz_star_is_standard_normal_for_honest_responses():
    """При H0 (ответы по 3PL, θ̂ — EAP движка) lz* ≈ N(0, 1): ошибка I рода у −1,645 около 5%."""
    rng = random.Random(7)
    values = []
    for _ in range(1500):
        theta = rng.gauss(0, 1)
        params = [
            (rng.uniform(0.8, 1.8), theta + rng.gauss(0, 0.7), rng.choice([0.0, 0.25])) for _ in range(20)
        ]
        scores = [1.0 if rng.random() < probability(theta, a, b, c) else 0.0 for a, b, c in params]
        estimate, _ = eap([ItemResponse(a, b, c, s) for (a, b, c), s in zip(params, scores, strict=True)])
        responses = [item(a, b, c, s) for (a, b, c), s in zip(params, scores, strict=True)]
        values.append(lz_star(responses, estimate))
    array = np.array([v for v in values if v is not None])
    assert abs(array.mean()) < 0.2
    assert 0.85 < array.std() < 1.15
    assert 0.02 < (array < -1.645).mean() < 0.09


# ---------- время ----------


def test_time_threshold_is_nt10_capped():
    assert time_threshold(60, 0.10, 10) == pytest.approx(6.0)
    assert time_threshold(600, 0.10, 10) == 10


def test_rapid_share_counts_answers_below_threshold():
    rule = RapidRule(limit_fraction=0.10, max_sec=10, share_threshold=0.10)
    responses = [
        item(1, 0, 0, 1, 5.0),
        item(1, 0, 0, 1, 11.0),
        item(1, 0, 0, 0, 2.0, 60),
        item(1, 0, 0, 1, None),
    ]
    # 5 с < 10 с; 11 с ≥ 10 с; 2 с < 6 с; без времени не учитывается
    assert rapid_share(responses, rule) == pytest.approx(2 / 3)
    assert rapid_share([item(1, 0, 0, 1, None)], rule) is None


def test_fast_correct_hard_needs_fast_correct_and_hard():
    rule = FastCorrectRule(limit_fraction=0.20, max_sec=30, b_margin=1.0, count_threshold=2)
    theta = 0.0
    responses = [
        item(1, 1.5, 0, 1.0, 10.0),  # засчитывается: трудное, верно, 10 с < 24 с
        item(1, 1.0, 0, 1.0, 23.9),  # засчитывается: b − θ̂ = 1,0 ровно
        item(1, 0.5, 0, 1.0, 5.0),  # не трудное
        item(1, 2.0, 0, 0.0, 5.0),  # неверно
        item(1, 2.0, 0, 1.0, 40.0),  # не быстро
        item(1, 2.0, 0, 1.0, None),  # время неизвестно
    ]
    assert fast_correct_hard(responses, theta, rule) == 2


# ---------- итог ----------


def honest_form(theta: float = 0.0) -> list[TimedResponse]:
    """Гуттмановский рисунок: лёгкие верно, трудные неверно, время обычное."""
    bs = np.linspace(-2, 2, 16)
    return [item(1.2, float(b), 0.0, 1.0 if b < theta else 0.0, 50.0) for b in bs]


def test_evaluate_honest_pattern_is_not_flagged():
    result = evaluate(honest_form(), 0.0, get_rules())
    assert result.enough_data and not result.flagged and result.reasons == ()
    assert result.lz_star > 0 and result.rapid_share == 0 and result.fast_correct_hard == 0


def test_evaluate_flags_each_signal():
    rules = get_rules()
    inverted = [item(r.a, r.b, r.c, 1.0 - r.score, r.time_sec) for r in honest_form()]
    assert PERSON_FIT in evaluate(inverted, 0.0, rules).reasons

    rapid = [item(r.a, r.b, r.c, r.score, 3.0) for r in honest_form()]
    assert evaluate(rapid, 0.0, rules).reasons == (RAPID_GUESSING,)

    form = honest_form()
    leaked = [item(1.2, 1.8, 0.0, 1.0, 15.0), item(1.2, 1.9, 0.0, 1.0, 15.0)]
    result = evaluate(form[:-2] + leaked, 0.0, rules)
    assert FAST_CORRECT_HARD in result.reasons and result.fast_correct_hard == 2
    assert result.flagged


def test_evaluate_requires_min_items():
    rules = get_rules()
    result = evaluate(honest_form()[: rules.min_items - 1], 0.0, rules)
    assert not result.enough_data and not result.flagged and result.lz_star is None
    assert result.as_dict()["reasons"] == []


def test_rules_texts_cover_every_reason():
    assert set(get_rules().texts.reasons) == set(integrity.REASONS)


# ---------- API: работодатель видит пометку, грейд не меняется, выключатель ----------


@pytest.fixture
def small_min_items(monkeypatch):
    rules = get_rules().model_copy(update={"min_items": 2})
    monkeypatch.setattr(integrity, "get_rules", lambda: rules)


async def finish_fast_attempt(client, session, email: str) -> tuple[dict, int]:
    """Кандидат отвечает мгновенно: каждое задание быстрее порога NT10 → сигнал rapid_guessing."""
    from tests.test_testing_flow import answer_all, onboard, signup

    headers = await signup(client, email)
    await onboard(client, headers)
    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "middle"}, headers=headers
    )
    attempt_id = started.json()["id"]
    await answer_all(client, session, headers, attempt_id, correct=True)
    result = (await client.get(f"{API}/tests/attempts/{attempt_id}/result", headers=headers)).json()
    return result, attempt_id


@pytest.fixture
def synthetic(monkeypatch):
    from app.modules.testing import service as testing_service
    from tests.test_engine import synthetic_bank

    bank = synthetic_bank()
    monkeypatch.setattr(testing_service, "get_bank", lambda: bank)
    monkeypatch.setattr(get_settings(), "test_mode", "short")


async def test_signals_shown_to_employer_and_do_not_affect_grade(client, session, synthetic, small_min_items):
    from tests.test_needs import candidate_id
    from tests.test_needs import signup as signup_employer

    result, attempt_id = await finish_fast_attempt(client, session, "fast@example.com")
    # Грейд определяет только тест: при сигнале результат тот же, что у честного прохождения
    assert result["result"] == "confident_pass"
    assert result["category"]["label"].endswith("Middle")
    assert "integrity" not in result and "flags" not in result

    attempt = await session.scalar(select(Attempt).where(Attempt.id == attempt_id))
    await session.refresh(attempt)
    stored = attempt.flags["integrity"]
    assert stored["flagged"] and RAPID_GUESSING in stored["reasons"] and stored["rapid_share"] == 1.0

    employer = await signup_employer(client, "hr@fast.ru")
    cid = await candidate_id(session, "fast@example.com")
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    signals = card["integrity"]
    assert signals["flagged"] and signals["enough_data"]
    assert RAPID_GUESSING in [reason["code"] for reason in signals["reasons"]]
    assert all(reason["text"] for reason in signals["reasons"])
    assert "на грейд не влияет" in signals["note"]

    # Выключатель скрывает уже сохранённые сигналы
    get_settings().integrity_signals_enabled = False
    try:
        card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    finally:
        get_settings().integrity_signals_enabled = True
    assert card["integrity"] is None


async def test_disabled_signals_are_not_computed(client, session, synthetic, small_min_items, monkeypatch):
    from tests.test_needs import candidate_id
    from tests.test_needs import signup as signup_employer

    monkeypatch.setattr(get_settings(), "integrity_signals_enabled", False)
    result, attempt_id = await finish_fast_attempt(client, session, "off@example.com")
    assert result["result"] == "confident_pass"
    attempt = await session.scalar(select(Attempt).where(Attempt.id == attempt_id))
    await session.refresh(attempt)
    assert "integrity" not in attempt.flags

    employer = await signup_employer(client, "hr@off.ru")
    cid = await candidate_id(session, "off@example.com")
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    assert card["integrity"] is None
