"""Потребности: CRUD, версии с шорт-листом, изоляция работодателей, публикация, разбор текста (§8.1, §8.7)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import ApplicationStatus, InvitationStatus
from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate
from app.modules.categories.service import category_ref
from app.modules.employers.models import Employer
from app.modules.invitations.models import Invitation
from app.modules.needs import parser

API = "/api/v1"

NEED = {
    "title": "Middle Python-разработчик",
    "raw_text": "Ищем Middle Python-разработчика в финтех",
    "specialization": "backend",
    "grade": "middle",
    "required_skills": ["python", "postgresql"],
    "optional_skills": ["kafka"],
    "industry": "fintech",
    "work_format": "remote",
    "salary_from": 250000,
    "salary_to": 300000,
}


async def signup(
    client, email: str, role: str = "employer", company: str | None = "Тестовая компания"
) -> dict[str, str]:
    """Работодатель по умолчанию с названием компании: без него приглашения и публикация — 409."""
    response = await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "password-123",
            "role": role,
            "consent_pd_processing": True,
            "consent_profile_publication": True,
        },
    )
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    if role == "employer" and company:
        profile = await client.put(f"{API}/employers/me", json={"company_name": company}, headers=headers)
        assert profile.status_code == 200, profile.text
    return headers


async def candidate_id(session, email: str) -> int:
    from app.modules.auth.models import User

    query = select(Candidate.id).join(User, User.id == Candidate.user_id).where(User.email == email)
    return await session.scalar(query)


async def employer_of(session, email: str) -> Employer:
    from app.modules.auth.models import User

    query = select(Employer).join(User, User.id == Employer.user_id).where(User.email == email)
    return await session.scalar(query)


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr(parser.llm, "is_enabled", lambda: False)


async def test_create_list_get_need(client, db):
    headers = await signup(client, "hr@bank.ru")

    created = await client.post(f"{API}/needs", json=NEED, headers=headers)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version"] == 1 and body["parent_id"] is None
    assert body["status"] == "active" and body["published"] is False
    assert body["category"] == category_ref("backend", "middle").model_dump(mode="json")
    assert body["stats"] == {
        "shortlisted": 0,
        "invitations_active": 0,
        "invitations_total": 0,
        "invitations_limit": get_settings().max_active_invites_per_need,
        "applications": 0,
    }
    listed = await client.get(f"{API}/needs", headers=headers)
    assert [item["id"] for item in listed.json()] == [body["id"]]
    fetched = await client.get(f"{API}/needs/{body['id']}", headers=headers)
    assert fetched.json()["required_skills"] == ["python", "postgresql"]


async def test_update_creates_version_and_keeps_shortlist(client, session):
    from tests.test_invitations import make_candidate  # кандидат в выдаче: невидимого в шорт-лист не добавить

    headers = await signup(client, "hr@bank.ru")
    _, anna = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=headers)).json()
    pinned = await client.post(
        f"{API}/needs/{need['id']}/shortlist/{anna}", json={"note": "сильный SQL"}, headers=headers
    )
    assert pinned.status_code == 200
    again = await client.post(f"{API}/needs/{need['id']}/shortlist/{anna}", json={}, headers=headers)
    assert again.status_code == 200

    updated = await client.put(
        f"{API}/needs/{need['id']}", json=NEED | {"grade": "senior", "salary_to": 380000}, headers=headers
    )

    assert updated.status_code == 200, updated.text
    new = updated.json()
    assert new["version"] == 2 and new["parent_id"] == need["id"] and new["id"] != need["id"]
    assert new["category"] == category_ref("backend", "senior").model_dump(mode="json")
    assert new["stats"]["shortlisted"] == 1
    listed = (await client.get(f"{API}/needs", headers=headers)).json()
    assert [item["id"] for item in listed] == [new["id"]]
    history = (await client.get(f"{API}/needs/{need['id']}", headers=headers)).json()
    assert history["grade"] == "middle"
    stale = await client.put(f"{API}/needs/{need['id']}", json=NEED, headers=headers)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "need_superseded"

    removed = await client.delete(f"{API}/needs/{new['id']}/shortlist/{anna}", headers=headers)
    assert removed.status_code == 200
    after = (await client.get(f"{API}/needs/{new['id']}", headers=headers)).json()
    assert after["stats"]["shortlisted"] == 0


async def test_shortlist_unknown_candidate_404(client, db):
    headers = await signup(client, "hr@bank.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=headers)).json()

    response = await client.post(f"{API}/needs/{need['id']}/shortlist/999999", json={}, headers=headers)

    assert response.status_code == 404


async def test_other_employer_gets_404(client, db):
    owner = await signup(client, "hr@bank.ru")
    stranger = await signup(client, "hr@shop.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=owner)).json()

    for method, path, kwargs in [
        ("get", f"/needs/{need['id']}", {}),
        ("put", f"/needs/{need['id']}", {"json": NEED}),
        ("post", f"/needs/{need['id']}/publish", {}),
        ("post", f"/needs/{need['id']}/unpublish", {}),
        ("post", f"/needs/{need['id']}/shortlist/1", {"json": {}}),
        ("delete", f"/needs/{need['id']}/shortlist/1", {}),
    ]:
        response = await client.request(method.upper(), f"{API}{path}", headers=stranger, **kwargs)
        assert response.status_code == 404, (method, path, response.text)
    assert (await client.get(f"{API}/needs", headers=stranger)).json() == []


async def test_candidate_cannot_use_needs(client, db):
    headers = await signup(client, "anna@example.com", role="candidate")

    assert (await client.get(f"{API}/needs", headers=headers)).status_code == 403
    assert (await client.post(f"{API}/needs", json=NEED, headers=headers)).status_code == 403
    assert (await client.get(f"{API}/employers/me", headers=headers)).status_code == 403


@pytest.mark.parametrize(
    ("override", "field", "message"),
    [
        ({"salary_from": 300000, "salary_to": 200000}, None, "salary_from не может быть больше salary_to"),
        ({"salary_from": 0}, "salary_from", "Значение слишком маленькое"),
        ({"salary_to": None}, "salary_to", None),
    ],
)
async def test_salary_validation(client, db, override, field, message):
    headers = await signup(client, "hr@bank.ru")

    response = await client.post(f"{API}/needs", json=NEED | override, headers=headers)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    details = error["details"]
    if field:
        assert any(item["loc"][-1] == field for item in details)
    if message:
        assert any(item["msg"] == message for item in details)


async def test_missing_salary_is_rejected(client, db):
    headers = await signup(client, "hr@bank.ru")
    body = {key: value for key, value in NEED.items() if key != "salary_from"}

    response = await client.post(f"{API}/needs", json=body, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["msg"] == "Обязательное поле"


async def test_unknown_catalog_values_are_rejected(client, db):
    headers = await signup(client, "hr@bank.ru")
    body = NEED | {"specialization": "astrology", "required_skills": ["python", "cobol9000"], "industry": "x"}

    response = await client.post(f"{API}/needs", json=body, headers=headers)

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert {"body", "specialization"} <= set(details[0]["loc"])
    assert {tuple(item["loc"]) for item in details} == {
        ("body", "specialization"),
        ("body", "required_skills", 1),
        ("body", "industry"),
    }
    assert details[1]["msg"] == "Неизвестный навык: cobol9000"


async def test_publish_requires_company_and_toggles(client, db):
    headers = await signup(client, "hr@bank.ru", company=None)
    need = (await client.post(f"{API}/needs", json=NEED, headers=headers)).json()

    blocked = await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "company_profile_required"

    profile = await client.put(f"{API}/employers/me", json={"company_name": "Банк Пример"}, headers=headers)
    assert profile.status_code == 200
    published = await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)
    assert published.status_code == 200
    assert published.json()["published"] is True and published.json()["published_at"]

    updated = (await client.put(f"{API}/needs/{need['id']}", json=NEED, headers=headers)).json()
    assert updated["published"] is True
    assert (await client.get(f"{API}/needs/{need['id']}", headers=headers)).json()["published"] is False

    unpublished = await client.post(f"{API}/needs/{updated['id']}/unpublish", headers=headers)
    assert unpublished.json()["published"] is False


async def test_parse_endpoint_dict_without_llm(client, db, no_llm):
    headers = await signup(client, "hr@bank.ru")
    text = "Senior DevOps-инженер\nKubernetes, Terraform, Prometheus. Удалённо, зарплата до 400к."

    response = await client.post(f"{API}/needs/parse", json={"raw_text": text}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parser"] == "dict"
    assert body["draft"]["specialization"] == "devops"
    assert body["draft"]["grade"] == "senior"
    assert body["draft"]["salary_to"] == 400000
    assert {"kubernetes", "terraform", "prometheus"} <= set(body["draft"]["required_skills"])


async def test_parse_rejects_short_text(client, db):
    headers = await signup(client, "hr@bank.ru")

    response = await client.post(f"{API}/needs/parse", json={"raw_text": "Python"}, headers=headers)

    assert response.status_code == 422


async def test_stats_and_employer_reputation(client, session):
    headers = await signup(client, "hr@bank.ru", company=None)
    await signup(client, "anna@example.com", role="candidate")
    await signup(client, "boris@example.com", role="candidate")
    anna = await candidate_id(session, "anna@example.com")
    boris = await candidate_id(session, "boris@example.com")
    employer = await employer_of(session, "hr@bank.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=headers)).json()
    now = datetime.now(UTC)

    def invitation(candidate: int, status: InvitationStatus) -> Invitation:
        return Invitation(
            employer_id=employer.id,
            candidate_id=candidate,
            need_id=need["id"],
            title="Оффер",
            message="Приглашаем",
            salary_from=250000,
            salary_to=300000,
            contact_method={"email": "hr@bank.ru"},
            status=status,
            expires_at=now + timedelta(days=14),
        )

    session.add_all(
        [
            invitation(anna, InvitationStatus.accepted),
            invitation(boris, InvitationStatus.sent),
            invitation(anna, InvitationStatus.declined),
            invitation(boris, InvitationStatus.withdrawn),
            Application(
                need_id=need["id"],
                candidate_id=anna,
                status=ApplicationStatus.accepted,
                created_at=now - timedelta(hours=10),
                responded_at=now,
            ),
        ]
    )
    await session.commit()

    updated = (await client.put(f"{API}/needs/{need['id']}", json=NEED, headers=headers)).json()
    assert updated["stats"]["invitations_total"] == 4
    assert updated["stats"]["invitations_active"] == 1
    assert updated["stats"]["applications"] == 1

    profile = (await client.get(f"{API}/employers/me", headers=headers)).json()
    assert profile["company_name"] is None
    assert profile["reputation"] == {
        "invitations_sent": 4,
        "acceptance_rate": 0.5,
        "withdrawn_rate": 0.25,
        "median_response_hours": 10.0,
    }


async def test_employer_profile_update_and_validation(client, db):
    headers = await signup(client, "hr@bank.ru")
    body = {
        "company_name": "Банк Пример",
        "inn": "7707083893",
        "industry": "fintech",
        "website": "https://bank.example",
        "contact_email": "hr@bank.example",
    }

    saved = await client.put(f"{API}/employers/me", json=body, headers=headers)

    assert saved.status_code == 200, saved.text
    assert saved.json()["company_name"] == "Банк Пример"
    assert saved.json()["reputation"]["acceptance_rate"] is None
    assert (await client.get(f"{API}/employers/me", headers=headers)).json()["industry"] == "fintech"
    bad = await client.put(f"{API}/employers/me", json=body | {"industry": "astrology"}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["msg"] == "Неизвестная отрасль"
    bad_inn = await client.put(f"{API}/employers/me", json=body | {"inn": "12"}, headers=headers)
    assert bad_inn.status_code == 422
