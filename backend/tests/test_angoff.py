"""Modified Angoff (§10.4, §12.4): решатель порога, доступ, upsert оценок, отсутствие ключей, сводка."""

import math
from statistics import mean, stdev

import pytest

from app.core.enums import Role
from app.modules.expert.angoff_service import _items, template_set
from app.modules.testing.engine.angoff import THETA_MAX, THETA_MIN, AngoffItem, angoff_cut, tcc
from tests.conftest import bearer
from tests.test_expert import invite_code, register_expert  # noqa: F401
from tests.test_explainer import KEY_FIELDS, _keys
from tests.test_needs import API, signup

ANGOFF = f"{API}/expert/angoff"


# ——— решатель: golden-кейсы ———


def test_cut_single_2pl_item_at_half_is_b():
    assert angoff_cut([AngoffItem(1.0, 0.7, 0.0)], [0.5]).theta == pytest.approx(0.7, abs=1e-5)


def test_cut_single_2pl_item_inverts_logistic():
    # P = 1/(1+e^{−1.5·(1−0.4)}) = σ(0.9) ≈ 0.710950 → θ = 1.0
    p = 1 / (1 + math.exp(-0.9))
    assert angoff_cut([AngoffItem(1.5, 0.4, 0.0)], [p]).theta == pytest.approx(1.0, abs=1e-5)


def test_cut_3pl_uses_guessing():
    # c = 0.25: P(b) = 0.25 + 0.75·0.5 = 0.625
    cut = angoff_cut([AngoffItem(1.0, -0.3, 0.25)], [0.625])
    assert cut.theta == pytest.approx(-0.3, abs=1e-5) and not cut.clamped


def test_cut_symmetric_pair_is_zero():
    items = [AngoffItem(1.2, -1.0, 0.0), AngoffItem(1.2, 1.0, 0.0)]
    assert angoff_cut(items, [0.9, 0.1]).theta == pytest.approx(0.0, abs=1e-5)


def test_cut_matches_tcc_and_expected():
    items = [AngoffItem(0.8, -1.0, 0.25), AngoffItem(1.4, 0.2, 0.0), AngoffItem(2.0, 1.1, 1 / 3)]
    ratings = [0.85, 0.55, 0.4]
    cut = angoff_cut(items, ratings)
    assert cut.expected == pytest.approx(1.8)
    assert tcc(cut.theta, items) == pytest.approx(1.8, abs=1e-5)


def test_cut_is_monotone_in_ratings():
    items = [AngoffItem(1.0, b, 0.0) for b in (-1.0, 0.0, 1.0)]
    cuts = [angoff_cut(items, [p] * 3).theta for p in (0.2, 0.4, 0.6, 0.8)]
    assert cuts == sorted(cuts) and len(set(cuts)) == 4


def test_cut_clamps_outside_tcc_range():
    item = [AngoffItem(1.0, 0.0, 0.25)]
    below_guessing = angoff_cut(item, [0.2])  # Σp < Σc
    assert below_guessing.theta == THETA_MIN and below_guessing.clamped
    all_correct = angoff_cut(item, [1.0])  # Σp = n
    assert all_correct.theta == THETA_MAX and all_correct.clamped


def test_cut_rejects_bad_input():
    with pytest.raises(ValueError):
        angoff_cut([AngoffItem(1.0, 0.0, 0.0)], [0.5, 0.5])
    with pytest.raises(ValueError):
        angoff_cut([AngoffItem(1.0, 0.0, 0.0)], [1.2])
    with pytest.raises(ValueError):
        angoff_cut([], [])


def test_template_set_is_deterministic_and_auto_graded():
    first = template_set("backend", "middle")
    template_set.cache_clear()
    assert template_set("backend", "middle") == first
    assert len(first) == 12 and len({t.id for t in first}) == 12
    assert all(t.kind != "open_approach" for t in first)


# ——— API ———


