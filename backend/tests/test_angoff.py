"""Modified Angoff (§10.4, §12.4): решатель порога, доступ, upsert оценок, отсутствие ключей, сводка."""

import math
from statistics import mean, stdev

import pytest

from app.core.enums import Role
from app.modules.expert.angoff_service import _items, template_set
from app.modules.testing.engine.angoff import (
    THETA_MAX,
    THETA_MIN,
    AngoffItem,
    HofsteeBox,
    angoff_cut,
    fail_rate,
    hofstee,
    in_hofstee_box,
    share_to_theta,
    tcc,
    theta_to_share,
)
from tests.conftest import bearer_for
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


async def test_only_experts_rate_and_tasks_have_no_keys(client, session):
    employer = await signup(client, "hr@bank.ru")
    params = {"specialization": "backend", "grade": "middle"}
    for headers in (employer, await bearer_for(session, Role.candidate)):
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


async def test_summary_math_on_two_raters(client, session):
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
    assert [r["round"] for r in middle["rounds"]] == [1], "раунд 2 никто не проходил"
    round1 = middle["rounds"][0]

    items = _items(template_set("backend", "middle"))
    cuts = [angoff_cut(items, r).theta for r in (alice_ratings, bob_ratings)]
    assert round1["raters"] == 2 and round1["incomplete_raters"] == 1 and middle["items"] == 12
    assert [c["rater"] for c in round1["rater_cuts"]] == ["Эксперт 1", "Эксперт 2"]
    assert [c["you"] for c in round1["rater_cuts"]] == [False, True]
    assert [c["cut"] for c in round1["rater_cuts"]] == [round(c, 3) for c in cuts]
    assert round1["rater_cuts"][0]["expected_share"] == round(mean(alice_ratings), 3)
    assert round1["mean_cut"] == round(mean(cuts), 3)
    assert round1["sd"] == round(stdev(cuts), 3)
    assert round1["se"] == round(stdev(cuts) / math.sqrt(2), 3)
    assert middle["recommended_round"] == 1 and middle["recommended_cut"] == round(mean(cuts), 3)
    assert middle["se"] == round1["se"]
    assert middle["current_cut"] == 0.2
    assert middle["difference"] == round(mean(cuts) - 0.2, 3)
    assert middle["recommended_raters"] == 8
    assert middle["hofstee"] is None and middle["impact_source"] == "synthetic"
    assert cuts[0] < cuts[1], "выше оценки — выше порог"

    admin = await client.get(
        f"{ANGOFF}/summary",
        params={"specialization": "backend"},
        headers=await bearer_for(session, Role.admin),
    )
    assert admin.status_code == 200
    assert not any(c["you"] for c in admin.json()["grades"][0]["rounds"][0]["rater_cuts"])


# ——— Hofstee: golden-кейсы ———


def test_hofstee_linear_curve_golden():
    # Кривая f = k, окно k ∈ [0,4; 0,8], f ∈ [0,2; 0,6]: диагональ f = 0,6 − (k − 0,4) → k = f = 0,5
    result = hofstee(HofsteeBox(0.4, 0.8, 0.2, 0.6), lambda k: k)
    assert result.intersects
    assert result.cut == pytest.approx(0.5, abs=1e-5)
    assert result.fail == pytest.approx(0.5, abs=1e-5)


def test_hofstee_quadratic_curve_golden():
    # f = k², окно k ∈ [0,5; 0,9], f ∈ [0,1; 0,5]: k² = 0,5 − (k − 0,5) → k² + k − 1 = 0 → k = (√5 − 1)/2
    result = hofstee(HofsteeBox(0.5, 0.9, 0.1, 0.5), lambda k: k * k)
    golden = (math.sqrt(5) - 1) / 2
    assert result.intersects
    assert result.cut == pytest.approx(golden, abs=1e-5)
    assert result.fail == pytest.approx(golden**2, abs=1e-5)


