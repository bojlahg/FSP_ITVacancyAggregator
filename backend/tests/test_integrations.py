"""Интеграция с ATS (docs/anti-fraud-ats.md §2): API-ключи, подписанные webhook'и, доступ и повторы."""

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.integrations import service as integrations_service
from app.modules.integrations.models import EmployerApiKey, WebhookDelivery
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, NEED, signup

HOOK = "https://ats.example.com/itscout"


@pytest.fixture
def sent(monkeypatch):
    """Подмена транспорта: запоминаем запросы, ответ задаёт тест."""
    calls: list[dict] = []
    state = {"status": 200}

    async def fake_post(url: str, headers: dict[str, str], body: bytes) -> int:
        calls.append({"url": url, "headers": headers, "body": body})
        return state["status"]

    async def public_url(url: str) -> None:
        return None

    monkeypatch.setattr(integrations_service, "post_webhook", fake_post)
    monkeypatch.setattr(integrations_service, "check_url", public_url)
    return calls, state


async def test_api_key_gives_employer_api_but_not_key_management(client, session):
    employer = await signup(client, "hr@bank.ru")
    created = await client.post(f"{API}/employers/me/api-keys", json={"name": "Huntflow"}, headers=employer)
    assert created.status_code == 201, created.text
    key = created.json()["key"]
    assert key.startswith("itsk_") and created.json()["prefix"] in key
    stored = await session.scalar(select(EmployerApiKey))
    assert stored.key_hash != key and len(stored.key_hash) == 64, "в БД только хеш"

    ats = {"X-API-Key": key}
    assert (await client.post(f"{API}/needs", json=NEED, headers=ats)).status_code == 201
    assert len((await client.get(f"{API}/needs", headers=employer)).json()) == 1
    assert (await client.get(f"{API}/employers/me/api-keys", headers=ats)).status_code == 401
    listed = (await client.get(f"{API}/employers/me/api-keys", headers=employer)).json()
    assert "key" not in listed[0] and listed[0]["last_used_at"] is not None

    assert (await client.get(f"{API}/needs", headers={"X-API-Key": key + "x"})).status_code == 401
    assert (await client.get(f"{API}/needs", headers={"X-API-Key": "garbage"})).status_code == 401
    other = await signup(client, "hr@other.ru")
    key_id = listed[0]["id"]
    assert (await client.delete(f"{API}/employers/me/api-keys/{key_id}", headers=other)).status_code == 404
    assert (await client.delete(f"{API}/employers/me/api-keys/{key_id}", headers=employer)).status_code == 204
    assert (await client.get(f"{API}/needs", headers=ats)).status_code == 401, "отозванный ключ не работает"


async def test_candidate_cannot_use_integrations(client, db):
    candidate = await signup(client, "anna@example.com", role="candidate")
    assert (await client.get(f"{API}/employers/me/api-keys", headers=candidate)).status_code == 403
    response = await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=candidate)
    assert response.status_code == 403


async def test_api_key_limit(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_keys_per_employer", 1)
    employer = await signup(client, "hr@bank.ru")
    first = await client.post(f"{API}/employers/me/api-keys", json={"name": "a"}, headers=employer)
    assert first.status_code == 201
    second = await client.post(f"{API}/employers/me/api-keys", json={"name": "b"}, headers=employer)
    assert second.status_code == 409 and second.json()["error"]["code"] == "api_key_limit"


async def test_webhook_url_must_be_public_https(client, db):
    employer = await signup(client, "hr@bank.ru")
    for url in ["http://ats.example.com/hook", "https://127.0.0.1/hook", "https://10.0.0.5/x", "ftp://a.b/c"]:
        response = await client.put(f"{API}/employers/me/webhook", json={"url": url}, headers=employer)
        assert response.status_code == 422, url
        assert response.json()["error"]["code"] == "invalid_webhook_url"
    assert (await client.get(f"{API}/employers/me/webhook", headers=employer)).json() is None


async def test_accept_sends_signed_webhook_with_contacts(client, session, sent):
    calls, _ = sent
    employer = await signup(client, "hr@bank.ru")
    hook = (await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)).json()
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    invitation = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    assert calls == [], "отправка приглашения — не событие для ATS"

    await client.post(f"{API}/invitations/{invitation['id']}/accept", headers=candidate)

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == HOOK and call["headers"]["X-ITScout-Event"] == "invitation.accepted"
    header = call["headers"]["X-ITScout-Signature"]
    timestamp, signature = (part.split("=", 1)[1] for part in header.split(","))
    expected = hmac.new(hook["secret"].encode(), f"{timestamp}.".encode() + call["body"], hashlib.sha256)
    assert hmac.compare_digest(signature, expected.hexdigest())
    body = json.loads(call["body"])
    assert body["event"] == "invitation.accepted" and body["data"]["id"] == invitation["id"]
    assert body["data"]["contacts"]["telegram"] == "@anna", "после принятия контакты раскрыты"
    deliveries = (await client.get(f"{API}/employers/me/webhook/deliveries", headers=employer)).json()
    assert deliveries[0]["status"] == "delivered" and deliveries[0]["attempts"] == 1