async def test_only_experts_rate_and_tasks_have_no_keys(client, db):
    employer = await signup(client, "hr@bank.ru")
    params = {"specialization": "backend", "grade": "middle"}
    for headers in (employer, bearer(Role.candidate)):
        assert (await client.get(f"{ANGOFF}/tasks", params=params, headers=headers)).status_code == 403
        assert (await client.get(f"{ANGOFF}/summary", params=params, headers=headers)).status_code == 403
        body = {**params, "template_id": "x", "rating": 0.5}
        assert (await client.put(f"{ANGOFF}/ratings", json=body, headers=headers)).status_code == 403
    assert (await client.get(f"{ANGOFF}/tasks", params=params)).status_code == 401

    expert = await register_expert(client, "expert@example.com")
    response = await client.get(f"{ANGOFF}/tasks", params=params, headers=expert)
    assert response.status_code == 200
    data = response.json()
    assert data["progress"] == {"done": 0, "total": 12} and len(data["tasks"]) == 12
    assert all(task["rating"] is None and task["instance"]["stem"] for task in data["tasks"])
    assert not _keys(data) & (KEY_FIELDS | {"a", "b", "c"}), "ни ключей, ни параметров IRT"

    missing = await client.get(
        f"{ANGOFF}/tasks", params={**params, "specialization": "mobile"}, headers=expert
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "specialization_not_found"


async def test_rating_upsert_replaces_and_validates(client, db):
    expert = await register_expert(client, "expert@example.com")
    params = {"specialization": "backend", "grade": "junior"}
    template_id = template_set("backend", "junior")[0].id
    body = {**params, "template_id": template_id, "rating": 0.6}
    first = await client.put(f"{ANGOFF}/ratings", json=body, headers=expert)
    assert first.status_code == 200 and first.json() == {"done": 1, "total": 12}
    again = await client.put(f"{ANGOFF}/ratings", json=body | {"rating": 0.35}, headers=expert)
    assert again.json() == {"done": 1, "total": 12}, "повторная оценка заменяет прежнюю"
    tasks = (await client.get(f"{ANGOFF}/tasks", params=params, headers=expert)).json()["tasks"]
    assert {t["template_id"]: t["rating"] for t in tasks}[template_id] == 0.35

    assert (
        await client.put(f"{ANGOFF}/ratings", json=body | {"rating": 1.1}, headers=expert)
    ).status_code == 422
    foreign = body | {"template_id": "be.no_such_template"}
    response = await client.put(f"{ANGOFF}/ratings", json=foreign, headers=expert)
    assert response.status_code == 404 and response.json()["error"]["code"] == "template_not_found"


async def _rate_all(client, headers, grade: str, ratings: list[float]) -> None:
    for template, rating in zip(template_set("backend", grade), ratings, strict=True):
        body = {"specialization": "backend", "grade": grade, "template_id": template.id, "rating": rating}
        assert (await client.put(f"{ANGOFF}/ratings", json=body, headers=headers)).status_code == 200


async def test_summary_math_on_two_raters(client, db):
    alice = await register_expert(client, "alice@example.com")
    bob = await register_expert(client, "bob@example.com")
    carol = await register_expert(client, "carol@example.com")
    alice_ratings = [0.4, 0.5, 0.6, 0.7, 0.5, 0.5, 0.45, 0.55, 0.6, 0.4, 0.5, 0.65]
    bob_ratings = [0.6, 0.7, 0.8, 0.75, 0.7, 0.65, 0.6, 0.7, 0.8, 0.6, 0.7, 0.85]
    await _rate_all(client, alice, "middle", alice_ratings)
    await _rate_all(client, bob, "middle", bob_ratings)
    first = template_set("backend", "middle")[0].id
    partial = {"specialization": "backend", "grade": "middle", "template_id": first, "rating": 0.9}
    await client.put(f"{ANGOFF}/ratings", json=partial, headers=carol)

    response = await client.get(f"{ANGOFF}/summary", params={"specialization": "backend"}, headers=bob)
    assert response.status_code == 200
    grades = response.json()["grades"]
    assert [g["grade"] for g in grades] == ["middle"], "только грейды с полным набором хотя бы у одного"
    middle = grades[0]

    items = _items(template_set("backend", "middle"))
    cuts = [angoff_cut(items, r).theta for r in (alice_ratings, bob_ratings)]
    assert middle["raters"] == 2 and middle["incomplete_raters"] == 1 and middle["items"] == 12
    assert [c["rater"] for c in middle["rater_cuts"]] == ["Эксперт 1", "Эксперт 2"]
    assert [c["you"] for c in middle["rater_cuts"]] == [False, True]
    assert [c["cut"] for c in middle["rater_cuts"]] == [round(c, 3) for c in cuts]
    assert middle["rater_cuts"][0]["expected_share"] == round(mean(alice_ratings), 3)
    assert middle["mean_cut"] == round(mean(cuts), 3)
    assert middle["sd"] == round(stdev(cuts), 3)
    assert middle["se"] == round(stdev(cuts) / math.sqrt(2), 3)
    assert middle["current_cut"] == 0.2
    assert middle["difference"] == round(mean(cuts) - 0.2, 3)
    assert cuts[0] < cuts[1], "выше оценки — выше порог"

    admin = await client.get(
        f"{ANGOFF}/summary", params={"specialization": "backend"}, headers=bearer(Role.admin)
    )
    assert admin.status_code == 200
    assert not any(c["you"] for c in admin.json()["grades"][0]["rater_cuts"])
