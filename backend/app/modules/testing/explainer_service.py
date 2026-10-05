"""Публичная страница «Как работает тест»: живые данные движка без БД и без входа.

Всё считается тем же кодом, что и настоящий тест: рендер по seed (§10.2), Planner MST (§10.3),
3PL и информация Фишера (§10.4). Ключи ответов (`Instance.key`) не покидают этот модуль.
"""

import itertools
import random
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean

import numpy as np

from app.core.config import get_settings
from app.core.enums import Grade, ItemKind
from app.core.errors import NotFoundError
from app.modules.catalog.service import get_catalog
from app.modules.testing.engine.bank import GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.irt import GRID, information, probability
from app.modules.testing.engine.model import Instance, Template
from app.modules.testing.engine.render import render
from app.modules.testing.engine.session import Answered, AttemptConfig, Planner
from app.modules.testing.schemas import (
    CurvePoint,
    ExplainerDiversity,
    ExplainerGrade,
    ExplainerInformation,
    ExplainerInstance,
    ExplainerInstances,
    ExplainerItemPoint,
    ExplainerOverview,
    ExplainerScenario,
    ExplainerSpecialization,
    ExplainerTemplate,
    InformationPoint,
    ItemOption,
)

SCENARIO_LABELS = {
    "below": "Кандидат слабее порога",
    "at": "Кандидат у порога",
    "above": "Кандидат сильнее порога",
}


def _scorable(template: Template) -> bool:
    return template.status == "active" and template.kind != "open_approach"


def _grade_names() -> dict[str, str]:
    return {item.slug.value: item.name for item in get_catalog().grades}


def _grades() -> list[ExplainerGrade]:
    blueprints, names = get_blueprints(), _grade_names()
    return [ExplainerGrade(grade=Grade(g), name=names.get(g, g), cut=blueprints.cut(g)) for g in GRADE_ORDER]


def _tested_specializations() -> dict[str, str]:
    blueprints = get_blueprints()
    return {
        spec.slug: spec.name
        for spec in get_catalog().specializations
        if spec.has_test and spec.slug in blueprints.specializations
    }


def _require_specialization(slug: str) -> None:
    if slug not in _tested_specializations():
        raise NotFoundError("Для этой специализации теста нет", code="specialization_not_found")


def _require_template(template_id: str) -> Template:
    template = get_bank().templates.get(template_id)
    if template is None or not _scorable(template):
        raise NotFoundError("Шаблон не найден или не используется в тесте", code="template_not_found")
    return template


def _difficulty(b: float) -> str:
    """Сложность словами: самый высокий грейд, порог которого не выше b (как в «Проверке под вакансию»)."""
    blueprints, names = get_blueprints(), _grade_names()
    level = next((g for g in reversed(GRADE_ORDER) if b >= blueprints.cut(g)), None)
    return f"уровень {names.get(level, level)}" if level else "ниже уровня стажёра"


def _template_out(template: Template) -> ExplainerTemplate:
    skill_names = {skill.id: skill.name for skill in get_catalog().skills}
    topic_names = get_blueprints().topic_names
    return ExplainerTemplate(
        id=template.id,
        topic=template.topic,
        topic_name=topic_names.get(template.topic, template.topic),
        kind=ItemKind(template.kind),
        skills=[skill_names.get(skill, skill) for skill in template.skills],
        a=template.irt.a,
        b=template.irt.b,
        c=round(template.guessing, 4),
        difficulty=_difficulty(template.irt.b),
    )


def _curve(values: np.ndarray) -> list[CurvePoint]:
    return [
        CurvePoint(theta=round(float(t), 2), value=round(float(v), 4))
        for t, v in zip(GRID, values, strict=True)
    ]


