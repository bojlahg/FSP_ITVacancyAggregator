"""Публичная страница «Как работает тест»: без входа, без ключей ответов, с лимитами (без БД)."""

from collections import Counter
from typing import Any

import pytest

from app.core.config import get_settings
from app.modules.testing.engine.bank import get_bank
from app.modules.testing.engine.render import render
from app.modules.testing.explainer_service import _content, diversity_of

API = "/api/v1/explainer"
KEY_FIELDS = {
    "key",
    "answer_key",
    "choice_ids",
    "correct",
    "order",
    "number",
    "rubric",
    "answer",
    "tolerance",
}


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in _keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in _keys(item)}
    return set()


def _template_ids(kind: str) -> str:
    return next(
        t.id
        for t in sorted(get_bank().templates.values(), key=lambda t: t.id)
        if t.kind == kind and t.status == "showcase"
    )


async def test_overview_is_public(client):
    response = await client.get(f"{API}/overview")
    assert response.status_code == 200
    body = response.json()
    assert [g["grade"] for g in body["grades"]] == ["intern", "junior", "middle", "senior"]
    assert {s["slug"] for s in body["specializations"]} >= {"backend", "frontend", "qa", "devops", "data"}
    assert all(s["active_templates"] > 0 for s in body["specializations"])


async def test_templates_list_without_keys(client):
    response = await client.get(f"{API}/specializations/backend/templates")
    assert response.status_code == 200
    templates = response.json()
    assert templates
    assert all(t["kind"] != "open_approach" for t in templates)
    assert not _keys(templates) & KEY_FIELDS
    # Публичная страница не открывает рабочий банк: только витрина, которая в тесты не входит (§10.6)
    bank = get_bank()
    assert all(bank.templates[t["id"]].status == "showcase" for t in templates)


async def test_working_bank_is_not_exposed(client):
    working = next(t.id for t in get_bank().for_spec("backend") if t.status == "active")
    response = await client.get(f"{API}/templates/{working}/instances", params={"seeds": [1]})
    assert response.status_code == 404


async def test_unknown_specialization_is_404(client):
    for path in ("templates", "information?grade=middle"):
        response = await client.get(f"{API}/specializations/mobile/{path}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "specialization_not_found"


@pytest.mark.parametrize("kind", ["single_choice", "multi_choice", "numeric", "ordering", "code_output"])
async def test_instances_have_no_answer_keys(client, kind):
    template_id = _template_ids(kind)
    response = await client.get(f"{API}/templates/{template_id}/instances", params={"seeds": [1, 2, 3, 2]})
    assert response.status_code == 200
    body = response.json()
    assert [item["seed"] for item in body["instances"]] == [1, 2, 3]
    assert not _keys(body) & KEY_FIELDS
    template = get_bank().templates[template_id]
    first = body["instances"][0]
    rendered = render(template, 1)
    assert first["stem"] == rendered.stem
    assert [o["text"] for o in first["options"]] == [o.text for o in rendered.options]
    assert body["template"]["c"] == pytest.approx(template.guessing, abs=1e-4)
    assert len(body["icc"]) == 81


async def test_unknown_or_inactive_template_is_404(client):
    bank = get_bank()
    hidden = [t.id for t in bank.templates.values() if t.status != "showcase" or t.kind == "open_approach"]
    for template_id in ["no.such.template", *hidden[:2]]:
        for path in ("instances?seeds=1", "diversity?sample=10"):
            response = await client.get(f"{API}/templates/{template_id}/{path}")
            assert response.status_code == 404, (template_id, path)
            assert response.json()["error"]["code"] == "template_not_found"


async def test_caps_are_enforced(client):
    settings = get_settings()
    template_id = _template_ids("single_choice")
    too_many = {"seeds": list(range(settings.explainer_max_seeds + 1))}
    assert (await client.get(f"{API}/templates/{template_id}/instances", params=too_many)).status_code == 422
    assert (await client.get(f"{API}/templates/{template_id}/instances")).status_code == 422
    assert (
        await client.get(f"{API}/templates/{template_id}/instances", params={"seeds": [-1]})
    ).status_code == 422
    big = {"sample": settings.explainer_max_sample + 1}
    assert (await client.get(f"{API}/templates/{template_id}/diversity", params=big)).status_code == 422


async def test_diversity_counts_distinct_instances(client):
    template_id = _template_ids("code_output")
    response = await client.get(f"{API}/templates/{template_id}/diversity", params={"sample": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["sample"] == 100
    assert 1 < body["distinct"] <= 100
    assert 0 <= body["collision_probability"] <= 1
    assert (body["collision_probability"] > 0) == (body["distinct"] < body["sample"])
    assert 0 <= body["leak_match_share"] <= 1
    assert body["leak_size"] == get_settings().explainer_leak_size


async def test_information_simulates_three_routes(client):
    response = await client.get(f"{API}/specializations/backend/information", params={"grade": "middle"})
    assert response.status_code == 200
    body = response.json()
    assert body["cut"] == pytest.approx(0.2)
    assert [s["scenario"] for s in body["scenarios"]] == ["below", "at", "above"]
    below, at, above = body["scenarios"]
    assert below["pass_share"] < at["pass_share"] < above["pass_share"]
    assert below["stage2_target"] < at["stage2_target"] < above["stage2_target"]
    peak = max(at["information"], key=lambda p: p["information"])
    assert abs(peak["theta"] - body["cut"]) < 1.0
    assert 0 < body["instance_overlap"] < body["template_overlap"] < 1
    assert not _keys(body) & KEY_FIELDS


async def test_information_rejects_unknown_grade(client):
    response = await client.get(f"{API}/specializations/backend/information", params={"grade": "lead"})
    assert response.status_code == 422


def test_collision_probability_is_unbiased_pair_estimate():
    template = min(
        (t for t in get_bank().for_spec("backend") if t.status == "active" and t.kind != "open_approach"),
        key=lambda t: len({_content(render(t, seed)) for seed in range(50)}),
    )
    sample, leak = 60, get_settings().explainer_leak_size
    counts = Counter(_content(render(template, seed)) for seed in range(leak, leak + sample))
    expected = sum(c * (c - 1) for c in counts.values()) / (sample * (sample - 1))
    result = diversity_of(template, sample)
    assert result.distinct == len(counts)
    assert result.collision_probability == pytest.approx(expected, abs=1e-4)
    assert result.collision_probability > 0
