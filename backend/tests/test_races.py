"""Регрессии ревью 09.10: гонки параллельных запросов и скрытый ФСП в поиске.

Пауза вставляется между проверкой условия и записью: без блокировки оба запроса проходят проверку.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.enums import AttemptStatus
from app.modules.auth import service as auth_service
from app.modules.auth.models import RefreshToken
from app.modules.candidates.models import Candidate
from app.modules.fsp import service as fsp_service
from app.modules.fsp.models import FspAchievement
from app.modules.matching import service as matching_service
from app.modules.needs import service as needs_service
from app.modules.testing import service as testing_service
from app.modules.testing.models import TestAttempt as Attempt
from tests.test_auth import refresh_with, register_body, sent_mail  # noqa: F401 — фикстура
from tests.test_fsp_oidc import REGISTRY
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup
from tests.test_testing_flow import onboard
from tests.test_testing_flow import signup as candidate_signup

PAUSE = 0.3


def paused(monkeypatch, module, name: str, *, before: bool = False) -> None:
    """Пауза до или после настоящей функции — так оба запроса успевают пройти проверку."""
    original = getattr(module, name)

    async def wrapper(*args, **kwargs):
        if before:
            await asyncio.sleep(PAUSE)
        result = await original(*args, **kwargs)
        if not before:
            await asyncio.sleep(PAUSE)
        return result

    monkeypatch.setattr(module, name, wrapper)


@pytest.mark.usefixtures("sent_mail")
async def test_same_refresh_token_cannot_be_exchanged_twice(client, session, monkeypatch):
    await client.post(f"{API}/auth/register", json=register_body("race@example.com"))
    token = client.cookies.get(get_settings().refresh_cookie_name)
    paused(monkeypatch, auth_service, "_issue_session", before=True)

    first, second = await asyncio.gather(refresh_with(client, token), refresh_with(client, token))

    assert sorted([first.status_code, second.status_code]) == [200, 401]
    rejected = first if first.status_code == 401 else second
    assert rejected.json()["error"]["code"] == "refresh_token_reused"
    active = await session.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.revoked_at.is_(None))
    )
    assert active == 0, "повтор отзывает и только что выданную сессию"


async def test_parallel_express_start_creates_one_attempt(client, session, monkeypatch):
    headers = await candidate_signup(client, "express-race@example.com")
    await onboard(client, headers)
    paused(monkeypatch, testing_service, "_check_express")
    body = {"specialization": "backend", "grade_target": "junior", "purpose": "express"}

    responses = await asyncio.gather(
        client.post(f"{API}/tests/attempts", json=body, headers=headers),
        client.post(f"{API}/tests/attempts", json=body, headers=headers),
    )

    assert sorted(r.status_code for r in responses) == [201, 409]
    assert next(r for r in responses if r.status_code == 409).json()["error"]["code"] == "attempt_in_progress"
    running = await session.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.status == AttemptStatus.in_progress)
    )
    assert running == 1


async def test_parallel_need_edits_do_not_fork_versions(client, session, monkeypatch):
    employer = await signup(client, "hr@bank.ru")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    paused(monkeypatch, needs_service, "_get_latest_own")

    responses = await asyncio.gather(
        client.put(f"{API}/needs/{need['id']}", json=NEED | {"title": "Правка 1"}, headers=employer),
        client.put(f"{API}/needs/{need['id']}", json=NEED | {"title": "Правка 2"}, headers=employer),
    )

    assert sorted(r.status_code for r in responses) == [200, 409]
    assert next(r for r in responses if r.status_code == 409).json()["error"]["code"] == "need_superseded"
    children = await session.scalar(
        select(func.count())
        .select_from(needs_service.HiringNeed)
        .where(needs_service.HiringNeed.parent_id == need["id"])
    )
    assert children == 1


async def test_one_fsp_id_cannot_be_linked_to_two_profiles_at_once(client, session, monkeypatch):
    async def registry(fsp_id: str):
        await asyncio.sleep(PAUSE)
        return REGISTRY.get(fsp_id)

    monkeypatch.setattr(fsp_service, "fetch_from_registry", registry)
    anna = await signup(client, "anna@example.com", role="candidate")
    boris = await signup(client, "boris@example.com", role="candidate")
    body = {"fsp_id": "FSP-2026-1002", "consent": True}

    responses = await asyncio.gather(
        client.post(f"{API}/candidates/me/fsp/link", json=body, headers=anna),
        client.post(f"{API}/candidates/me/fsp/link", json=body, headers=boris),
    )

    assert sorted(r.status_code for r in responses) == [200, 409]
    assert next(r for r in responses if r.status_code == 409).json()["error"]["code"] == "fsp_id_taken"
    owners = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.fsp_id == "FSP-2026-1002")
    )
    assert owners == 1


async def test_hidden_fsp_discipline_is_not_searchable(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    session.add(
        FspAchievement(
            candidate_id=cid,
            competition_id="cup-2026",
            competition_name="Кубок России",
            discipline="алгоритмы",
            level="national",
            format="team",
            held_on=datetime.now(UTC).date(),
            place=1,
            participants=120,
            percentile=0.99,
            strength=0.9,
        )
    )
    await session.flush()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()

    async def found(params: dict) -> bool:
        result = (await client.get(f"{API}/talent/search", params=params, headers=employer)).json()
        return cid in [item["id"] for item in result["items"]]

    assert await found({"fsp_discipline": "алгоритмы"})

    hidden = {"show_last_name": True, "show_fsp": False, "show_salary": True, "hidden_employer_ids": []}
    saved = await client.put(f"{API}/candidates/me/privacy", json=hidden, headers=candidate)
    assert saved.status_code == 200
    assert not await found({"fsp_discipline": "алгоритмы"})
    assert not await found({"fsp_discipline": "алгоритмы", "has_fsp": "false"})