def test_hofstee_without_intersection_takes_nearest_edge():
    box = HofsteeBox(0.4, 0.8, 0.2, 0.6)
    too_strict = hofstee(box, lambda k: 0.9)  # кривая выше окна — порог у минимума
    assert not too_strict.intersects and too_strict.cut == 0.4 and too_strict.fail == 0.9
    too_lenient = hofstee(box, lambda k: 0.05)  # кривая ниже окна — порог у максимума
    assert not too_lenient.intersects and too_lenient.cut == 0.8


def test_hofstee_step_curve_and_degenerate_box():
    thetas = [-1.0, 0.0, 1.0, 2.0]
    # Ступенчатая эмпирическая кривая: пересечение на скачке — точка на диагонали
    result = hofstee(HofsteeBox(0.0, 1.0, 0.0, 1.0), lambda k: fail_rate(thetas, 4 * k - 2))
    assert result.intersects and result.fail == pytest.approx(1 - result.cut, abs=1e-5)
    point = hofstee(HofsteeBox(0.5, 0.5, 0.2, 0.6), lambda k: 0.4)
    assert point.intersects and point.cut == 0.5
    with pytest.raises(ValueError):
        hofstee(HofsteeBox(0.8, 0.4, 0.2, 0.6), lambda k: k)


def test_share_theta_roundtrip_and_box():
    items = [AngoffItem(1.0, b, 0.2) for b in (-1.0, 0.0, 1.0)]
    theta = share_to_theta(items, 0.6)
    assert theta_to_share(items, theta) == pytest.approx(0.6, abs=1e-5)
    assert fail_rate([0.1, 0.5, 0.9], 0.5) == pytest.approx(1 / 3)
    box = HofsteeBox(0.4, 0.8, 0.2, 0.6)
    assert in_hofstee_box(box, 0.5, 0.3) and not in_hofstee_box(box, 0.3, 0.3)
    assert not in_hofstee_box(box, 0.5, 0.7)


# ——— раунды, данные о последствиях, Hofstee: API ———


async def test_new_endpoints_require_expert(client, session):
    employer = await signup(client, "hr@bank.ru")
    params = {"specialization": "backend", "grade": "middle"}
    hofstee_body = {**params, "min_cut": 0.4, "max_cut": 0.7, "min_fail": 0.3, "max_fail": 0.6}
    for headers in (
        employer,
        await bearer_for(session, Role.candidate),
        await bearer_for(session, Role.admin),
    ):
        assert (await client.get(f"{ANGOFF}/impact", params=params, headers=headers)).status_code == 403
        assert (await client.post(f"{ANGOFF}/round2", json=params, headers=headers)).status_code == 403
        assert (await client.put(f"{ANGOFF}/hofstee", json=hofstee_body, headers=headers)).status_code == 403
    assert (await client.get(f"{ANGOFF}/impact", params=params)).status_code == 401


