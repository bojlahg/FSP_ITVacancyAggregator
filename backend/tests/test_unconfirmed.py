"""Кандидат без подтверждённого тестом грейда: виден после всех подтверждённых, с пометкой (§8.2)."""

from datetime import UTC, datetime

from sqlalchemy import update

from app.core.config import get_settings
from app.core.enums import SkillSource
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.matching import service as matching_service
from app.modules.matching.models import CandidateSearchIndex
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, NEED, candidate_id, employer_of, signup


async def make_unconfirmed(client, session, email: str, **profile) -> tuple[dict[str, str], int]:
    """Кандидат прошёл опрос и выбрал специализацию, но категории (теста) нет."""
    headers = await signup(client, email, role="candidate")
    cid = await candidate_id(session, email)
    values = {
        "first_name": "Борис",
        "last_name": "Петров",
        "phone": "+7 900 111-11-11",
        "telegram": "@boris",
        "contact_email": "boris@example.com",
        "about": "Пишите на boris@example.com",
        "city": "Москва",
        "work_formats": ["remote"],
        "salary_min": 200000,
        "specialization": "backend",
    } | profile
    await session.execute(update(Candidate).where(Candidate.id == cid).values(**values))
    now = datetime.now(UTC)
    session.add(
        CandidateSkill(candidate_id=cid, skill_id="python", source=SkillSource.declared, updated_at=now)
    )
    # Навык от старой попытки без категории не должен выдаваться за «проверено тестом»
    session.add(
        CandidateSkill(candidate_id=cid, skill_id="postgresql", source=SkillSource.test, updated_at=now)
    )
    await session.flush()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    return headers, cid


