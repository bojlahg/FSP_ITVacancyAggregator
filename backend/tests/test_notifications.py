"""Письма о событиях подбора (§8.9): адресат, тема, отписка, служебные адреса, сбой почты."""

import logging

import pytest

from app.core import mail as mail_module
from app.core.config import get_settings
from app.core.mail import Mail, is_skipped_address
from tests.test_applications import publish
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, signup

EMPLOYER = "hr@bank.ru"
CANDIDATE = "anna@mail.ru"


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[Mail] = []

    async def send(self, mail: Mail) -> None:
        self.sent.append(mail)


class BrokenSender:
    async def send(self, mail: Mail) -> None:
        raise ConnectionRefusedError("smtp down")


@pytest.fixture
def outbox(monkeypatch) -> list[Mail]:
    sender = FakeSender()
    monkeypatch.setattr(mail_module, "get_email_sender", lambda: sender)
    return sender.sent


async def setup_pair(client, session, outbox: list[Mail]) -> tuple[dict, dict, int]:
    employer = await signup(client, EMPLOYER)
    await client.put(f"{API}/employers/me", json={"company_name": "Банк Точка"}, headers=employer)
    candidate, cid = await make_candidate(client, session, CANDIDATE)
    outbox.clear()  # письма подтверждения почты после регистрации
    return employer, candidate, cid


async def test_invitation_mails_go_to_both_sides_without_contacts(client, session, outbox):
    employer, candidate, cid = await setup_pair(client, session, outbox)

    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()

    assert [m.to for m in outbox] == [CANDIDATE]
    received = outbox[0]
    assert received.subject == "ITScout: приглашение от Банк Точка"
    assert "Backend в платёжную команду" in received.text and "250 000 – 300 000 ₽" in received.text
    assert "/candidate/invitations" in received.text and "/candidate/settings" in received.text
    assert "Отключить уведомления можно в настройках" in received.text
    assert "Банк Точка" in received.html

    outbox.clear()
    accepted = await client.post(f"{API}/invitations/{sent['id']}/accept", headers=candidate)
    assert accepted.status_code == 200

    assert [m.to for m in outbox] == [EMPLOYER]
    mail = outbox[0]
    assert mail.subject == "ITScout: Анна К. принял(а) приглашение"
    assert f"/employer/candidates/{cid}" in mail.text and "/employer/company" in mail.text
    for secret in ("+7 900 000-00-00", "@anna", CANDIDATE, "Ковалёва"):
        assert secret not in mail.text and secret not in mail.html


async def test_decline_and_withdraw_mails(client, session, outbox):
    employer, candidate, cid = await setup_pair(client, session, outbox)
    first = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    outbox.clear()

    await client.post(
        f"{API}/invitations/{first['id']}/decline",
        json={"reason": "salary", "comment": "Пишите на anna@mail.ru"},
        headers=candidate,
    )

    assert [m.to for m in outbox] == [EMPLOYER]
    assert "отклонил(а)" in outbox[0].subject and "Причина: зарплата" in outbox[0].text
    assert CANDIDATE not in outbox[0].text, "комментарий кандидата в письмо не попадает"

    second = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    outbox.clear()
    withdrawn = await client.post(f"{API}/invitations/{second['id']}/withdraw", headers=employer)

    assert withdrawn.status_code == 200
    assert [m.to for m in outbox] == [CANDIDATE]
    assert outbox[0].subject == "ITScout: Банк Точка отозвала приглашение"


async def test_application_mail_to_employer(client, session, outbox):
    employer = await signup(client, EMPLOYER)
    candidate, cid = await make_candidate(client, session, CANDIDATE)
    vacancy = await publish(client, employer, title="Backend")
    outbox.clear()

    applied = await client.post(f"{API}/vacancies/{vacancy['id']}/apply", json={}, headers=candidate)

    assert applied.status_code == 201, applied.text
    assert [m.to for m in outbox] == [EMPLOYER]
    mail = outbox[0]
    assert mail.subject == "ITScout: новый отклик на «Backend»"
    assert f"/employer/candidates/{cid}?need={vacancy['id']}" in mail.text
    assert "+7 900 000-00-00" not in mail.text and CANDIDATE not in mail.text


async def test_user_opt_out_is_respected(client, session, outbox):
    employer, candidate, cid = await setup_pair(client, session, outbox)

    me = await client.put(f"{API}/me/notifications", json={"email_notifications": False}, headers=candidate)

    assert me.status_code == 200 and me.json()["email_notifications"] is False
    assert (await client.get(f"{API}/me", headers=candidate)).json()["email_notifications"] is False
    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    assert outbox == []
    await client.post(f"{API}/invitations/{sent['id']}/accept", headers=candidate)
    assert [m.to for m in outbox] == [EMPLOYER], "выключил только кандидат"


async def test_global_toggle_disables_all(client, session, outbox, monkeypatch):
    employer, candidate, cid = await setup_pair(client, session, outbox)
    monkeypatch.setattr(get_settings(), "notifications_enabled", False)

    sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(f"{API}/invitations/{sent['id']}/accept", headers=candidate)

    assert outbox == []


async def test_reserved_and_demo_addresses_are_skipped(client, session, outbox):
    employer = await signup(client, "hr@bank.example")
    _, cid = await make_candidate(client, session, "anna@example.com")
    outbox.clear()

    created = await client.post(f"{API}/invitations", json=invite(cid), headers=employer)

    assert created.status_code == 201 and outbox == []
    settings = get_settings()
    for address in (
        "x@example.org",
        "hr@acme.example",
        "candidate0001@demo.itscout.ru",
        settings.demo_candidate_email,
        settings.demo_employer_email.upper(),
        "e2e-candidate@itscout.ru",
    ):
        assert is_skipped_address(address), address
    assert not is_skipped_address("anna@mail.ru")
    assert not is_skipped_address("team@itscout.ru")


async def test_sender_failure_does_not_fail_request(client, session, outbox, monkeypatch, caplog):
    employer, candidate, cid = await setup_pair(client, session, outbox)
    monkeypatch.setattr(mail_module, "get_email_sender", lambda: BrokenSender())

    with caplog.at_level(logging.ERROR, logger="itscout.mail"):
        created = await client.post(f"{API}/invitations", json=invite(cid), headers=employer)

    assert created.status_code == 201, created.text
    assert "failed to send email to anna@mail.ru" in caplog.text
    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    assert [item["id"] for item in inbox] == [created.json()["id"]]