async def test_round2_and_impact_open_after_round1(client, db):
    alice = await register_expert(client, "alice@example.com")
    params = {"specialization": "backend", "grade": "middle"}
    for blocked in (
        await client.get(f"{ANGOFF}/tasks", params={**params, "round": 2}, headers=alice),
        await client.get(f"{ANGOFF}/impact", params=params, headers=alice),
        await client.post(f"{ANGOFF}/round2", json=params, headers=alice),
    ):
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "round1_incomplete"
    first = template_set("backend", "middle")[0].id
    body = {**params, "template_id": first, "rating": 0.5, "round": 2}
    response = await client.put(f"{ANGOFF}/ratings", json=body, headers=alice)
    assert response.status_code == 409

    ratings = [0.5] * 12
    await _rate_all(client, alice, "middle", ratings)
    tasks = (await client.get(f"{ANGOFF}/tasks", params=params, headers=alice)).json()
    assert tasks["round1_complete"] and not tasks["round2_started"] and tasks["round"] == 1
    assert tasks["hofstee"] is None and tasks["hofstee_defaults"]["min_fail"] == 0.3

    impact = (await client.get(f"{ANGOFF}/impact", params=params, headers=alice)).json()
    items = _items(template_set("backend", "middle"))
    cut = angoff_cut(items, ratings).theta
    assert impact["source"] == "synthetic" and impact["candidates"] == 2000
    assert impact["your_cut"] == round(cut, 3)
    assert impact["group"] is None, "один эксперт — группы нет"
    assert impact["proposed_cut"] == round(cut, 3) and impact["current_cut"] == 0.2
    assert [b["band"] for b in impact["bands"]] == ["none", "intern", "junior", "middle", "senior"]
    assert sum(b["current"] for b in impact["bands"]) == pytest.approx(1.0, abs=1e-3)
    assert sum(b["proposed"] for b in impact["bands"]) == pytest.approx(1.0, abs=1e-3)
    below_middle = sum(b["proposed"] for b in impact["bands"] if b["band"] in {"none", "intern", "junior"})
    assert below_middle == pytest.approx(impact["proposed_fail_rate"], abs=1e-3)

    started = await client.post(f"{ANGOFF}/round2", json=params, headers=alice)
    assert started.status_code == 200 and started.json() == {"done": 12, "total": 12}
    response = await client.put(f"{ANGOFF}/ratings", json=body | {"rating": 0.9}, headers=alice)
    assert response.json() == {"done": 12, "total": 12}
    round2 = (await client.get(f"{ANGOFF}/tasks", params={**params, "round": 2}, headers=alice)).json()
    assert round2["round2_started"] and round2["round"] == 2
    by_id = {t["template_id"]: t for t in round2["tasks"]}
    assert by_id[first]["rating"] == 0.9 and by_id[first]["round1_rating"] == 0.5
    assert by_id[first]["group"] is None
    round1 = (await client.get(f"{ANGOFF}/tasks", params=params, headers=alice)).json()
    assert {t["template_id"]: t["rating"] for t in round1["tasks"]}[first] == 0.5, "раунд 1 не меняется"
    again = await client.post(f"{ANGOFF}/round2", json=params, headers=alice)
    assert again.json() == {"done": 12, "total": 12}
    round2 = (await client.get(f"{ANGOFF}/tasks", params={**params, "round": 2}, headers=alice)).json()
    assert {t["template_id"]: t["rating"] for t in round2["tasks"]}[first] == 0.9, "копия не затирает раунд 2"

    summary = (
        await client.get(f"{ANGOFF}/summary", params={"specialization": "backend"}, headers=alice)
    ).json()
    middle = summary["grades"][0]
    assert [r["round"] for r in middle["rounds"]] == [1, 2]
    round2_ratings = [0.9 if t.id == first else 0.5 for t in template_set("backend", "middle")]
    round2_cut = angoff_cut(items, round2_ratings).theta
    assert middle["rounds"][0]["mean_cut"] == round(cut, 3)
    assert middle["rounds"][1]["mean_cut"] == round(round2_cut, 3)
    assert middle["recommended_round"] == 2 and middle["recommended_cut"] == round(round2_cut, 3)


async def test_group_feedback_with_two_raters(client, db):
    alice = await register_expert(client, "alice@example.com")
    bob = await register_expert(client, "bob@example.com")
    params = {"specialization": "backend", "grade": "junior"}
    alice_ratings = [0.4] * 12
    bob_ratings = [0.8] * 12
    await _rate_all(client, alice, "junior", alice_ratings)
    await _rate_all(client, bob, "junior", bob_ratings)
    impact = (await client.get(f"{ANGOFF}/impact", params=params, headers=alice)).json()
    items = _items(template_set("backend", "junior"))
    cuts = sorted(angoff_cut(items, r).theta for r in (alice_ratings, bob_ratings))
    group = impact["group"]
    assert group["raters"] == 2
    assert group["median_cut"] == round((cuts[0] + cuts[1]) / 2, 3)
    assert group["min_cut"] == round(cuts[0], 3) and group["max_cut"] == round(cuts[1], 3)
    await client.post(f"{ANGOFF}/round2", json=params, headers=alice)
    tasks = (await client.get(f"{ANGOFF}/tasks", params={**params, "round": 2}, headers=alice)).json()
    feedback = tasks["tasks"][0]["group"]
    assert feedback == {"raters": 2, "median": 0.6, "low": 0.4, "high": 0.8}


