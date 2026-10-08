"""Фильтры поверх подборки: «проверено тестом» и справочник городов."""

from sqlalchemy import update

from app.core.config import get_settings
from app.modules.matching.models import CandidateSearchIndex
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup


async def set_skills(session, cid: int, statuses: dict[str, str]) -> None:
    query = update(CandidateSearchIndex).where(CandidateSearchIndex.candidate_id == cid)
    await session.execute(query.values(skills_status=statuses))
    await session.commit()


async def test_verified_only_needs_one_required_skill_checked_by_test(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "recommendations_cache_seconds", 0)
    employer = await signup(client, "hr@bank.ru")
    _, anna = await make_candidate(client, session, "anna@example.com")
    _, boris = await make_candidate(client, session, "boris@example.com", first_name="Борис")
    await set_skills(session, anna, {"python": "verified", "postgresql": "declared"})
    await set_skills(session, boris, {"python": "declared", "postgresql": "declared", "kafka": "verified"})
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()

    url = f"{API}/needs/{need['id']}/recommendations"
    params = {"verified_only": "true", "group_by": "none"}
    recs = (await client.get(url, params=params, headers=employer)).json()

    assert [m["candidate"]["id"] for m in recs["candidates"]] == [anna], "желательный навык не в счёт"


async def test_cities_list_candidate_cities_most_common_first(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, _ = await make_candidate(client, session, "anna@example.com", city="Казань")
    await make_candidate(client, session, "boris@example.com", city="Москва")
    await make_candidate(client, session, "vera@example.com", city="Москва")
    await make_candidate(client, session, "gleb@example.com", city=None)

    cities = await client.get(f"{API}/talent/cities", headers=employer)

    assert cities.status_code == 200 and cities.json() == ["Москва", "Казань"]
    assert (await client.get(f"{API}/talent/cities", headers=candidate)).status_code == 403
