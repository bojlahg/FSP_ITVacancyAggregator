"""Экспертная разметка пар «потребность — кандидат» (§12.2): доступ, «слепая» карточка, оценки и метрики."""

import pytest

from app.core.config import get_settings
from app.modules.expert import service as expert_service
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup

CODE = "expert-code-2026"


@pytest.fixture(autouse=True)
def invite_code(monkeypatch):
    monkeypatch.setattr(get_settings(), "expert_invite_code", CODE)


async def register_expert(client, email: str) -> dict[str, str]:
    response = await client.post(
        f"{API}/auth/register-expert",
        json={"email": email, "password": "password-123", "code": CODE, "consent_pd_processing": True},
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["role"] == "expert"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def setup_pool(client, session) -> dict[str, str]:
    employer = await signup(client, "hr@bank.ru")
    for index in range(7):
        await make_candidate(client, session, f"cand{index}@example.com", telegram=f"@cand{index}")
    assert (await client.post(f"{API}/needs", json=NEED, headers=employer)).status_code == 201
    return employer


async def test_registration_requires_invite_code(client, monkeypatch):
    body = {
        "email": "e@example.com",
        "password": "password-123",
        "code": "wrong",
        "consent_pd_processing": True,
    }
    assert (await client.post(f"{API}/auth/register-expert", json=body)).status_code == 403
    monkeypatch.setattr(get_settings(), "expert_invite_code", "")
    assert (await client.post(f"{API}/auth/register-expert", json=body | {"code": CODE})).status_code == 404


async def test_only_experts_label_and_cards_are_blind(client, session):
    employer = await setup_pool(client, session)
    expert = await register_expert(client, "expert@example.com")
    assert (await client.get(f"{API}/expert/next", headers=employer)).status_code == 403
    assert (await client.get(f"{API}/expert/summary", headers=employer)).status_code == 403

    task = (await client.get(f"{API}/expert/next", headers=expert)).json()
    total = task["progress"]["total"]
    assert task["progress"]["done"] == 0 and 6 <= total <= 7  # объединение топ-6 двух ранжирований
    assert task["need"]["category"] == "Backend · Middle"
    card = task["candidate"]
    assert card["match"] is None and card["contacts"] is None and card["contacts_unlocked"] is False
    assert card["invitation_status"] is None
    assert "@cand" not in str(card), "контакты не попадают в карточку для эксперта"
    assert "score" not in str(task["need"])

    assert (
        await client.post(f"{API}/expert/pairs/{task['pair_id']}/label", json={"label": 4}, headers=expert)
    ).status_code == 422
    assert (
        await client.post(f"{API}/expert/pairs/999999/label", json={"label": 1}, headers=expert)
    ).status_code == 404
    first = await client.post(
        f"{API}/expert/pairs/{task['pair_id']}/label", json={"label": 2}, headers=expert
    )
    assert first.json() == {"done": 1, "total": total}
    again = await client.post(
        f"{API}/expert/pairs/{task['pair_id']}/label", json={"label": 3}, headers=expert
    )
    assert again.json() == {"done": 1, "total": total}, "повторная оценка заменяет прежнюю"
    following = (await client.get(f"{API}/expert/next", headers=expert)).json()
    assert following["pair_id"] != task["pair_id"]


async def test_summary_metrics_on_expert_labels(client, session):
    await setup_pool(client, session)
    alice = await register_expert(client, "alice@example.com")
    bob = await register_expert(client, "bob@example.com")
    pairs = {}
    while (task := (await client.get(f"{API}/expert/next", headers=alice)).json())["pair_id"] is not None:
        pairs[task["pair_id"]] = task
        await client.post(f"{API}/expert/pairs/{task['pair_id']}/label", json={"label": 3}, headers=alice)
        await client.post(f"{API}/expert/pairs/{task['pair_id']}/label", json={"label": 3}, headers=bob)

    summary = (await client.get(f"{API}/expert/summary", headers=alice)).json()
    assert summary["raters"] == 2 and summary["pairs_labeled"] == summary["pairs_total"] == len(pairs)
    ours = summary["rankers"][0]
    assert ours["needs"] == 1 and ours["precision_at_5"] == 1.0
    assert summary["agreement_pairs"] == len(pairs) and summary["exact_agreement"] == 1.0


def test_weighted_kappa_golden():
    assert expert_service._weighted_kappa([(3, 3), (0, 0), (2, 2), (1, 1)]) == 1.0
    assert expert_service._weighted_kappa([(3, 0), (0, 3), (3, 0), (0, 3)]) < 0
    assert expert_service._weighted_kappa([(1, 1)]) is None