async def test_hofstee_saved_and_checked_in_summary(client, db):
    alice = await register_expert(client, "alice@example.com")
    bob = await register_expert(client, "bob@example.com")
    params = {"specialization": "backend", "grade": "middle"}
    bad = {**params, "min_cut": 0.7, "max_cut": 0.4, "min_fail": 0.3, "max_fail": 0.6}
    assert (await client.put(f"{ANGOFF}/hofstee", json=bad, headers=alice)).status_code == 422
    alice_box = {"min_cut": 0.4, "max_cut": 0.7, "min_fail": 0.3, "max_fail": 0.6}
    bob_box = {"min_cut": 0.5, "max_cut": 0.8, "min_fail": 0.2, "max_fail": 0.5}
    response = await client.put(f"{ANGOFF}/hofstee", json={**params, **alice_box}, headers=alice)
    assert response.status_code == 200 and response.json() == alice_box
    await client.put(f"{ANGOFF}/hofstee", json={**params, **alice_box, "max_fail": 0.7}, headers=bob)
    await client.put(f"{ANGOFF}/hofstee", json={**params, **bob_box}, headers=bob)
    tasks = (await client.get(f"{ANGOFF}/tasks", params=params, headers=bob)).json()
    assert tasks["hofstee"] == bob_box, "повторная отправка заменяет прежние значения"

    ratings = [0.6] * 12
    await _rate_all(client, alice, "middle", ratings)
    summary = (
        await client.get(f"{ANGOFF}/summary", params={"specialization": "backend"}, headers=alice)
    ).json()
    check = summary["grades"][0]["hofstee"]
    assert check["raters"] == 2
    assert check["box"] == {"min_cut": 0.45, "max_cut": 0.75, "min_fail": 0.25, "max_fail": 0.55}

    from app.modules.expert.angoff_service import synthetic_thetas

    items = _items(template_set("backend", "middle"))
    thetas = list(synthetic_thetas())
    box = HofsteeBox(0.45, 0.75, 0.25, 0.55)
    expected = hofstee(box, lambda share: fail_rate(thetas, share_to_theta(items, share)))
    angoff_theta = angoff_cut(items, ratings).theta
    assert check["cut_share"] == round(expected.cut, 4) and check["intersects"] == expected.intersects
    assert check["angoff_share"] == pytest.approx(0.6, abs=1e-3)
    assert check["angoff_fail_rate"] == round(fail_rate(thetas, angoff_theta), 4)
    assert check["in_box"] == in_hofstee_box(
        box, theta_to_share(items, angoff_theta), fail_rate(thetas, angoff_theta)
    )


async def test_impact_population_uses_latest_completed_attempt(client, session, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app.core.enums import AttemptPurpose, AttemptStatus, Grade
    from app.modules.expert import angoff_service
    from app.modules.testing import service as testing_service
    from app.modules.testing.models import TestAttempt
    from tests.test_needs import candidate_id

    now = datetime.now(UTC)
    for email, attempts in (
        ("anna@example.com", [(-0.5, 2, AttemptStatus.completed), (0.8, 1, AttemptStatus.completed)]),
        ("boris@example.com", [(1.5, 1, AttemptStatus.in_progress), (0.1, 3, AttemptStatus.completed)]),
    ):
        await signup(client, email, role="candidate")
        cid = await candidate_id(session, email)
        for theta, days_ago, status in attempts:
            session.add(
                TestAttempt(
                    candidate_id=cid,
                    specialization="backend",
                    grade_target=Grade.middle,
                    purpose=AttemptPurpose.calibration,
                    blueprint={},
                    seed=1,
                    status=status,
                    theta=theta,
                    finished_at=now - timedelta(days=days_ago),
                )
            )
    await session.commit()
    assert sorted(await testing_service.latest_thetas(session, "backend")) == [0.1, 0.8]
    assert await testing_service.latest_thetas(session, "frontend") == []
    assert (await angoff_service.population(session, "backend"))[1] == "synthetic"
    monkeypatch.setattr(angoff_service.get_config().impact, "min_candidates", 2)
    thetas, source = await angoff_service.population(session, "backend")
    assert source == "results" and sorted(thetas) == [0.1, 0.8]
