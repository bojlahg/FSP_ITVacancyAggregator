"""Сброс демо-данных: только DEMO_MODE и роль admin."""

from app.core.config import get_settings
from app.core.enums import Role
from app.core.schemas import MessageResponse
from app.modules.admin import service
from tests.conftest import bearer

API = "/api/v1"


async def test_reseed_requires_admin(client, db):
    for role in (Role.candidate, Role.employer):
        response = await client.post(f"{API}/admin/reseed", headers=bearer(role))
        assert response.status_code == 403
    assert (await client.post(f"{API}/admin/reseed")).status_code == 401


async def test_reseed_hidden_without_demo_mode(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    response = await client.post(f"{API}/admin/reseed", headers=bearer(Role.admin))
    assert response.status_code == 404


async def test_admin_runs_reseed(client, db, monkeypatch):
    async def fake() -> MessageResponse:
        return MessageResponse(message="Демо-данные пересозданы")

    monkeypatch.setattr(service, "reseed", fake)
    response = await client.post(f"{API}/admin/reseed", headers=bearer(Role.admin))
    assert response.status_code == 200 and response.json()["message"] == "Демо-данные пересозданы"
