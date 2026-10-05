"""Отладочный раздел: без DEBUG_TOOLS его нет (404), с флагом — действия по ролям."""

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.categories.models import CandidateCategory
from tests.test_invitations import make_candidate
from tests.test_needs import API, signup

ENDPOINTS = [
    ("GET", "/debug/status"),
    ("POST", "/debug/reset-cooldowns"),
    ("POST", "/debug/reset-test"),
    ("POST", "/debug/test-email"),
    ("POST", "/debug/reseed"),
]


async def test_debug_section_absent_without_flag(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "debug_tools", False)
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    for method, path in ENDPOINTS:
        response = await client.request(method, f"{API}{path}", headers=candidate)
        assert response.status_code == 404, path


@pytest.fixture
def debug_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "debug_tools", True)


async def test_candidate_resets_test_and_cooldowns(client, session, debug_on):
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    status = (await client.get(f"{API}/debug/status", headers=candidate)).json()
    assert status == {"enabled": True, "actions": ["reset_cooldowns", "reset_test", "test_email"]}

    assert (await client.post(f"{API}/debug/reset-cooldowns", headers=candidate)).status_code == 200
    reset = await client.post(f"{API}/debug/reset-test", headers=candidate)
    assert reset.status_code == 200, reset.text
    session.expire_all()
    query = select(CandidateCategory).where(CandidateCategory.candidate_id == cid)
    assert await session.scalar(query) is None
    grade = (await client.get(f"{API}/candidates/me/grade-status", headers=candidate)).json()
    assert grade["current"] is None


async def test_employer_cannot_use_candidate_actions(client, session, debug_on):
    employer = await signup(client, "hr@bank.ru")
    assert (await client.get(f"{API}/debug/status", headers=employer)).json()["actions"] == ["test_email"]
    assert (await client.post(f"{API}/debug/reset-test", headers=employer)).status_code == 403
    assert (await client.post(f"{API}/debug/reseed", headers=employer)).status_code == 403


async def test_test_email_skips_service_domains(client, session, debug_on):
    reserved = await signup(client, "hr@bank.example.com")
    response = await client.post(f"{API}/debug/test-email", headers=reserved)
    assert response.status_code == 409 and response.json()["error"]["code"] == "address_skipped"
    real = await signup(client, "hr@bank.ru")
    response = await client.post(f"{API}/debug/test-email", headers=real)
    assert response.status_code == 200 and "hr@bank.ru" in response.json()["message"]
