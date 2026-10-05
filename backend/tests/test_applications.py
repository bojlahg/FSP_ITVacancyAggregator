"""Вакансии и отклики: подбор по категории, отклик раскрывает контакты, изоляция сторон (§8.7)."""

from sqlalchemy import select

from app.modules.invitations.models import ContactUnlock
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup


async def publish(client, headers, **fields) -> dict:
    await client.put(f"{API}/employers/me", json={"company_name": "Банк"}, headers=headers)
    need = (await client.post(f"{API}/needs", json=NEED | fields, headers=headers)).json()
    published = await client.post(f"{API}/needs/{need['id']}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return published.json()


async def test_vacancies_sorted_by_match_and_apply_unlocks_contacts(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    frontend = await publish(
        client, employer, title="Frontend", specialization="frontend", required_skills=["react"]
    )
    backend = await publish(client, employer, title="Backend")
    hidden = (await client.post(f"{API}/needs", json=NEED | {"title": "Черновик"}, headers=employer)).json()

    listed = (await client.get(f"{API}/vacancies", headers=candidate)).json()

    assert [item["id"] for item in listed] == [backend["id"], frontend["id"]]
    assert listed[0]["match_score"] > 0 and listed[0]["match_explanation"]["lines"]
    assert listed[1]["match_score"] is None
    assert hidden["id"] not in [item["id"] for item in listed]
    assert (await client.get(f"{API}/vacancies/{hidden['id']}", headers=candidate)).status_code == 404
    searched = (await client.get(f"{API}/vacancies", params={"q": "react"}, headers=candidate)).json()
    assert [item["id"] for item in searched] == [frontend["id"]]

    applied = await client.post(
        f"{API}/vacancies/{backend['id']}/apply",
        json={"cover_note": "Готова к собеседованию"},
        headers=candidate,
    )

    assert applied.status_code == 201, applied.text
    assert applied.json()["status"] == "sent" and applied.json()["vacancy"]["applied"] is True
    unlock = await session.scalar(select(ContactUnlock))
    assert (unlock.candidate_id, unlock.source.value) == (cid, "application")
    again = await client.post(f"{API}/vacancies/{backend['id']}/apply", json={}, headers=candidate)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_applied"

    inbox = (await client.get(f"{API}/needs/{backend['id']}/applications", headers=employer)).json()
    assert len(inbox) == 1 and inbox[0]["contacts"]["telegram"] == "@anna"
    assert inbox[0]["match_score"] == listed[0]["match_score"]
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    assert card["contacts_unlocked"] is True

    application_id = inbox[0]["id"]
    assert (await client.post(f"{API}/applications/{application_id}/view", headers=employer)).json()[
        "status"
    ] == "viewed"
    accepted = await client.post(f"{API}/applications/{application_id}/accept", headers=employer)
    assert accepted.json()["status"] == "accepted"
    assert (
        await client.post(f"{API}/applications/{application_id}/reject", headers=employer)
    ).status_code == 409
    mine = (await client.get(f"{API}/candidates/me/applications", headers=candidate)).json()
    assert [(item["vacancy"]["id"], item["status"]) for item in mine] == [(backend["id"], "accepted")]


async def test_apply_requires_category(client, session):
    employer = await signup(client, "hr@bank.ru")
    vacancy = await publish(client, employer)
    newcomer = await signup(client, "new@example.com", role="candidate")

    response = await client.post(f"{API}/vacancies/{vacancy['id']}/apply", json={}, headers=newcomer)

    assert response.status_code == 409 and response.json()["error"]["code"] == "category_required"
    assert await session.scalar(select(ContactUnlock.candidate_id)) is None


async def test_applications_are_isolated(client, session):
    owner = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@shop.ru")
    anna, _ = await make_candidate(client, session, "anna@example.com")
    boris, _ = await make_candidate(client, session, "boris@example.com", first_name="Борис")
    vacancy = await publish(client, owner)
    await client.post(f"{API}/vacancies/{vacancy['id']}/apply", json={}, headers=anna)
    application_id = (await client.get(f"{API}/needs/{vacancy['id']}/applications", headers=owner)).json()[0][
        "id"
    ]

    assert (await client.get(f"{API}/needs/{vacancy['id']}/applications", headers=other)).status_code == 404
    for action in ("view", "accept", "reject"):
        response = await client.post(f"{API}/applications/{application_id}/{action}", headers=other)
        assert response.status_code == 404
    assert (await client.get(f"{API}/candidates/me/applications", headers=boris)).json() == []
    assert (await client.get(f"{API}/vacancies", headers=owner)).status_code == 403


async def test_application_survives_vacancy_new_version(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    vacancy = await publish(client, employer)
    await client.post(f"{API}/vacancies/{vacancy['id']}/apply", json={}, headers=candidate)

    newer = (
        await client.put(f"{API}/needs/{vacancy['id']}", json=NEED | {"salary_to": 330000}, headers=employer)
    ).json()

    listed = (await client.get(f"{API}/vacancies", headers=candidate)).json()
    assert [(item["id"], item["applied"]) for item in listed] == [(newer["id"], True)]
    again = await client.post(f"{API}/vacancies/{newer['id']}/apply", json={}, headers=candidate)
    assert again.status_code == 409
    assert len((await client.get(f"{API}/needs/{newer['id']}/applications", headers=employer)).json()) == 1
