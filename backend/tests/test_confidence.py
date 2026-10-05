"""Уверенность в грейде (§10.4.1): golden-кейсы Руднера, уровни из YAML и инвариант «на грейд не влияет»."""

import math

import pytest

from app.modules.testing.engine import confidence
from app.modules.testing.engine.bank import get_blueprints
from app.modules.testing.engine.confidence import (
    BELOW,
    band_of,
    band_probabilities,
    display_percent,
    get_rules,
    level_for,
    normal_cdf,
    probability_at_least,
    rudner_indices,
)
from tests.test_integrity import finish_fast_attempt, synthetic  # noqa: F401 — фикстура

API = "/api/v1"
CUTS = {"intern": -1.8, "junior": -0.8, "middle": 0.2, "senior": 1.2}


def test_normal_cdf_golden():
    assert normal_cdf(0.0) == 0.5
    assert normal_cdf(1.0) == pytest.approx(0.8413447, abs=1e-7)
    assert normal_cdf(-1.959964) == pytest.approx(0.025, abs=1e-6)


def test_band_probabilities_golden():
    """θ̂ = 0,5, SE = 0,3: P(Middle) = Φ((1,2 − 0,5)/0,3) − Φ((0,2 − 0,5)/0,3) = Φ(2,333) − Φ(−1)."""
    bands = band_probabilities(0.5, 0.3, CUTS)
    assert list(bands) == [BELOW, "intern", "junior", "middle", "senior"]
    assert bands["middle"] == pytest.approx(0.9901847 - 0.1586553, abs=1e-6)
    assert bands["senior"] == pytest.approx(1 - 0.9901847, abs=1e-6)
    assert bands["junior"] == pytest.approx(0.1586553 - 0.0000073, abs=1e-6)
    assert bands[BELOW] == pytest.approx(0.0, abs=1e-12)
    assert sum(bands.values()) == pytest.approx(1.0, abs=1e-12)


def test_bands_do_not_depend_on_cut_order_in_yaml():
    shuffled = {"senior": 1.2, "intern": -1.8, "middle": 0.2, "junior": -0.8}
    assert band_probabilities(-0.1, 0.4, shuffled) == band_probabilities(-0.1, 0.4, CUTS)


def test_probability_at_least_golden():
    assert probability_at_least(0.5, 0.3, 0.2) == pytest.approx(0.8413447, abs=1e-7)
    assert probability_at_least(0.2, 0.4, 0.2) == 0.5  # θ̂ ровно на пороге — монетка
    # Без погрешности — точечное правило §10.4
    assert probability_at_least(0.2, 0.0, 0.2) == 1.0
    assert probability_at_least(0.19, 0.0, 0.2) == 0.0


def test_band_of_matches_grade_rule():
    assert band_of(-2.0, CUTS) == BELOW
    assert band_of(-1.8, CUTS) == "intern"
    assert band_of(0.2, CUTS) == "middle"
    assert band_of(3.0, CUTS) == "senior"


def test_rudner_indices_golden():
    """Точность = P полосы θ̂; согласованность = Σ P_k² (Rudner 2005; Lee 2010)."""
    accuracy, consistency = rudner_indices(0.5, 0.3, CUTS)
    bands = band_probabilities(0.5, 0.3, CUTS)
    assert accuracy == pytest.approx(0.8315294, abs=1e-6)
    assert consistency == pytest.approx(sum(p * p for p in bands.values()), abs=1e-12)
    assert consistency == pytest.approx(0.7167067, abs=1e-6)
    # Один порог, θ̂ на пороге: точность и согласованность 0,5
    assert rudner_indices(0.2, 0.4, {"middle": 0.2}) == (0.5, 0.5)
    # Далеко от порогов — почти 1
    far = rudner_indices(3.5, 0.3, CUTS)
    assert far[0] > 0.999 and far[1] > 0.999


def test_levels_from_yaml():
    rules = get_rules()
    assert level_for(0.95, rules).code == "high"
    assert level_for(0.90, rules).code == "high"
    assert level_for(0.80, rules).code == "medium"
    assert level_for(0.50, rules).code == "low"
    assert display_percent(1.0, rules) == 99
    assert display_percent(0.0, rules) == 1
    assert display_percent(0.8413, rules) == 84


