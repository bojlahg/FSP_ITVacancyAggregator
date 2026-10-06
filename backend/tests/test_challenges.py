"""Челленджи компании (§11.1): конструктор, публикация, прохождение, решившие, доступ и приватность."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.modules.candidates.models import Candidate
from app.modules.challenges.models import ChallengeAttempt
from tests.test_invitations import make_candidate
from tests.test_needs import API, employer_of, signup

QUESTIONS = [
    {
        "kind": "single_choice",
        "text": "Какой HTTP-код вернуть при повторном создании ресурса с тем же ключом идемпотентности?",
        "options": [
            {"text": "201 с тем же телом", "correct": True},
            {"text": "409 всегда"},
            {"text": "500"},
        ],
    },
    {
        "kind": "multi_choice",
        "text": "Что из этого — уровни изоляции транзакций в PostgreSQL?",
        "options": [
            {"text": "Read committed", "correct": True},
            {"text": "Serializable", "correct": True},
            {"text": "Eventually consistent"},
        ],
    },
    {"kind": "numeric", "text": "Сколько байт в UUID?", "number": 16},
    {
        "kind": "open_approach",
        "text": "Как бы вы ограничили частоту запросов к API?",
        "rubric": ["Алгоритм окна или ведра", "Ответ 429 и Retry-After"],
    },
]
CHALLENGE = {
    "title": "Платёжный backend",
    "description": "Ищем backend-разработчиков в платёжную команду",
    "specialization": "backend",
    "skills": ["python", "postgresql"],
    "time_per_question_sec": 60,
    "questions": QUESTIONS,
}


async def published(client, headers, **extra) -> dict:
    created = await client.post(f"{API}/employer-challenges", json=CHALLENGE | extra, headers=headers)
    assert created.status_code == 201, created.text
    done = await client.post(f"{API}/employer-challenges/{created.json()['id']}/publish", headers=headers)
    assert done.status_code == 200, done.text
    return done.json()


async def answer_all(client, session, headers, attempt_id: int, open_text: str) -> None:
    """Отвечает верно по ключу из БД: кандидату видны только перемешанные метки вариантов."""
    from app.modules.challenges.models import Challenge

    while True:
        current = (await client.get(f"{API}/challenge-attempts/{attempt_id}/current", headers=headers)).json()
        if current["finished"]:
            return
        assert not {"key", "correct", "number", "option_map"} & set(current)
        session.expire_all()
        attempt = await session.get(ChallengeAttempt, attempt_id)
        challenge = await session.get(Challenge, attempt.challenge_id)
        item = attempt.items[current["item_id"] - 1]
        question = next(q for q in challenge.questions if q["id"] == item["question_id"])
        if question["kind"] == "open_approach":
            response = {"text": open_text}
        elif question["kind"] == "numeric":
            response = {"number": question["key"]["number"]}
        else:
            shown = {original: label for label, original in item["option_map"].items()}
            response = {"choice_ids": [shown[o] for o in question["key"]["choice_ids"]]}
            assert all(option["id"] in item["option_map"] for option in current["options"])
        ack = await client.post(
            f"{API}/challenge-attempts/{attempt_id}/answer",
            json={"item_id": current["item_id"], "response": response},
            headers=headers,
        )
        assert ack.status_code == 200, ack.text


async def test_full_flow_scores_and_hides_contacts(client, session):
    employer = await signup(client, "hr@bank.ru")
    challenge = await published(client, employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")

    [card] = (await client.get(f"{API}/challenges", headers=candidate)).json()
    assert card["id"] == challenge["id"] and card["questions"] == 4 and card["attempt_id"] is None
    assert "questions" not in str(card.get("description")) and "correct" not in str(card)
    started = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()
    again = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()
    assert again["attempt_id"] == started["attempt_id"]  # одна попытка на кандидата

    await answer_all(client, session, candidate, started["attempt_id"], "Token bucket, пишите anna.k@mail.ru")
    result = (await client.get(f"{API}/challenge-attempts/{started['attempt_id']}", headers=candidate)).json()
    assert result["status"] == "completed" and result["correct"] == 3 and result["scored_total"] == 3
    assert result["score"] == 1.0

    solvers = await client.get(f"{API}/employer-challenges/{challenge['id']}/solvers", headers=employer)
    assert solvers.status_code == 200
    [solver] = solvers.json()
    assert solver["candidate"]["id"] == cid and solver["score"] == 1.0
    assert "anna.k@mail.ru" not in solvers.text and "Token bucket" in solvers.text
    own = (await client.get(f"{API}/employer-challenges/{challenge['id']}", headers=employer)).json()
    assert own["stats"] == {"started": 1, "completed": 1, "average_score": 1.0}


async def test_options_are_shuffled_and_relabelled_per_attempt(client, session):
    employer = await signup(client, "hr@bank.ru")
    challenge = await published(client, employer)
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    started = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()
    seen = []
    while True:
        current = (
            await client.get(f"{API}/challenge-attempts/{started['attempt_id']}/current", headers=candidate)
        ).json()
        if current["finished"]:
            break
        seen += [option["id"] for option in current["options"]]
        await client.post(
            f"{API}/challenge-attempts/{started['attempt_id']}/answer",
            json={"item_id": current["item_id"], "response": {"text": "-", "number": 0, "choice_ids": []}},
            headers=candidate,
        )
    assert seen and all(label.isdigit() for label in seen)  # исходные o1, o2… кандидату не видны


async def test_visibility_and_access(client, session):
    employer = await signup(client, "hr@bank.ru")
    stranger = await signup(client, "hr@retail.ru")
    challenge = await published(client, employer)
    draft = (await client.post(f"{API}/employer-challenges", json=CHALLENGE, headers=employer)).json()
    frontend = await published(client, employer, specialization="frontend", skills=[])
    senior = await published(client, employer, grade="senior")
    candidate, cid = await make_candidate(client, session, "anna@example.com")

    visible = [card["id"] for card in (await client.get(f"{API}/challenges", headers=candidate)).json()]
    assert visible == [challenge["id"]]
    for hidden in (draft, frontend, senior):
        response = await client.post(f"{API}/challenges/{hidden['id']}/start", headers=candidate)
        assert response.status_code == 404
    for path in ("", "/solvers"):
        response = await client.get(f"{API}/employer-challenges/{challenge['id']}{path}", headers=stranger)
        assert response.status_code == 404
    assert (
        await client.post(f"{API}/employer-challenges", json=CHALLENGE, headers=candidate)
    ).status_code == 403

    started = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()
    boris, _ = await make_candidate(client, session, "boris@example.com")
    url = f"{API}/challenge-attempts/{started['attempt_id']}"
    assert (await client.get(url, headers=boris)).status_code == 404
    assert (await client.get(f"{url}/current", headers=boris)).status_code == 404

    # Кандидат скрыл компанию — её новые челленджи ему не показываются
    owner = await employer_of(session, "hr@bank.ru")
    await session.execute(update(Candidate).where(Candidate.id == cid).values(hidden_employer_ids=[owner.id]))
    await session.commit()
    fresh = await published(client, employer, title="Ещё один")
    visible = [card["id"] for card in (await client.get(f"{API}/challenges", headers=candidate)).json()]
    assert fresh["id"] not in visible and challenge["id"] in visible  # начатый остаётся в списке


async def test_constructor_validation_and_publication_rules(client, db):
    employer = await signup(client, "hr@bank.ru")
    url = f"{API}/employer-challenges"
    two_correct = [
        {**QUESTIONS[0], "options": [{"text": "a", "correct": True}, {"text": "b", "correct": True}]}
    ]
    bad_single = await client.post(
        url, json=CHALLENGE | {"questions": two_correct + QUESTIONS[1:]}, headers=employer
    )
    too_few = await client.post(url, json=CHALLENGE | {"questions": QUESTIONS[:2]}, headers=employer)
    bad_sample = await client.post(url, json=CHALLENGE | {"questions_per_attempt": 9}, headers=employer)
    unknown_skill = await client.post(url, json=CHALLENGE | {"skills": ["cobol-9000"]}, headers=employer)
    assert bad_single.status_code == 422
    assert too_few.status_code == 422 and too_few.json()["error"]["code"] == "invalid_challenge"
    assert bad_sample.status_code == 422 and unknown_skill.status_code == 422

    biased = (
        await client.post(
            url, json=CHALLENGE | {"description": "Ищем только мужчин до 30 лет"}, headers=employer
        )
    ).json()
    blocked = await client.post(f"{url}/{biased['id']}/publish", headers=employer)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "challenge_text_discriminatory"

    live = await published(client, employer)
    frozen = await client.put(f"{url}/{live['id']}", json=CHALLENGE | {"title": "Другое"}, headers=employer)
    assert frozen.status_code == 409 and frozen.json()["error"]["code"] == "challenge_not_draft"
    closed = (await client.post(f"{url}/{live['id']}/close", headers=employer)).json()
    assert closed["status"] == "closed"
    reopened = await client.post(f"{url}/{live['id']}/publish", headers=employer)
    assert reopened.status_code == 409


async def test_sample_limits_questions_per_attempt(client, session):
    employer = await signup(client, "hr@bank.ru")
    challenge = await published(client, employer, questions_per_attempt=3)
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    started = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()
    assert started["total"] == 3


async def test_late_answer_scores_zero(client, session):
    employer = await signup(client, "hr@bank.ru")
    challenge = await published(client, employer)
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    attempt_id = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()[
        "attempt_id"
    ]
    current = (await client.get(f"{API}/challenge-attempts/{attempt_id}/current", headers=candidate)).json()
    attempt = await session.get(ChallengeAttempt, attempt_id)
    items = [dict(item) for item in attempt.items]
    items[0]["shown_at"] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    attempt.items = items
    await session.commit()

    ack = await client.post(
        f"{API}/challenge-attempts/{attempt_id}/answer",
        json={"item_id": current["item_id"], "response": {"choice_ids": ["1"], "number": 16, "text": "x"}},
        headers=candidate,
    )
    assert ack.status_code == 200 and ack.json()["late"] is True
    session.expire_all()
    stored = await session.get(ChallengeAttempt, attempt_id)
    assert stored.items[0]["score"] in (0.0, None)  # открытый вопрос не оценивается баллом


async def test_account_deletion_erases_open_answers(client, session):
    employer = await signup(client, "hr@bank.ru")
    challenge = await published(client, employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    attempt_id = (await client.post(f"{API}/challenges/{challenge['id']}/start", headers=candidate)).json()[
        "attempt_id"
    ]
    await answer_all(client, session, candidate, attempt_id, "Пишите anna.k@mail.ru")

    assert (await client.delete(f"{API}/candidates/me", headers=candidate)).status_code == 200
    session.expire_all()
    attempt = await session.scalar(select(ChallengeAttempt).where(ChallengeAttempt.candidate_id == cid))
    assert all("text" not in (item.get("response") or {}) for item in attempt.items)
    assert attempt.score == 1.0
