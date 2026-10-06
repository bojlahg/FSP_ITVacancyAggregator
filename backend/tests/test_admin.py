"""Сброс демо-данных: только DEMO_MODE и роль admin."""

from app.core.config import get_settings
from app.core.enums import Role
from app.core.schemas import MessageResponse
from app.modules.admin import service
from tests.conftest import bearer_for

API = "/api/v1"


async def test_reseed_requires_admin(client, session):
    for role in (Role.candidate, Role.employer):
        response = await client.post(f"{API}/admin/reseed", headers=await bearer_for(session, role))
        assert response.status_code == 403
    assert (await client.post(f"{API}/admin/reseed")).status_code == 401


async def test_reseed_hidden_without_demo_mode(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    response = await client.post(f"{API}/admin/reseed", headers=await bearer_for(session, Role.admin))
    assert response.status_code == 404


async def test_admin_runs_reseed(client, session, monkeypatch):
    async def fake() -> MessageResponse:
        return MessageResponse(message="Демо-данные пересозданы")

    monkeypatch.setattr(service, "reseed", fake)
    response = await client.post(f"{API}/admin/reseed", headers=await bearer_for(session, Role.admin))
    assert response.status_code == 200 and response.json()["message"] == "Демо-данные пересозданы"


async def test_reseed_waits_for_backup_and_stops_if_it_fails(tmp_path, monkeypatch, db):
    import asyncio

    import pytest

    from app.core.errors import AppError

    monkeypatch.setattr(get_settings(), "backup_requests_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "backup_request_timeout_seconds", 5)

    async def answer(suffix: str) -> None:
        for _ in range(50):
            if requests := list(tmp_path.glob("*.request")):
                requests[0].rename(requests[0].with_suffix(suffix))
                return
            await asyncio.sleep(0.1)

    started = []

    async def fake_exec(*args, **kwargs):
        started.append(args)
        raise RuntimeError("seed не должен запускаться")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    responder = asyncio.create_task(answer(".failed"))
    with pytest.raises(AppError) as failed:
        await service.reseed()
    await responder
    assert failed.value.code == "backup_failed" and not started
    assert list(tmp_path.iterdir()) == []

    responder = asyncio.create_task(answer(".ok"))
    with pytest.raises(RuntimeError):
        await service.reseed()  # бэкап готов — дальше запускается генератор
    await responder
    assert started
