"""Blueprint под вакансию (§10.7): смещение весов тем по навыкам вакансии и выбор примеров заданий.

Чистые функции без БД: одинаковые навыки дают одинаковый blueprint и одинаковые шаблоны примеров.
Seed меняет только экземпляры (числа, имена, порядок вариантов), но не шаблоны и не сложность.
"""

from collections import Counter
from dataclasses import dataclass, field

from app.modules.testing.engine.bank import Bank, Blueprints
from app.modules.testing.engine.model import Template
from app.modules.testing.engine.session import split_quotas


@dataclass(frozen=True)
class SkillBoost:
    skill: str
    topic: str
    weight: int
    required: bool


@dataclass
class VacancyBlueprint:
    specialization: str
    base_topics: dict[str, int]
    topics: dict[str, int]
    stack_modules: list[str]
    boosts: list[SkillBoost] = field(default_factory=list)
    uncovered_skills: list[str] = field(default_factory=list)
    dropped_topics: list[str] = field(default_factory=list)


def _scorable(bank: Bank, specialization: str) -> list[Template]:
    return [t for t in bank.for_spec(specialization) if t.status == "active" and t.kind != "open_approach"]


def build(
    bank: Bank,
    blueprints: Blueprints,
    specialization: str,
    required: list[str],
    optional: list[str],
    stack_modules: list[str],
) -> VacancyBlueprint:
    """stack_modules — модули по навыкам вакансии (их соответствие навыкам задаёт content/survey.yaml)."""
    base = dict(blueprints.specializations[specialization].topics)
    total = sum(base.values())
    config = blueprints.vacancy
    modules = sorted(stack_modules)
    pool = [t for t in _scorable(bank, specialization) if t.stack_module is None or t.stack_module in modules]

    weights = dict(base)
    dropped = sorted(topic for topic in base if not any(t.topic == topic for t in pool))
    for topic in dropped:
        weights.pop(topic)
    if not weights:
        raise ValueError(f"нет активных шаблонов для {specialization}")

    boosts: list[SkillBoost] = []
    uncovered: list[str] = []
    seen: set[str] = set()
    for skill, is_required in [(s, True) for s in required] + [(s, False) for s in optional]:
        if skill in seen:
            continue
        seen.add(skill)
        topics = Counter(t.topic for t in pool if skill in t.skills and t.topic in weights)
        if not topics:
            uncovered.append(skill)
            continue
        # Тема, где навык проверяется чаще всего; при равенстве — более весомая в базовом blueprint
        topic = max(topics, key=lambda name: (topics[name], base[name], name))
        weight = config.boost_required if is_required else config.boost_optional
        weights[topic] += weight
        boosts.append(SkillBoost(skill=skill, topic=topic, weight=weight, required=is_required))

    return VacancyBlueprint(
        specialization=specialization,
        base_topics=base,
        topics=split_quotas(weights, total),
        stack_modules=modules,
        boosts=boosts,
        uncovered_skills=uncovered,
        dropped_topics=dropped,
    )


def sample_templates(
    bank: Bank, blueprints: Blueprints, plan: VacancyBlueprint, skills: list[str], grade: str
) -> list[Template]:
    """Шаблоны для предпросмотра: разные темы, сначала темы с навыками вакансии, сложность у порога грейда."""
    target = blueprints.cut(grade)
    wanted = set(skills)
    boosted = Counter()
    for boost in plan.boosts:
        boosted[boost.topic] += boost.weight
    pool = [
        t
        for t in _scorable(bank, plan.specialization)
        if (t.stack_module is None or t.stack_module in plan.stack_modules) and plan.topics.get(t.topic)
    ]
    topics = sorted(plan.topics, key=lambda topic: (-boosted[topic], -plan.topics[topic], topic))
    chosen: list[Template] = []
    for topic in topics:
        candidates = [t for t in pool if t.topic == topic]
        if not candidates:
            continue
        best = min(
            candidates, key=lambda t: (not wanted & set(t.skills), round(abs(t.irt.b - target), 2), t.id)
        )
        chosen.append(best)
        if len(chosen) == blueprints.vacancy.sample_items:
            break
    return chosen