async def test_search_lists_unconfirmed_after_confirmed_and_marks_them(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, boris = await make_unconfirmed(client, session, "boris@example.com", salary_min=100000)
    _, anna = await make_candidate(client, session, "anna@example.com")

    for sort in ("vps", "percentile", "fresh"):
        found = (await client.get(f"{API}/talent/search", params={"sort": sort}, headers=employer)).json()
        assert [item["id"] for item in found["items"]] == [anna, boris], sort
        assert found["total"] == 2

    items = (await client.get(f"{API}/talent/search", headers=employer)).json()["items"]
    confirmed, unconfirmed = items
    assert confirmed["grade_confirmed"] is True and confirmed["category"]["label"] == "Backend · Middle"
    assert unconfirmed["grade_confirmed"] is False and unconfirmed["category"] is None
    assert unconfirmed["specialization"] == "backend" and unconfirmed["percentile"] is None
    assert unconfirmed["verified_skills"] == [] and unconfirmed["declared_skills"] == ["Python"]

    by_grade = (await client.get(f"{API}/talent/search", params={"grade": "middle"}, headers=employer)).json()
    assert [item["id"] for item in by_grade["items"]] == [anna]
    by_spec = await client.get(f"{API}/talent/search", params={"specialization": "backend"}, headers=employer)
    assert boris in [item["id"] for item in by_spec.json()["items"]]
    # Каталог и рыночные агрегаты — только по категориям из теста
    catalog = (await client.get(f"{API}/talent/categories", headers=employer)).json()
    assert [(item["category"]["label"], item["candidates_count"]) for item in catalog] == [
        ("Backend · Middle", 1)
    ]


async def test_recommendations_put_unconfirmed_in_separate_tail(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, anna = await make_candidate(client, session, "anna@example.com")
    _, boris = await make_unconfirmed(client, session, "boris@example.com")
    await make_unconfirmed(client, session, "fedor@example.com", specialization="frontend")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()

    recs = (await client.get(f"{API}/needs/{need['id']}/recommendations", headers=employer)).json()

    assert [m["candidate"]["id"] for m in recs["candidates"]] == [anna] and recs["total"] == 1
    assert [m["candidate"]["id"] for m in recs["unconfirmed"]] == [boris], "другая специализация не видна"
    assert recs["unconfirmed_total"] == 1
    tail = recs["unconfirmed"][0]
    assert tail["candidate"]["grade_confirmed"] is False
    assert tail["components"]["category"] == 0 and tail["components"]["strength"] == 0
    assert tail["explanation"]["lines"][0]["text"].startswith("Грейд не подтверждён тестом")
    assert not any("Категория совпадает" in line["text"] for line in tail["explanation"]["lines"])
    assert [card["category"]["label"] for card in recs["categories"]] == ["Backend · Middle"]

    by_grade = await client.get(
        f"{API}/needs/{need['id']}/recommendations", params={"grade": "middle"}, headers=employer
    )
    assert by_grade.json()["unconfirmed"] == []
    flat = await client.get(
        f"{API}/needs/{need['id']}/recommendations", params={"group_by": "none"}, headers=employer
    )
    assert [m["candidate"]["id"] for m in flat.json()["candidates"]] == [anna]
    coverage = (await client.get(f"{API}/needs/{need['id']}/salary-coverage", headers=employer)).json()
    assert sum(bucket["count"] for bucket in coverage["histogram"]) == 1, "только кандидаты категории"


async def test_setting_off_hides_unconfirmed_everywhere(client, session, monkeypatch):
    employer = await signup(client, "hr@bank.ru")
    _, anna = await make_candidate(client, session, "anna@example.com")
    _, boris = await make_unconfirmed(client, session, "boris@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    monkeypatch.setattr(get_settings(), "show_unconfirmed_candidates", False)
    monkeypatch.setattr(get_settings(), "recommendations_cache_seconds", 0)

    found = (await client.get(f"{API}/talent/search", headers=employer)).json()
    assert [item["id"] for item in found["items"]] == [anna] and found["total"] == 1
    recs = (await client.get(f"{API}/needs/{need['id']}/recommendations", headers=employer)).json()
    assert recs["unconfirmed"] == [] and recs["unconfirmed_total"] == 0
    assert (await client.get(f"{API}/talent/candidates/{boris}", headers=employer)).status_code == 404
    assert (await client.post(f"{API}/invitations", json=invite(boris), headers=employer)).status_code == 404


async def test_unconfirmed_respects_privacy_and_hidden_company(client, session):
    employer = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@shop.ru")
    candidate, boris = await make_unconfirmed(client, session, "boris@example.com")
    bank = await employer_of(session, "hr@bank.ru")

    saved = await client.put(
        f"{API}/candidates/me/privacy",
        json={
            "show_last_name": False,
            "show_fsp": True,
            "show_salary": False,
            "hidden_employer_ids": [bank.id],
        },
        headers=candidate,
    )
    assert saved.status_code == 200, saved.text

    assert (await client.get(f"{API}/talent/candidates/{boris}", headers=employer)).status_code == 404
    assert (await client.post(f"{API}/invitations", json=invite(boris), headers=employer)).status_code == 404
    assert (await client.get(f"{API}/talent/search", headers=employer)).json()["items"] == []
    session.expire_all()
    assert (await session.get(CandidateSearchIndex, boris)).salary_min is None, (
        "скрытая зарплата не в индексе"
    )
    shown = (await client.get(f"{API}/talent/search", headers=other)).json()["items"]
    assert [item["id"] for item in shown] == [boris] and shown[0]["salary_min"] is None
    filtered = await client.get(f"{API}/talent/search", params={"salary_max": 150000}, headers=other)
    assert [item["id"] for item in filtered.json()["items"]] == [boris], "скрытая зарплата не фильтруется"

    await client.put(
        f"{API}/candidates/me/search-status", json={"search_status": "hidden"}, headers=candidate
    )
    assert (await client.get(f"{API}/talent/search", headers=other)).json()["items"] == []


async def test_invite_unconfirmed_without_category_claim_and_contacts_only_after_accept(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, boris = await make_unconfirmed(client, session, "boris@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()

    card = (await client.get(f"{API}/talent/candidates/{boris}", headers=employer)).json()
    assert card["brief"]["grade_confirmed"] is False and card["contacts"] is None
    assert card["contacts_unlocked"] is False and "boris@example.com" not in (card["about"] or "")
    assert card["topic_scores"] == [] and card["grade_history"] == [] and card["grade_evidence"] is None
    resume = (await client.get(f"{API}/talent/candidates/{boris}/resume.json", headers=employer)).json()
    assert resume["basics"]["label"] == "Backend · грейд не подтверждён" and resume["basics"]["email"] is None
    assert resume["x-itscout"]["category"] is None and resume["x-itscout"]["grade_confirmed"] is False

    for body in (invite(boris, need_id=need["id"]), invite(boris, title="Без потребности")):
        created = await client.post(f"{API}/invitations", json=body, headers=employer)
        assert created.status_code == 201, created.text
        lines = created.json()["match_snapshot"]["lines"]
        assert lines[0]["text"].startswith("Грейд не подтверждён тестом")
        assert not any("Категория совпадает" in line["text"] for line in lines)
        assert created.json()["contacts"] is None
        await client.post(f"{API}/invitations/{created.json()['id']}/withdraw", headers=employer)

    sent = (await client.post(f"{API}/invitations", json=invite(boris), headers=employer)).json()
    listed = (await client.get(f"{API}/employers/me/invitations", headers=employer)).json()
    assert all(item["contacts"] is None for item in listed)
    assert listed[0]["candidate"]["grade_confirmed"] is False
    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    assert inbox[0]["salary_market"] is None, "рынка категории без категории нет"

    accepted = await client.post(f"{API}/invitations/{sent['id']}/accept", headers=candidate)
    assert accepted.status_code == 200, accepted.text
    card = (await client.get(f"{API}/talent/candidates/{boris}", headers=employer)).json()
    assert card["contacts_unlocked"] is True and card["contacts"]["telegram"] == "@boris"


async def test_index_row_needs_specialization_and_live_account(client, session):
    candidate, boris = await make_unconfirmed(client, session, "boris@example.com")
    _, nobody = await make_unconfirmed(client, session, "nobody@example.com", specialization=None)
    session.expire_all()
    row = await session.get(CandidateSearchIndex, boris)
    assert row is not None and row.grade is None and row.theta is None and row.visible
    assert row.skills_status == {"python": "declared"}
    assert await session.get(CandidateSearchIndex, nobody) is None

    market = (await client.get(f"{API}/candidates/me/market", headers=candidate)).json()
    assert market["category"] is None and market["suppressed"] is True

    assert (await client.delete(f"{API}/candidates/me", headers=candidate)).status_code == 200
    await matching_service.refresh_candidate(session, boris)
    await session.commit()
    session.expire_all()
    assert await session.get(CandidateSearchIndex, boris) is None