def overview() -> ExplainerOverview:
    blueprints, settings = get_blueprints(), get_settings()
    bank = get_bank()
    mode = blueprints.modes["full"]
    tested = _tested_specializations()
    return ExplainerOverview(
        grades=_grades(),
        active_templates=sum(
            1 for t in bank.templates.values() if _scorable(t) and set(t.specializations) & set(tested)
        ),
        specializations=[
            ExplainerSpecialization(
                slug=slug,
                name=name,
                active_templates=sum(1 for t in bank.for_spec(slug) if _scorable(t)),
                topics=len(blueprints.specializations[slug].topics),
            )
            for slug, name in tested.items()
        ],
        stage1_items=mode.stage1_items,
        stage2_items=mode.stage2_items,
        extra_items_max=mode.extra_items_max,
        stage_split=blueprints.scale.stage_split,
        max_seeds=settings.explainer_max_seeds,
        max_sample=settings.explainer_max_sample,
        leak_size=settings.explainer_leak_size,
    )


def templates(specialization: str) -> list[ExplainerTemplate]:
    _require_specialization(specialization)
    found = [t for t in get_bank().for_spec(specialization) if _scorable(t)]
    return [_template_out(t) for t in sorted(found, key=lambda t: (t.topic, t.irt.b, t.id))]


def _instance_out(seed: int, instance: Instance) -> ExplainerInstance:
    payload = instance.public_payload()  # без ключа: key остаётся в Instance
    return ExplainerInstance(
        seed=seed,
        stem=payload["stem"],
        code=payload["code"],
        code_language=payload["code_language"],
        options=[ItemOption(**option) for option in payload["options"]],
    )


def instances(template_id: str, seeds: list[int]) -> ExplainerInstances:
    template = _require_template(template_id)
    icc = probability(GRID, template.irt.a, template.irt.b, template.guessing)
    return ExplainerInstances(
        template=_template_out(template),
        icc=_curve(icc),
        instances=[_instance_out(seed, render(template, seed)) for seed in dict.fromkeys(seeds)],
    )


def _content(instance: Instance) -> tuple:
    """Экземпляр с точки зрения утечки: текст, код и набор вариантов без учёта их порядка."""
    return instance.stem, instance.code, tuple(sorted(option.text for option in instance.options))


@lru_cache(maxsize=256)
def diversity(template_id: str, sample: int) -> ExplainerDiversity:
    template = _require_template(template_id)
    leak_size = get_settings().explainer_leak_size
    leaked = {_content(render(template, seed)) for seed in range(leak_size)}
    fresh = Counter(_content(render(template, seed)) for seed in range(leak_size, leak_size + sample))
    # P(у двух разных попыток один экземпляр): несмещённая оценка Σ c(c−1) / (n(n−1)) по выборке
    collision = sum(count * (count - 1) for count in fresh.values()) / (sample * (sample - 1))
    matched = sum(count for content, count in fresh.items() if content in leaked)
    return ExplainerDiversity(
        template_id=template.id,
        sample=sample,
        distinct=len(fresh),
        collision_probability=round(collision, 4),
        leak_size=leak_size,
        leak_match_share=round(matched / sample, 4),
    )


def _scenario_thetas(grade: str) -> dict[str, float]:
    """Где стоит симулированный кандидат: у тех же точек, куда Planner ведёт этап 2 (§10.3)."""
    blueprints = get_blueprints()
    cut = blueprints.cut(grade)
    lower, higher = blueprints.previous_grade(grade), blueprints.next_grade(grade)
    return {
        "below": (blueprints.cut(lower) + cut) / 2 if lower else cut - 1.0,
        "at": cut,
        "above": blueprints.cut(higher) if higher else cut + 1.0,
    }


def _stack_module(specialization: str) -> str | None:
    """Самый частый стек-модуль банка: так симулированный тест покрывает тему «Язык и фреймворк»."""
    modules = Counter(
        t.stack_module for t in get_bank().for_spec(specialization) if _scorable(t) and t.stack_module
    )
    return min(modules, key=lambda m: (-modules[m], m)) if modules else None


@dataclass
class _Run:
    items: list[Template]
    stages: list[int]
    instances: set[tuple]
    theta: float
    se: float
    decision: str
    stage2_target: float


