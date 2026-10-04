import random

import pytest

from app.modules.testing.engine.bank import Bank, get_blueprints
from app.modules.testing.engine.irt import ItemResponse, eap, probability
from app.modules.testing.engine.model import Template
from app.modules.testing.engine.render import render
from app.modules.testing.engine.scoring import score
from app.modules.testing.engine.session import (
    STAGE_ONE,
    STAGE_PILOT,
    STAGE_TWO,
    Answered,
    AttemptConfig,
    Planner,
    split_quotas,
)

BLUEPRINTS = get_blueprints()
SPEC = "backend"


def synthetic_bank(per_topic: int = 9, pilots: int = 3) -> Bank:
    """Банк с равномерной сеткой сложностей по каждой теме blueprint'а backend."""
    templates = {}
    for topic in BLUEPRINTS.specializations[SPEC].topics:
        for index in range(per_topic):
            template_id = f"t.{topic}.{index}"
            templates[template_id] = Template.model_validate(
                {
                    "id": template_id,
                    "specializations": [SPEC],
                    "topic": topic,
                    "stack_module": "python" if topic == "stack" else None,
                    "skills": ["python"] if topic == "stack" else ["rest"],
                    "kind": "single_choice",
                    "irt": {"a": 1.5, "b": round(-2.0 + 4.0 * index / (per_topic - 1), 2)},
                    "params": {"n": {"int": [1, 50]}},
                    "stem": "Задание {{n}}",
                    "options": {
                        "correct": ["верно {{n}}"],
                        "wrong": ["a {{n}}", "b {{n}}", "c {{n}}", "d {{n}}"],
                    },
                }
            )
    for index in range(pilots):
        pilot_id = f"p.{index}"
        templates[pilot_id] = templates["t.http_api.0"].model_copy(update={"id": pilot_id, "status": "pilot"})
    return Bank(templates=templates)


def run_attempt(theta_true: float, grade: str, seed: int, bank: Bank, mode: str = "full"):
    config = AttemptConfig(SPEC, grade, seed=seed, mode=mode, stack_modules=("python",))
    planner = Planner(config, bank, BLUEPRINTS, exposure={})
    history: list[Answered] = []
    rng = random.Random(seed * 7919)
    while (item := planner.next_item(history)) is not None:
        template = item.template
        p = float(probability(theta_true, template.irt.a, template.irt.b, template.guessing))
        answer = 1.0 if rng.random() < p else 0.0
        history.append(Answered(template.id, item.stage, item.scored, answer if item.scored else None))
    return planner, history


def test_split_quotas_preserves_total():
    topics = BLUEPRINTS.specializations[SPEC].topics
    for total in (4, 8, 9, 18):
        quotas = split_quotas(topics, total)
        assert sum(quotas.values()) == total
        assert all(value >= 0 for value in quotas.values())


def test_eap_without_answers_is_prior():
    theta, se = eap([])
    assert abs(theta) < 1e-6
    assert se == pytest.approx(1.0, abs=0.02)


def test_eap_moves_with_answers():
    assert eap([ItemResponse(1.5, 1.0, 0.25, 1.0)] * 6)[0] > 1.0
    assert eap([ItemResponse(1.5, -1.0, 0.25, 0.0)] * 6)[0] < -1.0


def test_attempt_is_deterministic():
    bank = synthetic_bank()
    assert run_attempt(0.3, "middle", 42, bank)[1] == run_attempt(0.3, "middle", 42, bank)[1]


def test_attempt_length_stages_and_no_repeats():
    _, history = run_attempt(0.3, "middle", 5, synthetic_bank())
    mode = BLUEPRINTS.modes["full"]
    ids = [answer.template_id for answer in history]
    assert len(ids) == len(set(ids))
    scored = [answer for answer in history if answer.scored]
    assert sum(a.stage == STAGE_ONE for a in scored) == mode.stage1_items
    assert sum(a.stage == STAGE_TWO for a in scored) == mode.stage2_items
    assert len(scored) <= mode.stage1_items + mode.stage2_items + mode.extra_items_max
    assert sum(a.stage == STAGE_PILOT for a in history) == mode.pilot_slots


def test_topic_quotas_follow_blueprint():
    planner, history = run_attempt(0.0, "junior", 11, synthetic_bank())
    asked: dict[str, int] = {}
    for answer in history:
        if answer.scored and answer.stage in (STAGE_ONE, STAGE_TWO):
            topic = planner.templates[answer.template_id].topic
            asked[topic] = asked.get(topic, 0) + 1
    assert asked == BLUEPRINTS.specializations[SPEC].topics


def test_stage_two_routes_by_stage_one_result():
    bank = synthetic_bank()

    def mean_b(planner, history, stage):
        values = [planner.templates[a.template_id].irt.b for a in history if a.stage == stage]
        return sum(values) / len(values)

    strong_planner, strong = run_attempt(2.5, "junior", 3, bank)
    weak_planner, weak = run_attempt(-2.5, "senior", 3, bank)
    assert mean_b(strong_planner, strong, STAGE_TWO) > mean_b(strong_planner, strong, STAGE_ONE)
    assert mean_b(weak_planner, weak, STAGE_TWO) < mean_b(weak_planner, weak, STAGE_ONE)


@pytest.mark.parametrize(
    ("theta_true", "grade", "expected", "min_share"),
    [
        (2.5, "middle", {"confident_pass"}, 0.9),
        (-2.5, "middle", {"fail"}, 0.95),
        (0.9, "middle", {"pass", "confident_pass"}, 0.85),
        (-1.0, "middle", {"fail"}, 0.9),
    ],
)
def test_decision_matches_true_ability(theta_true, grade, expected, min_share):
    """Решение о грейде — статистическое: проверяем долю верных решений на 40 симуляциях."""
    bank = synthetic_bank()
    hits = 0
    for seed in range(40):
        planner, history = run_attempt(theta_true, grade, seed, bank)
        hits += planner.summarize(history).result in expected
    assert hits / 40 >= min_share


def test_exposure_cap_excludes_overexposed_templates():
    bank = synthetic_bank()
    exposure = {template_id: 0.9 for template_id in bank.templates if template_id.startswith("t.http_api.")}
    exposure.pop("t.http_api.4")
    planner = Planner(
        AttemptConfig(SPEC, "middle", seed=1, stack_modules=("python",)), bank, BLUEPRINTS, exposure
    )
    history: list[Answered] = []
    while (item := planner.next_item(history)) is not None:
        history.append(Answered(item.template.id, item.stage, item.scored, 1.0 if item.scored else None))
    first_http = next(a.template_id for a in history if a.template_id.startswith("t.http_api."))
    assert first_http == "t.http_api.4"


def test_render_differs_between_seeds_and_scoring_follows_key():
    template = synthetic_bank().templates["t.stack.3"]
    first, second = render(template, 1), render(template, 2)
    assert (first.stem, first.options) != (second.stem, second.options)
    correct = first.key["choice_ids"]
    assert score(first.kind, first.key, {"choice_ids": correct}) == 1.0
    wrong = [option.id for option in first.options if option.id not in correct][:1]
    assert score(first.kind, first.key, {"choice_ids": wrong}) == 0.0


def test_short_mode_is_short():
    _, history = run_attempt(0.0, "junior", 9, synthetic_bank(), mode="short")
    mode = BLUEPRINTS.modes["short"]
    assert len(history) <= mode.stage1_items + mode.stage2_items + mode.extra_items_max
