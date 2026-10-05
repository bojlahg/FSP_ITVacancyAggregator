"""Регулярные задания (§11): жизненный цикл, проверка, влияние на навыки и индекс, изоляция."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.enums import Grade, Role, SkillSource, UnlockSource
from app.modules.candidates.models import CandidateSkill
from app.modules.categories.models import CandidateCategory
from app.modules.invitations.models import ContactUnlock
from app.modules.matching import service as matching_service
from app.modules.matching.models import CandidateSearchIndex
from app.modules.tasks import service as tasks_service
from app.modules.tasks.models import TaskAssignment
from tests.conftest import bearer_for
from tests.test_needs import NEED, candidate_id, employer_of, signup

API = "/api/v1"
TEMPLATE = "be.db.composite_index"
AUTO = {
    "title": "Индекс для ленты платежей",
    "kind": "auto",
    "specialization": "backend",
    "template_id": TEMPLATE,
}
APPROACH = {
    "title": "Идемпотентные платежи",
    "kind": "approach",
    "specialization": "backend",
    "grade": "middle",
    "prompt": "Как сделать повторный запрос оплаты безопасным?",
    "rubric": [
        "Ключ идемпотентности",
        "Хранение результата",
        "Уникальный индекс",
        "Повтор возвращает тот же ответ",
    ],
}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(tasks_service.llm, "is_enabled", lambda: False)


async def candidate_with_category(client, session, email: str, grade: str = "middle") -> tuple[dict, int]:
    headers = await signup(client, email, role="candidate")
    cid = await candidate_id(session, email)
    now = datetime.now(UTC)
    session.add(
        CandidateCategory(
            candidate_id=cid,
            specialization="backend",
            grade=Grade(grade),
            theta=0.5,
            percentile=0.5,
            assigned_at=now - timedelta(days=60),
            valid_until=now + timedelta(days=300),
            is_current=True,
        )
    )
    await session.flush()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    return headers, cid


async def answer_key(session, assignment_id: int) -> dict:
    session.expire_all()
    assignment = await session.get(TaskAssignment, assignment_id)
    return assignment.answer_key


async def test_auto_task_lifecycle_confirms_skills(client, session):
    employer = await signup(client, "hr@bank.ru")
    created = await client.post(f"{API}/employer-tasks", json=AUTO, headers=employer)
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    headers, cid = await candidate_with_category(client, session, "anna@example.com")

    tasks = await client.get(f"{API}/candidates/me/tasks", headers=headers)
    assert tasks.status_code == 200, tasks.text
    [offered] = tasks.json()
    assert offered["status"] == "offered" and offered["company_name"]
    assert offered["item"]["options"] and "answer_key" not in tasks.text and "correct" not in tasks.text

    key = await answer_key(session, offered["id"])
    submitted = await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit",
        json={"response": {"choice_ids": key["choice_ids"]}},
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted" and body["score"] == 1.0 and body["graded_by"] == "auto"
    assert body["confirmed_skills"]

    profile = (await client.get(f"{API}/candidates/me", headers=headers)).json()
    statuses = {skill["skill_id"]: skill["status"] for skill in profile["skills"]}
    assert statuses["postgresql"] == "task_confirmed" and statuses["sql"] == "task_confirmed"
    session.expire_all()
    index = await session.get(CandidateSearchIndex, cid)
    assert index.skills_status["postgresql"] == "task_confirmed"
    assert (datetime.now(UTC) - index.last_activity_at).total_seconds() < 120  # решение освежило профиль

    again = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    assert len(again) == 1  # следующее — не раньше чем через неделю

    resubmit = await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit",
        json={"response": {"choice_ids": ["a"]}},
        headers=headers,
    )
    assert resubmit.status_code == 409

    submissions = await client.get(f"{API}/employer-tasks/{task_id}/submissions", headers=employer)
    assert submissions.status_code == 200
    [submission] = submissions.json()
    assert submission["candidate"]["id"] == cid and submission["score"] == 1.0
    assert "phone" not in submissions.text and "anna@example.com" not in submissions.text
    listed = (await client.get(f"{API}/employer-tasks", headers=employer)).json()
    assert listed[0]["assignments_total"] == 1 and listed[0]["submissions"] == 1


async def test_wrong_answer_does_not_confirm_skills(client, session):
    employer = await signup(client, "hr@bank.ru")
    await client.post(f"{API}/employer-tasks", json=AUTO, headers=employer)
    headers, _ = await candidate_with_category(client, session, "anna@example.com")
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    key = await answer_key(session, offered["id"])
    wrong = next(o["id"] for o in offered["item"]["options"] if o["id"] not in key["choice_ids"])

    body = (
        await client.post(
            f"{API}/tasks/assignments/{offered['id']}/submit",
            json={"response": {"choice_ids": [wrong]}},
            headers=headers,
        )
    ).json()

    assert body["score"] == 0.0 and body["confirmed_skills"] == []
    profile = (await client.get(f"{API}/candidates/me", headers=headers)).json()
    assert all(skill["status"] != "task_confirmed" for skill in profile["skills"])


async def test_approach_without_llm_waits_for_employer_rating(client, session):
    employer = await signup(client, "hr@bank.ru")
    task_id = (await client.post(f"{API}/employer-tasks", json=APPROACH, headers=employer)).json()["id"]
    headers, cid = await candidate_with_category(client, session, "anna@example.com")
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    assert offered["item"] is None and offered["rubric"] == APPROACH["rubric"]

    empty = await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit", json={"response": {"text": "  "}}, headers=headers
    )
    assert empty.status_code == 422
    body = (
        await client.post(
            f"{API}/tasks/assignments/{offered['id']}/submit",
            json={"response": {"text": "Ключ идемпотентности и уникальный индекс"}},
            headers=headers,
        )
    ).json()
    assert body["status"] == "submitted" and body["score"] is None and body["graded_by"] is None
    assert (await client.get(f"{API}/employer-tasks", headers=employer)).json()[0]["awaiting_rating"] == 1

    rated = await client.post(
        f"{API}/employer-tasks/{task_id}/submissions/{offered['id']}/rate",
        json={"rating": 5},
        headers=employer,
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["score"] == 1.0 and rated.json()["graded_by"] == "employer"
    session.expire_all()
    assert (await session.get(CandidateSearchIndex, cid)).approach == 1.0


async def test_approach_checklist_by_llm_scored_by_code(client, session, monkeypatch):
    employer = await signup(client, "hr@bank.ru")
    task_id = (await client.post(f"{API}/employer-tasks", json=APPROACH, headers=employer)).json()["id"]
    headers, _ = await candidate_with_category(client, session, "anna@example.com")
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    monkeypatch.setattr(tasks_service.llm, "is_enabled", lambda: True)

    async def fake_complete(system, user, hint, user_id=None):
        return {"hits": [True, False, True, True], "score": 0.01}

    monkeypatch.setattr(tasks_service.llm, "complete_json", fake_complete)

    body = (
        await client.post(
            f"{API}/tasks/assignments/{offered['id']}/submit",
            json={"response": {"text": "Ключ идемпотентности в заголовке"}},
            headers=headers,
        )
    ).json()
    assert body["score"] == 0.75 and body["graded_by"] == "llm"  # score LLM игнорируется

    rated = (
        await client.post(
            f"{API}/employer-tasks/{task_id}/submissions/{offered['id']}/rate",
            json={"rating": 2},
            headers=employer,
        )
    ).json()
    assert (
        rated["score"] == 0.75
        and rated["employer_rating"] == 2
        and rated["rubric_hits"] == [True, False, True, True]
    )


async def test_submission_text_hides_contacts_until_unlock(client, session):
    """Ревью 06.10, №2: свободный текст решения не раскрывает контакты без contact_unlocks."""
    employer = await signup(client, "hr@bank.ru")
    task_id = (await client.post(f"{API}/employer-tasks", json=APPROACH, headers=employer)).json()["id"]
    headers, cid = await candidate_with_category(client, session, "anna@example.com")
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    text = "Ключ идемпотентности. Пишите на anna.k@mail.ru или +7 916 123-45-67"
    submitted = await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit", json={"response": {"text": text}}, headers=headers
    )
    assert submitted.status_code == 200, submitted.text

    listed = await client.get(f"{API}/employer-tasks/{task_id}/submissions", headers=employer)
    rate_url = f"{API}/employer-tasks/{task_id}/submissions/{offered['id']}/rate"
    rated = await client.post(rate_url, json={"rating": 4}, headers=employer)
    for response in (listed, rated):
        assert response.status_code == 200, response.text
        assert "anna.k@mail.ru" not in response.text and "123-45-67" not in response.text
    assert "Ключ идемпотентности" in listed.text

    owner = await employer_of(session, "hr@bank.ru")
    unlock = ContactUnlock(
        employer_id=owner.id, candidate_id=cid, source=UnlockSource.invitation, source_id=1
    )
    session.add(unlock)
    await session.commit()
    unlocked = await client.get(f"{API}/employer-tasks/{task_id}/submissions", headers=employer)
    assert "anna.k@mail.ru" in unlocked.text


async def test_one_active_task_weekly_and_expiry(client, session):
    employer = await signup(client, "hr@bank.ru")
    await client.post(f"{API}/employer-tasks", json=AUTO, headers=employer)
    await client.post(f"{API}/employer-tasks", json=APPROACH, headers=employer)
    headers, cid = await candidate_with_category(client, session, "anna@example.com")

    first = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    assert len(first) == 1
    assert len((await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()) == 1

    past = datetime.now(UTC) - timedelta(days=8)
    await session.execute(
        update(TaskAssignment).where(TaskAssignment.candidate_id == cid).values(due_at=past, offered_at=past)
    )
    await session.commit()
    expired = await client.post(
        f"{API}/tasks/assignments/{first[0]['id']}/submit", json={"response": {"text": "x"}}, headers=headers
    )
    assert expired.status_code == 409

    later = (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json()
    assert [item["status"] for item in later] == ["offered", "expired"]
    assert later[0]["title"] != first[0]["title"]

    skipped = await client.post(f"{API}/tasks/assignments/{later[0]['id']}/skip", headers=headers)
    assert skipped.status_code == 200 and skipped.json()["status"] == "skipped"


async def test_offer_respects_grade_and_hidden_employers(client, session):
    employer = await signup(client, "hr@bank.ru")
    await client.post(f"{API}/employer-tasks", json={**AUTO, "grade": "senior"}, headers=employer)
    no_category = await signup(client, "new@example.com", role="candidate")
    headers, _ = await candidate_with_category(client, session, "anna@example.com")

    assert (await client.get(f"{API}/candidates/me/tasks", headers=headers)).json() == []
    assert (await client.get(f"{API}/candidates/me/tasks", headers=no_category)).json() == []


async def test_isolation_between_candidates_and_employers(client, session):
    owner = await signup(client, "hr@bank.ru")
    stranger = await signup(client, "hr@retail.ru")
    task_id = (await client.post(f"{API}/employer-tasks", json=APPROACH, headers=owner)).json()["id"]
    anna, _ = await candidate_with_category(client, session, "anna@example.com")
    boris, _ = await candidate_with_category(client, session, "boris@example.com")
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=anna)).json()

    foreign_submit = await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit", json={"response": {"text": "чужое"}}, headers=boris
    )
    assert foreign_submit.status_code == 404
    assert (
        await client.post(f"{API}/tasks/assignments/{offered['id']}/skip", headers=boris)
    ).status_code == 404
    await client.post(
        f"{API}/tasks/assignments/{offered['id']}/submit",
        json={"response": {"text": "мой подход"}},
        headers=anna,
    )

    assert (
        await client.get(f"{API}/employer-tasks/{task_id}/submissions", headers=stranger)
    ).status_code == 404
    rate = await client.post(
        f"{API}/employer-tasks/{task_id}/submissions/{offered['id']}/rate",
        json={"rating": 4},
        headers=stranger,
    )
    assert rate.status_code == 404
    assert (await client.get(f"{API}/employer-tasks", headers=stranger)).json() == []

    assert (
        await client.get(f"{API}/employer-tasks", headers=await bearer_for(session, Role.candidate))
    ).status_code == 403
    assert (
        await client.get(f"{API}/candidates/me/tasks", headers=await bearer_for(session, Role.employer))
    ).status_code == 403


async def test_create_validation(client, db):
    owner = await signup(client, "hr@bank.ru")
    stranger = await signup(client, "hr@retail.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=owner)).json()

    unknown = await client.post(f"{API}/employer-tasks", json={**AUTO, "template_id": "nope"}, headers=owner)
    wrong_spec = await client.post(
        f"{API}/employer-tasks", json={**AUTO, "specialization": "devops"}, headers=owner
    )
    too_long = await client.post(
        f"{API}/employer-tasks",
        json={**APPROACH, "rubric": [f"критерий {i}" for i in range(7)]},
        headers=owner,
    )
    foreign_need = await client.post(
        f"{API}/employer-tasks", json={**AUTO, "need_id": need["id"]}, headers=stranger
    )
    by_need = await client.post(
        f"{API}/employer-tasks", json={**AUTO, "specialization": "qa", "need_id": need["id"]}, headers=owner
    )

    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_template"
    assert wrong_spec.status_code == 422
    assert too_long.status_code == 422
    assert foreign_need.status_code == 404
    assert by_need.status_code == 201, by_need.text
    assert by_need.json()["specialization"] == "backend" and by_need.json()["grade"] == "middle"


async def test_template_options_prefer_need_skills(client, db):
    owner = await signup(client, "hr@bank.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=owner)).json()

    options = await client.get(
        f"{API}/employer-tasks/templates", params={"need_id": need["id"]}, headers=owner
    )

    assert options.status_code == 200, options.text
    items = options.json()
    assert items[0]["matches_need"] is True
    assert not any(item["id"].startswith("be.java.") for item in items)  # стек потребности — Python
    assert "choice_ids" not in options.text
    missing = await client.get(f"{API}/employer-tasks/templates", headers=owner)
    assert missing.status_code == 422


async def test_assignment_answer_key_stays_in_db(client, session):
    employer = await signup(client, "hr@bank.ru")
    await client.post(f"{API}/employer-tasks", json=AUTO, headers=employer)
    headers, cid = await candidate_with_category(client, session, "anna@example.com")
    response = await client.get(f"{API}/candidates/me/tasks", headers=headers)

    stored = await session.scalar(select(TaskAssignment).where(TaskAssignment.candidate_id == cid))
    assert stored.answer_key["choice_ids"]
    assert "choice_ids" not in response.text


async def test_index_keeps_strongest_skill_source(client, session):
    """Ревью 06.10, №5: «проверено тестом» сильнее «подтверждено заданием» независимо от порядка строк."""
    employer = await signup(client, "hr@bank.ru")
    _, cid = await candidate_with_category(client, session, "anna@example.com")
    now = datetime.now(UTC)
    for source in (SkillSource.task, SkillSource.test):
        session.add(CandidateSkill(candidate_id=cid, skill_id="python", source=source, updated_at=now))
        await session.commit()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()

    session.expire_all()
    assert (await session.get(CandidateSearchIndex, cid)).skills_status["python"] == "verified"
    params = {"skills": "python", "verified_only": "true"}
    found = (await client.get(f"{API}/talent/search", params=params, headers=employer)).json()
    assert cid in [item["id"] for item in found["items"]]