def _simulate(
    specialization: str,
    grade: str,
    theta_true: float,
    stack: str | None,
    run: int,
    exposure: dict[str, float],
) -> _Run:
    """Одна попытка настоящим Planner'ом: ответы симулированного кандидата — по 3PL от theta_true."""
    planner = Planner(
        AttemptConfig(specialization, grade, seed=run, stack_modules=(stack,) if stack else ()),
        get_bank(),
        get_blueprints(),
        exposure=exposure,
    )
    rng = random.Random(f"explainer:{specialization}:{grade}:{theta_true}:{run}")
    history: list[Answered] = []
    result = _Run([], [], set(), 0.0, 0.0, "", 0.0)
    while (item := planner.next_item(history)) is not None:
        score = None
        if item.scored:
            t = item.template
            p = float(probability(theta_true, t.irt.a, t.irt.b, t.guessing))
            score = 1.0 if rng.random() < p else 0.0
            result.items.append(t)
            result.stages.append(item.stage)
            result.instances.add((t.id, _content(render(t, item.instance_seed))))
        history.append(Answered(item.template.id, item.stage, item.scored, score))
    result.theta, result.se = planner.estimate(history)
    result.decision = planner.decide(result.theta, result.se)
    result.stage2_target = planner.stage_two_target(history)
    return result


def _mean_overlap(sets: list[set]) -> float:
    """Средняя доля заданий одной попытки, встретившихся в другой (как в validation/leakage.py)."""
    pairs = [(x, y) for x, y in itertools.permutations(sets, 2) if x]
    return mean(len(x & y) / len(x) for x, y in pairs) if pairs else 0.0


def _scenario(specialization: str, grade: Grade, key: str, theta_true: float, stack: str | None) -> tuple:
    runs: list[_Run] = []
    shows: Counter[str] = Counter()
    for run in range(get_settings().explainer_simulations):
        # Контроль экспозиции как в продукте: доля показов шаблона среди предыдущих попыток
        exposure = {tid: count / run for tid, count in shows.items()} if run else {}
        result = _simulate(specialization, grade.value, theta_true, stack, run, exposure)
        shows.update(t.id for t in result.items)
        runs.append(result)
    info = np.mean(
        [sum(information(GRID, t.irt.a, t.irt.b, t.guessing) for t in r.items) for r in runs], axis=0
    )
    se_curve = 1.0 / np.sqrt(info + 1.0)
    scenario = ExplainerScenario(
        scenario=key,
        label=SCENARIO_LABELS[key],
        theta_true=round(theta_true, 2),
        stage2_target=round(mean(r.stage2_target for r in runs), 2),
        items_mean=round(mean(len(r.items) for r in runs), 1),
        se_mean=round(mean(r.se for r in runs), 3),
        pass_share=round(mean(r.decision != "fail" for r in runs), 3),
        information=[
            InformationPoint(theta=round(float(t), 2), information=round(float(i), 3), se=round(float(s), 3))
            for t, i, s in zip(GRID, info, se_curve, strict=True)
        ],
        items=[
            ExplainerItemPoint(b=t.irt.b, a=t.irt.a, stage=stage)
            for t, stage in zip(runs[0].items, runs[0].stages, strict=True)
        ],
    )
    template_overlap = _mean_overlap([{t.id for t in r.items} for r in runs])
    instance_overlap = _mean_overlap([r.instances for r in runs])
    return scenario, template_overlap, instance_overlap


@lru_cache(maxsize=32)
def information_profile(specialization: str, grade: Grade) -> ExplainerInformation:
    _require_specialization(specialization)
    stack = _stack_module(specialization)
    scenarios: list[ExplainerScenario] = []
    template_overlap = instance_overlap = 0.0
    for key, theta_true in _scenario_thetas(grade.value).items():
        scenario, templates_shared, instances_shared = _scenario(
            specialization, grade, key, theta_true, stack
        )
        scenarios.append(scenario)
        if key == "at":
            template_overlap, instance_overlap = templates_shared, instances_shared
    return ExplainerInformation(
        specialization=specialization,
        grade=grade,
        cut=get_blueprints().cut(grade.value),
        grades=_grades(),
        stack_module=stack,
        simulations=get_settings().explainer_simulations,
        template_overlap=round(template_overlap, 3),
        instance_overlap=round(instance_overlap, 4),
        scenarios=scenarios,
    )
