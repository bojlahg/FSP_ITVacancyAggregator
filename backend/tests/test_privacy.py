"""Приватность, согласия и удаление аккаунта (§6.4, §8.2, §13)."""

from sqlalchemy import select

from app.modules.auth.models import AuditLog, User
from app.modules.candidates.models import Candidate
from app.modules.matching.models import CandidateSearchIndex
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, employer_of, signup


async def test_privacy_controls_what_employer_sees(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")

    default = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()["brief"]
    assert default["display_name"] == "Анна К." and default["salary_min"] == 260000

    updated = await client.put(
        f"{API}/candidates/me/privacy",
        json={"show_last_name": True, "show_fsp": True, "show_salary": False, "hidden_employer_ids": []},
        headers=candidate,
    )
    assert updated.status_code == 200, updated.text
    brief = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()["brief"]
    assert brief["display_name"] == "Анна Ковалёва" and brief["salary_min"] is None
    assert (await client.get(f"{API}/candidates/me", headers=candidate)).json()["privacy"][
        "show_salary"
    ] is False


async def test_hidden_company_loses_access(client, session):
    employer = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@shop.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    bank = await employer_of(session, "hr@bank.ru")

    await client.put(
        f"{API}/candidates/me/privacy",
        json={
            "show_last_name": False,
            "show_fsp": True,
            "show_salary": True,
            "hidden_employer_ids": [bank.id],
        },
        headers=candidate,
    )

    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 404
    assert (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).status_code == 404
    found = (await client.get(f"{API}/talent/search", headers=employer)).json()
    assert cid not in [item["id"] for item in found["items"]]
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=other)).status_code == 200


async def test_consents_history_and_publication_revoke(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")

    consents = {
        c["kind"]: c for c in (await client.get(f"{API}/candidates/me/consents", headers=candidate)).json()
    }
    assert consents["pd_processing"]["granted"] and consents["profile_publication"]["granted"]
    assert consents["fsp_import"]["granted"] is False and consents["fsp_import"]["granted_at"] is None

    revoked = await client.put(
        f"{API}/candidates/me/consents",
        json={"kind": "profile_publication", "granted": False},
        headers=candidate,
    )
    assert revoked.status_code == 200
    state = {c["kind"]: c for c in revoked.json()}["profile_publication"]
    assert state["granted"] is False and state["revoked_at"] is not None
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 404

    regranted = await client.put(
        f"{API}/candidates/me/consents",
        json={"kind": "profile_publication", "granted": True},
        headers=candidate,
    )
    assert {c["kind"]: c for c in regranted.json()}["profile_publication"]["granted"] is True
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 200
    actions = list(await session.scalars(select(AuditLog.action).where(AuditLog.object_type == "consent")))
    assert actions.count("consent.revoked") == 1 and actions.count("consent.granted") >= 1

    pd = await client.put(
        f"{API}/candidates/me/consents", json={"kind": "pd_processing", "granted": False}, headers=candidate
    )
    assert pd.status_code == 409


async def test_delete_account_anonymizes_and_hides(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()

    response = await client.delete(f"{API}/candidates/me", headers=candidate)

    assert response.status_code == 200
    session.expire_all()
    row = await session.get(Candidate, cid)
    user = await session.get(User, row.user_id)
    assert row.last_name is None and row.phone is None and row.telegram is None
    assert user.deleted_at is not None and user.email.endswith("@deleted.invalid")
    assert await session.get(CandidateSearchIndex, cid) is None
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 404
    statuses = [
        item["status"]
        for item in (await client.get(f"{API}/employers/me/invitations", headers=employer)).json()
    ]
    assert statuses == ["expired"] and sent["status"] == "sent"
    login = await client.post(
        f"{API}/auth/login", json={"email": "anna@example.com", "password": "password-123"}
    )
    assert login.status_code == 401


async def test_search_status_and_company_lookup(client, session):
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me", json={"company_name": "Демо Банк"}, headers=employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")

    hidden = await client.put(
        f"{API}/candidates/me/search-status", json={"search_status": "hidden"}, headers=candidate
    )
    assert hidden.status_code == 200 and hidden.json()["search_status"] == "hidden"
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 404
    await client.put(
        f"{API}/candidates/me/search-status", json={"search_status": "active"}, headers=candidate
    )
    assert (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).status_code == 200

    found = (
        await client.get(f"{API}/candidates/me/companies", params={"q": "банк"}, headers=candidate)
    ).json()
    assert [item["company_name"] for item in found] == ["Демо Банк"]
    by_id = await client.get(
        f"{API}/candidates/me/companies", params={"ids": [found[0]["id"]]}, headers=candidate
    )
    assert by_id.json() == found
