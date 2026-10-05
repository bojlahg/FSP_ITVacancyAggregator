from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.testing import service as testing_service
from app.modules.testing.models import TestAttemptItem as AttemptItem
from tests.test_engine import synthetic_bank

API = "/api/v1"
SURVEY = {
    "daily_work": ["api"],
    "favorite_tasks": ["scale"],
    "main_language": "python",
    "stack": ["python", "fastapi", "postgresql"],
    "experience_years": 2,
    "work_formats": ["remote"],
    "relocation": "no",
    "salary": {"from": 200000, "to": 300000},
}


@pytest.fixture(autouse=True)
def short_synthetic_bank(monkeypatch):
    bank = synthetic_bank()
    monkeypatch.setattr(testing_service, "get_bank", lambda: bank)
    monkeypatch.setattr(get_settings(), "test_mode", "short")


async def signup(client, email: str) -> dict[str, str]:
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "password-123",
            "role": "candidate",
            "consent_pd_processing": True,
            "consent_profile_publication": True,
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def onboard(client, headers) -> None:
    survey = await client.post(f"{API}/survey/responses", json={"answers": SURVEY}, headers=headers)
    assert survey.status_code == 201, survey.text
    assert survey.json()["recommended"][0]["specialization"] == "backend"
    assert survey.json()["stack_modules"] == ["python"]
    confirmed = await client.post(
        f"{API}/survey/specialization", json={"specialization": "backend"}, headers=headers
    )
    assert confirmed.status_code == 200


async def answer_all(client, session, headers, attempt_id: int, correct: bool) -> None:
    while True:
        current = (await client.get(f"{API}/tests/attempts/{attempt_id}/current", headers=headers)).json()
        if current["finished"]:
            return
        assert "answer_key" not in current and "key" not in current
        item = await session.get(AttemptItem, current["item_id"])
        await session.refresh(item)
        if item.payload["kind"] == "open_approach":
            response = {"text": "Счётчики в Redis, token bucket, 429 и Retry-After"}
        elif correct:
            response = {"choice_ids": item.answer_key["choice_ids"]}
        else:
            wrong = [o["id"] for o in current["options"] if o["id"] not in item.answer_key["choice_ids"]]
            response = {"choice_ids": wrong[:1]}
        ack = await client.post(
            f"{API}/tests/attempts/{attempt_id}/answer",
            json={"item_id": current["item_id"], "response": response},
            headers=headers,
        )
        assert ack.status_code == 200, ack.text


async def test_full_path_assigns_category(client, session):
    headers = await signup(client, "flow@example.com")
    assert (await client.get(f"{API}/candidates/me", headers=headers)).json()["onboarding_step"] == "survey"
    await onboard(client, headers)
    assert (await client.get(f"{API}/candidates/me", headers=headers)).json()["onboarding_step"] == "grade"

    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "middle"}, headers=headers
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["id"]
    assert (await client.get(f"{API}/candidates/me", headers=headers)).json()["onboarding_step"] == "test"

    await answer_all(client, session, headers, attempt_id, correct=True)
    result = (await client.get(f"{API}/tests/attempts/{attempt_id}/result", headers=headers)).json()
    assert result["result"] == "confident_pass"
    assert result["category"]["label"].endswith("Middle")
    assert result["next_actions"][0]["action"] == "try_higher"
    assert result["topic_scores"]

    profile = (await client.get(f"{API}/candidates/me", headers=headers)).json()
    assert profile["onboarding_step"] == "done"
    assert profile["category"]["grade"] == "middle"
    assert any(skill["status"] == "verified" for skill in profile["skills"])

    status = (await client.get(f"{API}/candidates/me/grade-status", headers=headers)).json()
    senior = next(action for action in status["actions"] if action["grade"] == "senior")
    assert senior["allowed"] and senior["action"] == "upgrade"


async def test_failed_calibration_gives_no_category_and_offers_lower(client, session):
    headers = await signup(client, "weak@example.com")
    await onboard(client, headers)
    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "senior"}, headers=headers
    )
    attempt_id = started.json()["id"]
    await answer_all(client, session, headers, attempt_id, correct=False)

    result = (await client.get(f"{API}/tests/attempts/{attempt_id}/result", headers=headers)).json()
    assert result["result"] == "fail"
    assert result["category"] is None
    assert result["next_actions"][0] == {
        "action": "retake_lower",
        "grade": "middle",
        "available_at": None,
        "message": "Пройти тест на грейд ниже",
    }
    again = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "senior"}, headers=headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "grade_cooldown"


