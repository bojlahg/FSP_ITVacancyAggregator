"""Приглашения: цикл статусов, лимит, раскрытие контактов, изоляция сторон, отказы (§8.1, §8.5–8.6)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.enums import Grade
from app.modules.auth.models import AuditLog
from app.modules.candidates.models import Candidate
from app.modules.categories.models import CandidateCategory
from app.modules.invitations.models import ContactUnlock, Invitation
from app.modules.matching import service as matching_service
from tests.test_needs import API, NEED, candidate_id, signup

CONTACT = {"name": "Ольга, HR", "telegram": "@olga_hr"}


async def make_candidate(client, session, email: str, **profile) -> tuple[dict[str, str], int]:
    """Кандидат с действующей категорией Backend · Middle и строкой в индексе выдачи."""
    headers = await signup(client, email, role="candidate")
    cid = await candidate_id(session, email)
    values = {
        "first_name": "Анна",
        "last_name": "Ковалёва",
        "phone": "+7 900 000-00-00",
        "telegram": "@anna",
        "city": "Москва",
        "work_formats": ["remote"],
        "salary_min": 260000,
    } | profile
    await session.execute(update(Candidate).where(Candidate.id == cid).values(**values))
    session.add(
        CandidateCategory(
            candidate_id=cid,
            specialization="backend",
            grade=Grade.middle,
            theta=0.8,
            percentile=0.7,
            valid_until=datetime.now(UTC) + timedelta(days=365),
            is_current=True,
        )
    )
    await session.flush()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    return headers, cid


def invite(cid: int, **extra) -> dict:
    return {
        "candidate_id": cid,
        "title": "Backend в платёжную команду",
        "message": "Пишем платёжный шлюз на Python",
        "salary_from": 250000,
        "salary_to": 300000,
        "contact_method": CONTACT,
    } | extra


async def test_full_cycle_unlocks_contacts_only_after_accept(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()

    created = await client.post(f"{API}/invitations", json=invite(cid, need_id=need["id"]), headers=employer)

    assert created.status_code == 201, created.text
    sent = created.json()
    assert sent["status"] == "sent" and sent["contacts"] is None
    assert sent["candidate"]["display_name"] == "Анна К."
    assert sent["match_snapshot"]["lines"][0]["text"].startswith("Категория совпадает: Backend · Middle")
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    assert card["contacts"] is None and card["invitation_status"] == "sent"

    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    assert [item["id"] for item in inbox] == [sent["id"]]
    assert inbox[0]["contact_method"] is None, "контакт рекрутера — только после принятия"
    assert inbox[0]["why_you"] == sent["match_snapshot"]
    assert inbox[0]["salary_from"] == 250000 and inbox[0]["company"]["id"] > 0

    viewed = await client.post(f"{API}/invitations/{sent['id']}/view", headers=candidate)
    assert viewed.json()["status"] == "viewed" and viewed.json()["viewed_at"]
    accepted = await client.post(f"{API}/invitations/{sent['id']}/accept", headers=candidate)

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["contact_method"]["telegram"] == "@olga_hr"
    listed = (await client.get(f"{API}/employers/me/invitations", headers=employer)).json()
    assert listed[0]["status"] == "accepted"
    assert listed[0]["contacts"]["telegram"] == "@anna"
    card = (await client.get(f"{API}/talent/candidates/{cid}", headers=employer)).json()
    assert card["contacts_unlocked"] is True and card["contacts"]["phone"] == "+7 900 000-00-00"
    unlocks = list(await session.scalars(select(ContactUnlock)))
    assert [(u.candidate_id, u.source.value, u.source_id) for u in unlocks] == [
        (cid, "invitation", sent["id"])
    ]
    assert await session.scalar(select(AuditLog.id).where(AuditLog.action == "contacts.unlock"))

    again = await client.post(
        f"{API}/invitations/{sent['id']}/decline", json={"reason": "salary"}, headers=candidate
    )
    assert again.status_code == 409


async def test_candidates_see_only_their_invitations(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, anna = await make_candidate(client, session, "anna@example.com")
    boris, _ = await make_candidate(client, session, "boris@example.com", first_name="Борис")
    sent = (await client.post(f"{API}/invitations", json=invite(anna), headers=employer)).json()

    assert (await client.get(f"{API}/candidates/me/invitations", headers=boris)).json() == []
    for action in ("view", "accept"):
        response = await client.post(f"{API}/invitations/{sent['id']}/{action}", headers=boris)
        assert response.status_code == 404
    response = await client.post(
        f"{API}/invitations/{sent['id']}/decline", json={"reason": "stack"}, headers=boris
    )
    assert response.status_code == 404
    assert await session.scalar(select(ContactUnlock.candidate_id)) is None


async def test_employers_see_only_their_invitations(client, session):
    owner = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@shop.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")
    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=owner)).json()

    assert (await client.get(f"{API}/employers/me/invitations", headers=other)).json() == []
    assert (await client.post(f"{API}/invitations/{sent['id']}/withdraw", headers=other)).status_code == 404
    assert (await client.get(f"{API}/employers/me/decline-stats", headers=other)).json()["total_sent"] == 0
    candidate_inbox = await client.get(
        f"{API}/employers/me/invitations", headers=await signup(client, "c@x.ru", role="candidate")
    )
    assert candidate_inbox.status_code == 403
    foreign_need = (await client.post(f"{API}/needs", json=NEED, headers=owner)).json()
    response = await client.post(
        f"{API}/invitations", json=invite(cid, need_id=foreign_need["id"]), headers=other
    )
    assert response.status_code == 404


async def test_no_duplicate_active_invitation_and_withdraw(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    first = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()

    duplicate = await client.post(f"{API}/invitations", json=invite(cid), headers=employer)
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "already_invited"

    withdrawn = await client.post(f"{API}/invitations/{first['id']}/withdraw", headers=employer)
    assert withdrawn.json()["status"] == "withdrawn"
    assert (
        await client.post(f"{API}/invitations/{first['id']}/withdraw", headers=employer)
    ).status_code == 409
    assert (
        await client.post(f"{API}/invitations/{first['id']}/accept", headers=candidate)
    ).status_code == 409
    assert (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).status_code == 201


async def test_limit_counts_whole_need_version_chain(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_active_invites_per_need", 2)
    employer = await signup(client, "hr@bank.ru")
    ids = [(await make_candidate(client, session, f"c{i}@example.com"))[1] for i in range(4)]
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    for cid in ids[:2]:
        response = await client.post(
            f"{API}/invitations", json=invite(cid, need_id=need["id"]), headers=employer
        )
        assert response.status_code == 201
    newer = (
        await client.put(f"{API}/needs/{need['id']}", json=NEED | {"salary_to": 320000}, headers=employer)
    ).json()

    blocked = await client.post(
        f"{API}/invitations", json=invite(ids[2], need_id=newer["id"]), headers=employer
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "invitation_limit"

    # Ответ кандидата или истечение срока освобождают слот
    await session.execute(
        update(Invitation)
        .where(Invitation.candidate_id == ids[0])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()
    freed = await client.post(
        f"{API}/invitations", json=invite(ids[2], need_id=newer["id"]), headers=employer
    )
    assert freed.status_code == 201
    by_need = (
        await client.get(f"{API}/employers/me/invitations", params={"need_id": newer["id"]}, headers=employer)
    ).json()
    assert sorted(item["status"] for item in by_need) == ["expired", "sent", "sent"]
    stats = (await client.get(f"{API}/needs/{newer['id']}", headers=employer)).json()["stats"]
    assert stats["invitations_active"] == 2 and stats["invitations_total"] == 3


async def test_hidden_or_invisible_candidate_cannot_be_invited(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com", search_status="hidden")

    response = await client.post(f"{API}/invitations", json=invite(cid), headers=employer)

    assert response.status_code == 404
    assert (
        await client.post(f"{API}/invitations", json=invite(999_999), headers=employer)
    ).status_code == 404


async def test_salary_and_contact_method_are_required(client, session):
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")

    no_salary = invite(cid)
    del no_salary["salary_from"]
    assert (await client.post(f"{API}/invitations", json=no_salary, headers=employer)).status_code == 422
    reversed_range = invite(cid, salary_from=400000, salary_to=300000)
    assert (await client.post(f"{API}/invitations", json=reversed_range, headers=employer)).status_code == 422
    no_channel = invite(cid, contact_method={"name": "Ольга"})
    assert (await client.post(f"{API}/invitations", json=no_channel, headers=employer)).status_code == 422


async def test_decline_stats_hint(client, session):
    employer = await signup(client, "hr@bank.ru")
    reasons = ["salary", "salary", "stack"]
    for index, reason in enumerate(reasons):
        headers, cid = await make_candidate(client, session, f"c{index}@example.com")
        sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
        await client.post(f"{API}/invitations/{sent['id']}/decline", json={"reason": reason}, headers=headers)
    headers, cid = await make_candidate(client, session, "yes@example.com")
    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(f"{API}/invitations/{sent['id']}/accept", headers=headers)

    stats = (await client.get(f"{API}/employers/me/decline-stats", headers=employer)).json()

    assert stats["total_sent"] == 4 and stats["accepted"] == 1 and stats["declined"] == 3
    assert stats["acceptance_rate"] == 0.25
    assert stats["by_reason"]["salary"] == 2 and stats["top_reason"] == "salary"
    assert stats["hint"] == "2 из 3 отказов — зарплата"


async def test_salary_market_check_for_employer_and_candidate(client, session):
    """Вилка ниже рынка категории видна работодателю в покрытии вилки и кандидату в приглашении (§24)."""
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com", salary_min=260000)
    for index in range(5):
        await make_candidate(client, session, f"peer{index}@example.com", salary_min=300000 + index * 10000)
    low = NEED | {"salary_from": 120000, "salary_to": 150000}
    need = (await client.post(f"{API}/needs", json=low, headers=employer)).json()

    coverage = (await client.get(f"{API}/needs/{need['id']}/salary-coverage", headers=employer)).json()
    assert coverage["market"]["verdict"] == "below_market"
    assert coverage["market"]["message"].startswith("Вилка ниже рынка")

    sent = await client.post(
        f"{API}/invitations",
        json=invite(cid, need_id=need["id"], salary_from=120000, salary_to=150000),
        headers=employer,
    )
    assert sent.status_code == 201, sent.text
    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    assert inbox[0]["salary_market"]["verdict"] == "below_market"
    assert "вашей категории" in inbox[0]["salary_market"]["message"]


async def test_decline_comment_hides_contacts_without_unlock(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()

    comment = "Сейчас не ищу, пишите на anna.k@mail.ru или в @anna_dev"
    declined = await client.post(
        f"{API}/invitations/{sent['id']}/decline",
        json={"reason": "other", "comment": comment},
        headers=candidate,
    )

    assert declined.status_code == 200, declined.text
    listed = (await client.get(f"{API}/employers/me/invitations", headers=employer)).json()
    shown = listed[0]["decline_comment"]
    assert "Сейчас не ищу" in shown and "anna.k@mail.ru" not in shown and "@anna_dev" not in shown
    assert listed[0]["contacts"] is None
