"""Общий демо-кандидат открыт любому посетителю: необратимые действия ему запрещены, остальное работает."""

from sqlalchemy import func, select

from app.modules.auth.models import User
from tests.test_needs import API, signup

PRIVACY = {"show_last_name": True, "show_fsp": True, "show_salary": True, "hidden_employer_ids": []}


async def demo_candidate(client) -> dict:
    response = await client.post(f"{API}/auth/demo-login", json={"persona": "candidate"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def refused(response) -> bool:
    return response.status_code == 403 and response.json()["error"]["code"] == "demo_account"


async def test_shared_demo_candidate_cannot_break_the_demo(client, session):
    headers = await demo_candidate(client)
    employer = await signup(client, "hr@bank.ru")
    employer_id = (await client.get(f"{API}/employers/me", headers=employer)).json()["id"]

    assert refused(await client.delete(f"{API}/candidates/me", headers=headers))
    hidden = {"search_status": "hidden"}
    assert refused(await client.put(f"{API}/candidates/me/search-status", json=hidden, headers=headers))
    hide_from = PRIVACY | {"hidden_employer_ids": [employer_id]}
    assert refused(await client.put(f"{API}/candidates/me/privacy", json=hide_from, headers=headers))
    assert refused(await client.delete(f"{API}/candidates/me/fsp", headers=headers))
    grant = {"kind": "profile_publication", "granted": True}
    assert (await client.put(f"{API}/candidates/me/consents", json=grant, headers=headers)).status_code == 200
    revoke = {"kind": "profile_publication", "granted": False}
    assert refused(await client.put(f"{API}/candidates/me/consents", json=revoke, headers=headers))

    # Обратимые настройки демо-кандидату доступны
    status = {"search_status": "open"}
    assert (await client.put(f"{API}/candidates/me/search-status", json=status, headers=headers)).is_success
    privacy = PRIVACY | {"show_salary": False}
    assert (await client.put(f"{API}/candidates/me/privacy", json=privacy, headers=headers)).is_success

    deleted = await session.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_not(None)))
    assert deleted == 0, "демо-аккаунт не удалён"


async def test_regular_candidate_still_can_hide_and_delete(client):
    headers = await signup(client, "anna@example.com", role="candidate")

    hidden = {"search_status": "hidden"}
    assert (await client.put(f"{API}/candidates/me/search-status", json=hidden, headers=headers)).is_success
    assert (await client.delete(f"{API}/candidates/me", headers=headers)).is_success