async def test_attempt_rules_and_isolation(client, session):
    headers = await signup(client, "owner@example.com")
    stranger = await signup(client, "stranger@example.com")
    await onboard(client, headers)

    assert (await client.get(f"{API}/survey/responses/latest", headers=stranger)).json() is None
    latest = (await client.get(f"{API}/survey/responses/latest", headers=headers)).json()
    assert latest["recommended"][0]["specialization"] == "backend"

    no_survey = await client.post(
        f"{API}/tests/attempts",
        json={"specialization": "backend", "grade_target": "junior"},
        headers=stranger,
    )
    assert no_survey.json()["error"]["code"] == "survey_required"

    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "junior"}, headers=headers
    )
    attempt_id = started.json()["id"]
    second = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "junior"}, headers=headers
    )
    assert second.status_code == 409
    assert second.json()["error"]["details"] == {"attempt_id": attempt_id}

    # Чужая попытка неотличима от несуществующей
    assert (
        await client.get(f"{API}/tests/attempts/{attempt_id}/current", headers=stranger)
    ).status_code == 404
    current = (await client.get(f"{API}/tests/attempts/{attempt_id}/current", headers=headers)).json()
    wrong_item = await client.post(
        f"{API}/tests/attempts/{attempt_id}/answer",
        json={"item_id": current["item_id"] + 999, "response": {"choice_ids": ["a"]}},
        headers=headers,
    )
    assert wrong_item.json()["error"]["code"] == "not_current_item"


async def test_late_answer_scores_zero(client, session):
    headers = await signup(client, "late@example.com")
    await onboard(client, headers)
    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "junior"}, headers=headers
    )
    attempt_id = started.json()["id"]
    current = (await client.get(f"{API}/tests/attempts/{attempt_id}/current", headers=headers)).json()

    item = await session.get(AttemptItem, current["item_id"])
    item.shown_at = item.shown_at - timedelta(seconds=item.payload["time_limit_sec"] + 60)
    await session.commit()

    ack = await client.post(
        f"{API}/tests/attempts/{attempt_id}/answer",
        json={"item_id": current["item_id"], "response": {"choice_ids": item.answer_key["choice_ids"]}},
        headers=headers,
    )
    assert ack.json()["late"] is True
    session.expire_all()
    stored = await session.scalar(select(AttemptItem).where(AttemptItem.id == current["item_id"]))
    assert stored.score == 0.0


async def test_open_answer_checklist_scored_by_code_and_shown_to_employer(client, session, monkeypatch):
    """§10.5: LLM только отмечает критерии, approach = доля отмеченных; работодатель видит ответ и отметки."""
    from app.core import llm
    from app.modules.testing.engine.model import Template
    from tests.test_needs import candidate_id
    from tests.test_needs import signup as signup_employer

    bank = synthetic_bank()
    rubric = ["Ограничение по ключу клиента", "Хранилище счётчиков", "Ответ 429", "Заголовок Retry-After"]
    bank.templates["o.approach"] = Template.model_validate(
        {
            "id": "o.approach",
            "specializations": ["backend"],
            "topic": "architecture",
            "skills": ["rest"],
            "kind": "open_approach",
            "irt": {"a": 1.0, "b": 0.2},
            "stem": "Как бы вы сделали rate limiting для публичного API?",
            "rubric": rubric,
            "time_limit_sec": 600,
        }
    )
    monkeypatch.setattr(testing_service, "get_bank", lambda: bank)
    monkeypatch.setattr(llm, "is_enabled", lambda: True)
    prompts = []

    async def fake_complete(system, user, hint, user_id=None):
        prompts.append(user)
        return {"hits": [True, True, False, True], "score": 1.0}  # score от LLM игнорируется

    monkeypatch.setattr(llm, "complete_json", fake_complete)

    headers = await signup(client, "open@example.com")
    await onboard(client, headers)
    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "middle"}, headers=headers
    )
    attempt_id = started.json()["id"]
    await answer_all(client, session, headers, attempt_id, correct=True)

    assert len(prompts) == 1 and "Retry-After" in prompts[0] and "rate limiting" in prompts[0]
    result = (await client.get(f"{API}/tests/attempts/{attempt_id}/result", headers=headers)).json()
    assert result["approach_score"] == 0.75

    employer = await signup_employer(client, "hr@open.ru")
    cid = await candidate_id(session, "open@example.com")
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    [answer] = card["approach_answers"]
    assert answer["question"].startswith("Как бы вы сделали rate limiting")
    assert answer["score"] == 0.75
    assert [c["met"] for c in answer["criteria"]] == [True, True, False, True]
    assert [c["text"] for c in answer["criteria"]] == rubric


async def test_open_answer_without_llm_is_kept_unscored(client, session, monkeypatch):
    from app.core import llm

    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    headers = await signup(client, "nollm@example.com")
    await onboard(client, headers)
    started = await client.post(
        f"{API}/tests/attempts", json={"specialization": "backend", "grade_target": "middle"}, headers=headers
    )
    await answer_all(client, session, headers, started.json()["id"], correct=True)
    result = (await client.get(f"{API}/tests/attempts/{started.json()['id']}/result", headers=headers)).json()
    assert result["approach_score"] is None
