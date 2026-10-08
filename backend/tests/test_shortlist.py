"""Шорт-лист переживает любую правку потребности (§8.1 п.4)."""

from sqlalchemy import update

from app.modules.candidates.models import Candidate
from app.modules.matching import service as matching_service
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup


async def test_pinned_candidate_stays_after_need_moves_to_other_category(client, session):
    """Ревью 06.10, №6: после смены категории потребности закреплённый не пропадает."""
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    pinned = await client.post(f"{API}/needs/{need['id']}/shortlist/{cid}", json={}, headers=employer)
    assert pinned.status_code == 200

    moved = NEED | {"specialization": "frontend", "grade": "senior", "required_skills": ["react"]}
    new = (await client.put(f"{API}/needs/{need['id']}", json=moved, headers=employer)).json()
    recs = (await client.get(f"{API}/needs/{new['id']}/recommendations", headers=employer)).json()

    assert new["stats"]["shortlisted"] == 1
    assert recs["shortlist"] == []
    assert [brief["id"] for brief in recs["shortlist_outside"]] == [cid]
    assert recs["shortlist_outside"][0]["display_name"] == "Анна К."


async def test_card_match_reflects_shortlist(client, session):
    """Карточка кандидата с ?need_id знает, закреплён ли он: кнопка шорт-листа в карточке."""
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    url = f"{API}/talent/candidates/{cid}?need_id={need['id']}"

    assert (await client.get(url, headers=employer)).json()["match"]["shortlisted"] is False
    await client.post(f"{API}/needs/{need['id']}/shortlist/{cid}", json={}, headers=employer)
    assert (await client.get(url, headers=employer)).json()["match"]["shortlisted"] is True
    await client.delete(f"{API}/needs/{need['id']}/shortlist/{cid}", headers=employer)
    assert (await client.get(url, headers=employer)).json()["match"]["shortlisted"] is False


async def test_pinned_outside_respects_privacy(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    await client.post(f"{API}/needs/{need['id']}/shortlist/{cid}", json={}, headers=employer)
    moved = NEED | {"specialization": "frontend", "grade": "senior", "required_skills": ["react"]}
    new = (await client.put(f"{API}/needs/{need['id']}", json=moved, headers=employer)).json()

    # Кандидат скрыл профиль — закреплённая карточка тоже не показывается
    await session.execute(update(Candidate).where(Candidate.id == cid).values(search_status="hidden"))
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    recs = (await client.get(f"{API}/needs/{new['id']}/recommendations", headers=employer)).json()
    assert recs["shortlist_outside"] == []