async def test_declined_webhook_has_no_contacts(client, session, sent):
    calls, _ = sent
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    invitation = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(
        f"{API}/invitations/{invitation['id']}/decline", json={"reason": "salary"}, headers=candidate
    )
    body = json.loads(calls[0]["body"])
    assert body["event"] == "invitation.declined" and body["data"]["contacts"] is None
    assert "@anna" not in calls[0]["body"].decode()


async def test_failed_delivery_is_retried_then_marked_failed(client, session, sent, monkeypatch):
    calls, state = sent
    monkeypatch.setattr(get_settings(), "webhook_retry_delays_seconds", [0])
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)
    state["status"] = 500
    ping = await client.post(f"{API}/employers/me/webhook/test", headers=employer)
    assert ping.status_code == 202
    first = await session.get(WebhookDelivery, ping.json()["id"])
    await session.refresh(first)
    assert first.status == "pending" and first.attempts == 1 and first.last_error == "HTTP 500"

    await integrations_service.deliver_pending()
    await session.refresh(first)
    assert first.status == "failed" and first.attempts == 2

    state["status"] = 204
    retry = await client.post(f"{API}/employers/me/webhook/deliveries/{first.id}/retry", headers=employer)
    assert retry.status_code == 202
    await session.refresh(first)
    assert first.status == "delivered" and len(calls) == 3
    again = await client.post(f"{API}/employers/me/webhook/deliveries/{first.id}/retry", headers=employer)
    assert again.status_code == 409


async def test_deliveries_are_isolated_between_employers(client, session, sent):
    employer = await signup(client, "hr@bank.ru")
    other = await signup(client, "hr@other.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)
    ping = (await client.post(f"{API}/employers/me/webhook/test", headers=employer)).json()
    assert (await client.get(f"{API}/employers/me/webhook/deliveries", headers=other)).json() == []
    retry = await client.post(f"{API}/employers/me/webhook/deliveries/{ping['id']}/retry", headers=other)
    assert retry.status_code == 404
    assert (await client.post(f"{API}/employers/me/webhook/test", headers=other)).status_code == 404


async def test_disabled_webhook_queues_nothing(client, session, sent):
    calls, _ = sent
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK, "enabled": False}, headers=employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    invitation = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(f"{API}/invitations/{invitation['id']}/accept", headers=candidate)
    assert calls == [] and await session.scalar(select(WebhookDelivery)) is None


def test_signature_golden():
    assert integrations_service.sign("secret", 1700000000, b'{"a":1}') == (
        "t=1700000000,v1=" + hmac.new(b"secret", b'1700000000.{"a":1}', hashlib.sha256).hexdigest()
    )


async def test_post_webhook_has_total_timeout(monkeypatch):
    """Приёмник, отдающий ответ по байту, не держит доставку: тайм-аут на весь вызов, а не на чтение."""
    import asyncio

    monkeypatch.setattr(get_settings(), "webhook_timeout_seconds", 0.2)

    class HangingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            await asyncio.sleep(10)
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(integrations_service.httpx, "AsyncClient", HangingClient)
    started = asyncio.get_running_loop().time()
    with pytest.raises(TimeoutError):
        await integrations_service.post_webhook("https://ats.example.com", {}, b"{}")
    assert asyncio.get_running_loop().time() - started < 2


async def test_manual_sends_are_rate_limited(client, session, sent, monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_manual_per_hour", 2)
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)
    codes = [
        (await client.post(f"{API}/employers/me/webhook/test", headers=employer)).status_code
        for _ in range(3)
    ]
    assert codes == [202, 202, 429]


async def test_demo_employer_cannot_connect_ats(client, session):
    demo = await signup(client, get_settings().demo_employer_email)
    key = await client.post(f"{API}/employers/me/api-keys", json={"name": "x"}, headers=demo)
    assert key.status_code == 403 and key.json()["error"]["code"] == "demo_account"
    hook = await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=demo)
    assert hook.status_code == 403


async def test_account_deletion_removes_webhook_payloads(client, session, sent):
    employer = await signup(client, "hr@bank.ru")
    await client.put(f"{API}/employers/me/webhook", json={"url": HOOK}, headers=employer)
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    invitation = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(f"{API}/invitations/{invitation['id']}/accept", headers=candidate)
    assert await session.scalar(select(WebhookDelivery)) is not None
    deleted = await client.request(
        "DELETE", f"{API}/candidates/me", headers=candidate, json={"confirm": True}
    )
    assert deleted.status_code in (200, 204), deleted.text
    session.expire_all()
    assert await session.scalar(select(WebhookDelivery)) is None, "контакты удалённого кандидата не остаются"
