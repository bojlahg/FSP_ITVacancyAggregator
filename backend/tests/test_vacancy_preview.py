"""«Проверка под вакансию» (§10.7): blueprint по навыкам, примеры без ключей, черновики LLM, доступ."""

import json

import pytest

from app.core.enums import Role
from app.modules.testing import preview_service
from app.modules.testing.engine import vacancy
from app.modules.testing.engine.bank import get_bank, get_blueprints
from app.modules.testing.engine.render import render
from tests.conftest import bearer
from tests.test_needs import NEED, signup

API = "/api/v1"
BACKEND_TEXT = (
    "Backend-разработчик Middle (Python) в платёжную команду.\n"
    "Требования: Python, PostgreSQL, Kafka. Будет плюсом: Redis, gRPC.\n"
    "Зарплата 220 000 – 280 000 ₽."
)
FORBIDDEN_KEYS = {"answer_key", "key", "correct_option_ids", "correct", "order", "number"}


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(preview_service.llm, "is_enabled", lambda: False)


def test_kafka_and_postgresql_shift_topic_weights():
    blueprints = get_blueprints()
    base = blueprints.specializations["backend"].topics
    plan = vacancy.build(get_bank(), blueprints, "backend", ["python", "postgresql", "kafka"], [], ["python"])

    assert sum(plan.topics.values()) == sum(base.values())
    boosted = {boost.skill: boost.topic for boost in plan.boosts}
    assert boosted["kafka"] == "architecture" and boosted["postgresql"] == "databases"
    assert plan.topics["architecture"] > base["architecture"]
    assert plan.stack_modules == ["python"]
    assert plan == vacancy.build(
        get_bank(), blueprints, "backend", ["python", "postgresql", "kafka"], [], ["python"]
    )


def test_skill_without_templates_is_uncovered_and_missing_stack_drops_topic():
    plan = vacancy.build(get_bank(), get_blueprints(), "backend", ["helm"], [], [])

    assert plan.uncovered_skills == ["helm"]
    assert plan.dropped_topics == ["stack"] and "stack" not in plan.topics


def test_regeneration_keeps_templates_and_changes_instances():
    blueprints = get_blueprints()
    plan = vacancy.build(get_bank(), blueprints, "backend", ["python", "postgresql"], [], ["python"])
    templates = vacancy.sample_templates(get_bank(), blueprints, plan, ["python", "postgresql"], "middle")

    assert len(templates) == blueprints.vacancy.sample_items
    assert len({t.topic for t in templates}) == len(templates)
    first = [render(t, 1).stem for t in templates] + [render(t, 1).options for t in templates]
    second = [render(t, 2).stem for t in templates] + [render(t, 2).options for t in templates]
    assert first != second


async def test_preview_from_text_without_llm(client, db):
    headers = await signup(client, "hr@bank.ru")

    response = await client.post(
        f"{API}/vacancy-tests/preview", json={"raw_text": BACKEND_TEXT}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requirements"]["specialization"] == "backend"
    assert body["blueprint"]["grade"] == "middle"
    topics = {t["topic"]: t for t in body["blueprint"]["topics"]}
    assert topics["databases"]["items"] > topics["databases"]["base_items"]
    assert any("Kafka" in change for change in body["blueprint"]["weight_changes"])
    assert len(body["sample_items"]) == 3
    assert body["seed"] == 1
    assert body["llm_available"] is False and body["llm_drafts"] == []
    assert [s["id"] for s in body["uncovered_skills"]] == ["grpc"]
    assert "выключена" in body["llm_note"]
    assert not FORBIDDEN_KEYS & _keys(body["sample_items"])


async def test_preview_is_deterministic_and_seed_changes_only_instances(client, db):
    headers = await signup(client, "hr@bank.ru")
    url = f"{API}/vacancy-tests/preview"

    first = (await client.post(url, json={"raw_text": BACKEND_TEXT}, headers=headers)).json()
    again = (await client.post(url, json={"raw_text": BACKEND_TEXT}, headers=headers)).json()
    other = (
        await client.post(url, json={"raw_text": BACKEND_TEXT, "regenerate_seed": 2}, headers=headers)
    ).json()

    assert first == again
    assert other["seed"] == 2
    assert [(i["template_id"], i["difficulty_b"]) for i in first["sample_items"]] == [
        (i["template_id"], i["difficulty_b"]) for i in other["sample_items"]
    ]
    assert json.dumps(first["sample_items"]) != json.dumps(other["sample_items"])


async def test_preview_from_own_need_and_foreign_need_is_404(client, db):
    owner = await signup(client, "hr@bank.ru")
    stranger = await signup(client, "hr@retail.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=owner)).json()

    own = await client.post(f"{API}/vacancy-tests/preview", json={"need_id": need["id"]}, headers=owner)
    foreign = await client.post(
        f"{API}/vacancy-tests/preview", json={"need_id": need["id"]}, headers=stranger
    )

    assert own.status_code == 200, own.text
    assert own.json()["requirements"]["required_skills"] == NEED["required_skills"]
    assert own.json()["blueprint"]["stack_modules"] == ["python"]
    assert foreign.status_code == 404


async def test_candidate_cannot_preview(client):
    response = await client.post(
        f"{API}/vacancy-tests/preview", json={"raw_text": BACKEND_TEXT}, headers=bearer(Role.candidate)
    )
    examples = await client.get(f"{API}/vacancy-tests/examples", headers=bearer(Role.candidate))

    assert response.status_code == 403
    assert examples.status_code == 403


async def test_unrecognized_text_is_422(client, db):
    headers = await signup(client, "hr@bank.ru")

    response = await client.post(
        f"{API}/vacancy-tests/preview",
        json={"raw_text": "Ищем хорошего человека в дружную команду, печеньки и кофе"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "specialization_not_detected"


async def test_demo_examples_all_build_a_preview(client, db):
    headers = await signup(client, "hr@bank.ru")
    examples = (await client.get(f"{API}/vacancy-tests/examples", headers=headers)).json()

    assert len(examples) == 4
    specs = set()
    for example in examples:
        response = await client.post(
            f"{API}/vacancy-tests/preview", json={"raw_text": example["raw_text"]}, headers=headers
        )
        assert response.status_code == 200, (example["slug"], response.text)
        specs.add(response.json()["requirements"]["specialization"])
    assert specs == {"backend", "frontend", "qa", "devops"}


async def test_llm_drafts_are_validated_and_pilot(client, db, monkeypatch):
    headers = await signup(client, "hr@bank.ru")
    monkeypatch.setattr(preview_service.llm, "is_enabled", lambda: True)

    async def fake_complete(system, user, hint, user_id=None):
        return {
            "drafts": [
                {"title": "gRPC-стримы", "topic": "http_api", "skills": ["grpc"], "stem": "Когда стрим?"},
                {"title": "Чужая тема", "topic": "cooking", "skills": ["grpc"], "stem": "?"},
                {"title": "Чужой навык", "topic": "http_api", "skills": ["cobol"], "stem": "?"},
            ]
        }

    monkeypatch.setattr(preview_service.llm, "complete_json", fake_complete)

    body = (
        await client.post(f"{API}/vacancy-tests/preview", json={"raw_text": BACKEND_TEXT}, headers=headers)
    ).json()

    assert body["llm_available"] is True
    assert [d["title"] for d in body["llm_drafts"]] == ["gRPC-стримы"]
    assert body["llm_drafts"][0]["status"] == "pilot"