def test_confidence_levels_cover_zero():
    """Любая вероятность получает уровень: нижний уровень начинается с нуля."""
    assert min(level.min for level in get_rules().levels) == 0.0


def test_same_cuts_as_grade_rule():
    """P(θ ≥ cut_G) ≥ 0,5 ровно тогда, когда правило §10.4 даёт «пройден»: пороги одни и те же."""
    cuts = get_blueprints().scale.cuts
    for grade, cut in cuts.items():
        for theta in (cut - 0.01, cut, cut + 0.01):
            assert (probability_at_least(theta, 0.35, cut) >= 0.5) == (theta >= cut), grade


# ---------- API: кандидат, работодатель, обезличенная карточка ----------


async def test_confidence_in_api_does_not_change_grade(client, session, synthetic, monkeypatch):  # noqa: F811
    from tests.test_needs import candidate_id
    from tests.test_needs import signup as signup_employer

    result, _ = await finish_fast_attempt(client, session, "conf@example.com")
    assert result["result"] == "confident_pass"
    conf = result["confidence"]
    assert conf["grade"] == "middle"
    cut = get_blueprints().cut("middle")
    assert conf["at_least"] == pytest.approx(
        confidence.probability_at_least(result["theta"], result["se"], cut), abs=1e-4
    )
    assert conf["text"].startswith("Уверенность: ") and conf["text"].endswith("не ниже Middle")
    assert [band["grade"] for band in conf["bands"]] == [None, "intern", "junior", "middle", "senior"]
    assert math.isclose(sum(band["probability"] for band in conf["bands"]), 1.0, abs_tol=1e-3)
    assert "На грейд не влияет" in conf["note"]

    status = (await client.get(f"{API}/candidates/me/grade-status", headers=await _login(client))).json()
    evidence = status["current"]["evidence"]
    assert evidence["adaptive"] and evidence["short_mode"]
    assert evidence["items_scored"] > 0 and evidence["tested_at"]
    assert evidence["confidence"]["at_least"] == conf["at_least"]
    assert evidence["how_it_works_path"] == "/how-it-works"
    assert evidence["validation_url"].endswith("docs/validation/report.md")
    assert all(entry["evidence"] is None for entry in status["history"])

    employer = await signup_employer(client, "hr@conf.ru")
    cid = await candidate_id(session, "conf@example.com")
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    shown = card["grade_evidence"]
    assert shown["confidence"]["at_least"] == conf["at_least"]
    assert shown["confidence"]["text"].endswith("уровень не ниже Middle")
    assert not shown["confidence"]["text"].startswith("Уверенность")
    assert card["brief"]["category"]["grade"] == "middle"

    # Любые числа уверенности не меняют грейд: категория та же при «пессимистичных» уровнях
    rules = get_rules().model_copy(update={"levels": [get_rules().levels[-1]]})
    monkeypatch.setattr(confidence, "get_rules", lambda: rules)
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    assert card["grade_evidence"]["confidence"]["level"] == "low"
    assert card["brief"]["category"]["grade"] == "middle"


async def test_blind_card_has_no_evidence(client, session, synthetic):  # noqa: F811
    from app.modules.matching import service as matching_service
    from tests.test_needs import candidate_id
    from tests.test_needs import signup as signup_employer

    await finish_fast_attempt(client, session, "blind@example.com")
    await signup_employer(client, "hr@blind.ru")
    cid = await candidate_id(session, "blind@example.com")
    employer_id = await _employer_id(session, "hr@blind.ru")
    card = await matching_service.blind_card(session, employer_id, cid)
    assert card.grade_evidence is None


async def _login(client) -> dict[str, str]:
    response = await client.post(
        f"{API}/auth/login", json={"email": "conf@example.com", "password": "password-123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _employer_id(session, email: str) -> int:
    from sqlalchemy import select

    from app.modules.auth.models import User
    from app.modules.employers.models import Employer

    user = await session.scalar(select(User).where(User.email == email))
    return await session.scalar(select(Employer.id).where(Employer.user_id == user.id))
