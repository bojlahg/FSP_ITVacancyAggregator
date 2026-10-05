"""Приватность, согласия и удаление аккаунта (§6.4, §8.2, §13)."""

from sqlalchemy import select

from app.core.enums import AttemptPurpose, Grade
from app.modules.applications.models import Application
from app.modules.auth.models import AuditLog, User
from app.modules.candidates.models import Candidate
from app.modules.invitations.models import Invitation, InvitationReport
from app.modules.matching.models import CandidateSearchIndex
from app.modules.tasks import service as tasks_service
from app.modules.tasks.models import TaskAssignment
from app.modules.testing.models import TestAttempt as Attempt
from app.modules.testing.models import TestAttemptItem as AttemptItem
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, NEED, employer_of, signup
from tests.test_tasks import APPROACH, candidate_with_category


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


async def test_deleted_account_old_jwt_is_rejected(client, session):
    """Ревью 06.10, №1: выданный до удаления access JWT больше ничего не может."""
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    assert (await client.delete(f"{API}/candidates/me", headers=candidate)).status_code == 200

    profile = await client.get(f"{API}/candidates/me", headers=candidate)
    publish = {"kind": "profile_publication", "granted": True}
    consent = await client.put(f"{API}/candidates/me/consents", json=publish, headers=candidate)
    status = await client.put(
        f"{API}/candidates/me/search-status", json={"search_status": "active"}, headers=candidate
    )
    for response in (profile, consent, status):
        assert response.status_code == 401, response.text
    session.expire_all()
    assert await session.get(CandidateSearchIndex, cid) is None


async def test_delete_account_erases_free_text_copies(client, session, monkeypatch):
    """Ревью 06.10, №3: email из свободного текста не переживает удаление аккаунта (§13)."""
    monkeypatch.setattr(tasks_service.llm, "is_enabled", lambda: False)
    email = "anna.k@mail.ru"
    employer = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@shop.ru")
    candidate, cid = await candidate_with_category(client, session, "anna@example.com")

    task_id = (await client.post(f"{API}/employer-tasks", json=APPROACH, headers=employer)).json()["id"]
    [offered] = (await client.get(f"{API}/candidates/me/tasks", headers=candidate)).json()
    submit = {"response": {"text": f"Ключ идемпотентности, пишите {email}"}}
    await client.post(f"{API}/tasks/assignments/{offered['id']}/submit", json=submit, headers=candidate)
    declined = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(
        f"{API}/invitations/{declined['id']}/decline",
        json={"reason": "salary", "comment": f"Мало, пишите {email}"},
        headers=candidate,
    )
    reported = (await client.post(f"{API}/invitations", json=invite(cid), headers=other)).json()
    await client.post(
        f"{API}/invitations/{reported['id']}/report",
        json={"reason": "scam", "comment": f"Мне ответили на {email}"},
        headers=candidate,
    )
    need_id = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()["id"]
    session.add(Application(need_id=need_id, candidate_id=cid, cover_note=f"Готова, {email}"))
    attempt = Attempt(
        candidate_id=cid,
        specialization="backend",
        grade_target=Grade.middle,
        purpose=AttemptPurpose.calibration,
        blueprint={},
        seed=1,
    )
    session.add(attempt)
    await session.flush()
    attempt_id = attempt.id
    session.add(
        AttemptItem(
            attempt_id=attempt_id,
            template_id="t",
            instance_seed=1,
            stage=1,
            position=0,
            payload={"kind": "open_approach"},
            answer_key={},
            response={"text": f"Подход: {email}"},
            score=0.5,
        )
    )
    await session.commit()

    assert (await client.delete(f"{API}/candidates/me", headers=candidate)).status_code == 200

    submissions = await client.get(f"{API}/employer-tasks/{task_id}/submissions", headers=employer)
    assert email not in submissions.text
    session.expire_all()
    assignment = await session.scalar(select(TaskAssignment).where(TaskAssignment.candidate_id == cid))
    item = await session.scalar(select(AttemptItem).where(AttemptItem.attempt_id == attempt_id))
    report = await session.scalar(select(InvitationReport))
    assert "text" not in assignment.response and "text" not in item.response and item.score == 0.5
    assert (await session.scalar(select(Application))).cover_note is None
    assert (await session.get(Invitation, declined["id"])).decline_comment is None
    assert report.comment is None and report.reason.value == "scam"


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


async def test_free_text_hides_contacts_until_unlock(client, session):
    """Инвариант contact_unlocks: контакты не утекают через «О себе» и описания опыта."""
    from app.modules.candidates.models import CandidateExperience

    employer = await signup(client, "hr@bank.ru")
    about = "Пишите на anna.k@mail.ru или в t.me/anna_k, +7 912 345-67-89"
    _, cid = await make_candidate(client, session, "anna@example.com", about=about)
    session.add(
        CandidateExperience(candidate_id=cid, company="Банк", position="Backend", description="tg @anna_k")
    )
    await session.commit()

    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    text = card["about"] + " ".join(item["description"] or "" for item in card["experience"])
    for secret in ("anna.k@mail.ru", "t.me/anna_k", "345-67-89", "@anna_k"):
        assert secret not in text
    assert "Пишите на" in card["about"]
