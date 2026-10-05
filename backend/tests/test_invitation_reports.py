"""Признаки мошенничества в приглашении и жалобы кандидатов (§8.5)."""

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import Role
from app.core.text_rules import check_texts
from app.modules.auth.models import AuditLog, User
from app.modules.invitations.service import SCAM_RULES_FILE
from tests.conftest import bearer
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, signup

SCAM = "Обучение платное: стоимость курса 5000 ₽. Срочно напишите мне в телеграм, пришлите фото паспорта."


@pytest.mark.parametrize(
    ("text", "rules"),
    [
        (SCAM, ["payment", "messenger", "documents"]),
        ("Зарплата в USDT, пассивный доход", ["crypto"]),
        ("Пишите @hr_manager_x", ["messenger"]),
        ("Оплата обучения за счёт компании, ДМС, удалёнка", []),
        ("Вопросы — на почту hr@company.ru, оплачиваемая стажировка", []),
    ],
)
def test_scam_rules_golden(text, rules):
    assert sorted(issue.rule for issue in check_texts(SCAM_RULES_FILE, text)) == sorted(rules)


async def test_candidate_sees_warnings_and_reports_once(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    sent = (await client.post(f"{API}/invitations", json=invite(cid, message=SCAM), headers=employer)).json()

    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    assert {w["rule"] for w in inbox[0]["warnings"]} == {"payment", "messenger", "documents"}
    assert inbox[0]["report"] is None

    reported = await client.post(
        f"{API}/invitations/{sent['id']}/report",
        json={"reason": "scam", "comment": "просят деньги"},
        headers=candidate,
    )
    assert reported.status_code == 200, reported.text
    body = reported.json()
    assert body["report"]["reason"] == "scam" and body["report"]["status"] == "open"
    assert body["status"] == "sent", "жалоба не меняет статус приглашения"
    assert await session.scalar(select(AuditLog.id).where(AuditLog.action == "invitation.report"))

    again = await client.post(
        f"{API}/invitations/{sent['id']}/report", json={"reason": "spam"}, headers=candidate
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "report_exists"


async def test_report_isolation_and_admin_resolve(client, session):
    employer = await signup(client, "hr@bank.ru")
    anna_headers, anna = await make_candidate(client, session, "anna@example.com")
    boris, _ = await make_candidate(client, session, "boris@example.com", first_name="Борис")
    sent = (await client.post(f"{API}/invitations", json=invite(anna, message=SCAM), headers=employer)).json()

    foreign = await client.post(
        f"{API}/invitations/{sent['id']}/report", json={"reason": "scam"}, headers=boris
    )
    assert foreign.status_code == 404
    by_employer = await client.post(
        f"{API}/invitations/{sent['id']}/report", json={"reason": "scam"}, headers=employer
    )
    assert by_employer.status_code == 403

    own = await client.post(
        f"{API}/invitations/{sent['id']}/report", json={"reason": "scam"}, headers=anna_headers
    )
    assert own.status_code == 200

    for headers in (employer, boris):
        assert (await client.get(f"{API}/admin/invitation-reports", headers=headers)).status_code == 403
    admin_user = User(email="admin@example.com", password_hash="-", role=Role.admin)
    session.add(admin_user)
    await session.commit()
    admin = bearer(Role.admin, user_id=admin_user.id)
    reports = (await client.get(f"{API}/admin/invitation-reports?status=open", headers=admin)).json()
    assert len(reports) == 1 and reports[0]["invitation_id"] == sent["id"]
    assert {w["rule"] for w in reports[0]["warnings"]} == {"payment", "messenger", "documents"}

    resolved = await client.post(
        f"{API}/admin/invitation-reports/{reports[0]['id']}/resolve",
        json={"resolution": "Работодатель заблокирован"},
        headers=admin,
    )
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"
    assert (await client.get(f"{API}/admin/invitation-reports?status=open", headers=admin)).json() == []


async def test_scam_check_can_be_disabled(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "invitation_scam_check", False)
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    await client.post(f"{API}/invitations", json=invite(cid, message=SCAM), headers=employer)

    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()

    assert inbox[0]["warnings"] == []
