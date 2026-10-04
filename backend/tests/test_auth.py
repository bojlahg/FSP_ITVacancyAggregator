import re

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.mail import Mail
from app.modules.auth import router as auth_router
from app.modules.auth.models import AuditLog, Consent, RefreshToken, User
from app.modules.candidates.models import Candidate
from app.modules.employers.models import Employer

API = "/api/v1"
PASSWORD = "correct-horse-1"


@pytest.fixture
def sent_mail(monkeypatch) -> list[Mail]:
    sent: list[Mail] = []

    async def capture(mail: Mail) -> None:
        sent.append(mail)

    monkeypatch.setattr(auth_router, "send_safely", capture)
    return sent


async def refresh_with(client, token: str):
    client.cookies.clear()
    client.cookies.set(get_settings().refresh_cookie_name, token)
    return await client.post(f"{API}/auth/refresh")


def register_body(email: str = "Anna@Example.com", role: str = "candidate", **overrides) -> dict:
    body = {
        "email": email,
        "password": PASSWORD,
        "role": role,
        "consent_pd_processing": True,
        "consent_profile_publication": True,
    }
    return body | overrides


async def test_register_candidate_creates_profile_consents_and_session(client, session, sent_mail):
    response = await client.post(f"{API}/auth/register", json=register_body())

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "anna@example.com"
    assert body["user"]["role"] == "candidate"
    assert body["user"]["email_verified"] is False
    assert get_settings().refresh_cookie_name in response.cookies
    user_id = body["user"]["id"]
    candidates = select(func.count()).select_from(Candidate).where(Candidate.user_id == user_id)
    assert await session.scalar(candidates) == 1
    kinds = set(await session.scalars(select(Consent.kind).where(Consent.user_id == user_id)))
    assert {kind.value for kind in kinds} == {"pd_processing", "profile_publication"}
    assert await session.scalar(select(func.count()).select_from(AuditLog)) == 2
    assert len(sent_mail) == 1 and "verify-email?token=" in sent_mail[0].text


async def test_register_employer_creates_company_profile(client, session, sent_mail):
    response = await client.post(f"{API}/auth/register", json=register_body("hr@bank.ru", role="employer"))

    assert response.status_code == 201
    user_id = response.json()["user"]["id"]
    employers = select(func.count()).select_from(Employer).where(Employer.user_id == user_id)
    assert await session.scalar(employers) == 1
    kinds = list(await session.scalars(select(Consent.kind).where(Consent.user_id == user_id)))
    assert [kind.value for kind in kinds] == ["pd_processing"]


async def test_register_requires_pd_consent(client, db, sent_mail):
    response = await client.post(f"{API}/auth/register", json=register_body(consent_pd_processing=False))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "consent_required"


async def test_register_duplicate_email_is_case_insensitive(client, db, sent_mail):
    await client.post(f"{API}/auth/register", json=register_body("dup@example.com"))
    response = await client.post(f"{API}/auth/register", json=register_body("DUP@example.com"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_login_and_me(client, db, sent_mail):
    await client.post(f"{API}/auth/register", json=register_body("me@example.com"))

    wrong = await client.post(f"{API}/auth/login", json={"email": "me@example.com", "password": "nope-nope"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"

    ok = await client.post(f"{API}/auth/login", json={"email": "ME@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    me = await client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


async def test_refresh_rotates_token_and_detects_reuse(client, session, sent_mail):
    await client.post(f"{API}/auth/register", json=register_body("rot@example.com"))
    cookie_name = get_settings().refresh_cookie_name
    first_cookie = client.cookies.get(cookie_name)

    rotated = await client.post(f"{API}/auth/refresh")
    assert rotated.status_code == 200
    second_cookie = client.cookies.get(cookie_name)
    assert second_cookie and second_cookie != first_cookie

    # Повторное использование старого токена отзывает все сессии пользователя
    reused = await refresh_with(client, first_cookie)
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_token_reused"

    after = await refresh_with(client, second_cookie)
    assert after.status_code == 401
    active = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
    )
    assert active == 0


async def test_refresh_without_cookie_is_401(client, db):
    response = await client.post(f"{API}/auth/refresh")
    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client, db, sent_mail):
    await client.post(f"{API}/auth/register", json=register_body("out@example.com"))
    cookie_name = get_settings().refresh_cookie_name
    cookie = client.cookies.get(cookie_name)

    assert (await client.post(f"{API}/auth/logout")).status_code == 200
    response = await refresh_with(client, cookie)
    assert response.status_code == 401


async def test_verify_email_once(client, session, sent_mail):
    registered = await client.post(f"{API}/auth/register", json=register_body("verify@example.com"))
    token = re.search(r"token=([\w-]+)", sent_mail[0].text).group(1)

    assert (await client.post(f"{API}/auth/verify-email", json={"token": token})).status_code == 200
    user = await session.get(User, registered.json()["user"]["id"])
    assert user.email_verified_at is not None

    again = await client.post(f"{API}/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"


async def test_resend_verification_sends_new_mail(client, db, sent_mail):
    registered = await client.post(f"{API}/auth/register", json=register_body("resend@example.com"))
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    response = await client.post(f"{API}/auth/resend-verification", headers=headers)
    assert response.status_code == 200
    assert len(sent_mail) == 2


async def test_demo_login_reuses_same_account(client, db):
    first = await client.post(f"{API}/auth/demo-login", json={"persona": "employer"})
    second = await client.post(f"{API}/auth/demo-login", json={"persona": "employer"})

    assert first.status_code == 200
    assert first.json()["user"]["role"] == "employer"
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


async def test_demo_login_hidden_outside_demo_mode(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    response = await client.post(f"{API}/auth/demo-login", json={"persona": "candidate"})
    assert response.status_code == 404


async def test_login_is_rate_limited(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_rate_limit", 3)
    body = {"email": "nobody@example.com", "password": "whatever-1"}
    statuses = [(await client.post(f"{API}/auth/login", json=body)).status_code for _ in range(4)]
    assert statuses == [401, 401, 401, 429]
