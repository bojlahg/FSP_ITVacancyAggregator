"""Проверка текста потребности на запрещённые требования (§8.1): правила, публикация, режимы."""

import pytest

from app.core.config import get_settings
from app.modules.needs.text_check import check_texts
from tests.test_needs import API, NEED, no_llm, signup  # noqa: F401

DISCRIMINATORY = "Ищем девушку до 30 лет, прописка в Москве обязательна"


@pytest.mark.parametrize(
    ("text", "rules"),
    [
        (DISCRIMINATORY, ["age", "gender", "residence"]),
        ("Кандидаты 25–45 лет, молодой дружный коллектив", ["age"]),
        ("Без детей, только славяне", ["nationality", "family"]),
        ("Только граждане РФ, приятная внешность", ["appearance", "citizenship"]),
        ("Опыт от 10 лет в разработке, опыт 3–5 лет с Kafka", []),
        ("Компании более 20 лет на рынке, офис в Москве, гибрид", []),
        ("Зарплата от 300000 до 400000, Spring Boot, PostgreSQL", []),
    ],
)
def test_rules_golden(text, rules):
    assert sorted(issue.rule for issue in check_texts(text)) == sorted(rules)


async def _published_ready(client) -> tuple[dict, dict]:
    headers = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me", json={"company_name": "Банк Пример"}, headers=headers)
    response = await client.post(f"{API}/needs", json={**NEED, "raw_text": DISCRIMINATORY}, headers=headers)
    return headers, response.json()


async def test_publish_blocked_with_details(client, db):
    headers, need = await _published_ready(client)
    assert {issue["rule"] for issue in need["text_issues"]} == {"age", "gender", "residence"}

    blocked = await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)

    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "need_text_discriminatory"
    fragments = {issue["fragment"] for issue in error["details"]["issues"]}
    assert fragments == {"девушку", "до 30 лет", "прописка в Москве"}


async def test_published_need_cannot_be_edited_into_discrimination(client, db):
    headers = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me", json={"company_name": "Банк Пример"}, headers=headers)
    need = (await client.post(f"{API}/needs", json=NEED, headers=headers)).json()
    assert need["text_issues"] == []
    assert (await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)).status_code == 200

    edited = await client.put(
        f"{API}/needs/{need['id']}", json={**NEED, "team_description": "Только мужчины"}, headers=headers
    )

    assert edited.status_code == 409
    assert edited.json()["error"]["code"] == "need_text_discriminatory"


@pytest.mark.parametrize(("mode", "issues"), [("warn", 3), ("off", 0)])
async def test_modes_allow_publication(client, db, monkeypatch, mode, issues):
    monkeypatch.setattr(get_settings(), "need_text_check", mode)
    headers, need = await _published_ready(client)
    assert len(need["text_issues"]) == issues

    published = await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)

    assert published.status_code == 200, published.text


async def test_parse_reports_issues(client, db, no_llm):  # noqa: F811
    headers = await signup(client, "hr@bank.ru")
    text = "Senior Python-разработчик, Django, PostgreSQL. Только мужчины до 35 лет."

    body = (await client.post(f"{API}/needs/parse", json={"raw_text": text}, headers=headers)).json()

    assert {issue["rule"] for issue in body["text_issues"]} == {"age", "gender"}
    assert all(issue["severity"] == "block" for issue in body["text_issues"])
