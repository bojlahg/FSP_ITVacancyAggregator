"""Ранжирование и объяснение (§8.3–8.4). Чистые функции: score и объяснение считаются из одних компонентов."""

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import yaml
from pydantic import BaseModel

from app.modules.catalog.service import CONTENT_DIR, get_catalog
from app.modules.testing.engine.bank import GRADE_ORDER, get_bank, get_blueprints

Fit = Literal["exact", "adjacent_grade", "adjacent_specialization", "adjacent_both"]


class MatchingRules(BaseModel):
    weights: dict[str, float]
    category_fit: dict[str, float]
    skill_value: dict[str, float]
    required_weight: float
    optional_weight: float
    strength: dict[str, float]
    conditions: dict[str, float]
    recommendations: dict[str, int]


@lru_cache
def get_rules() -> MatchingRules:
    with (CONTENT_DIR / "matching.yaml").open(encoding="utf-8") as file:
        return MatchingRules.model_validate(yaml.safe_load(file))


@dataclass(frozen=True)
class NeedSpec:
    specialization: str
    grade: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    work_format: str | None = None
    city: str | None = None
    salary_from: int = 0
    salary_to: int = 0


@dataclass
class CandidateFacts:
    candidate_id: int
    specialization: str
    grade: str
    theta: float
    percentile: float | None
    topic_scores: dict[str, dict]
    skills_status: dict[str, str]
    fsp_score: float = 0.0
    has_fsp: bool = False
    fresh: float = 0.0
    fresh_days: int | None = None
    salary_min: int | None = None
    work_formats: list[str] = field(default_factory=list)
    city: str | None = None
    relocation: bool = False
    best_fsp: str | None = None


@dataclass
class MatchResult:
    score: int
    components: dict[str, float]
    fit: Fit
    lines: list[dict]
    out_of_filter: list[str]


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def category_fit(candidate_spec: str, candidate_grade: str, need: NeedSpec) -> Fit | None:
    """Точная категория, соседний грейд, смежная специализация или и то и другое (§8.3)."""
    adjacent_specs = next(
        (set(spec.adjacent) for spec in get_catalog().specializations if spec.slug == need.specialization),
        set(),
    )
    same_spec = candidate_spec == need.specialization
    near_spec = candidate_spec in adjacent_specs
    distance = abs(GRADE_ORDER.index(candidate_grade) - GRADE_ORDER.index(need.grade))
    if same_spec and distance == 0:
        return "exact"
    if same_spec and distance == 1:
        return "adjacent_grade"
    if near_spec and distance == 0:
        return "adjacent_specialization"
    if near_spec and distance == 1:
        return "adjacent_both"
    return None


@lru_cache
def skill_topics(specialization: str) -> dict[str, frozenset[str]]:
    """Какие темы теста проверяют навык — из банка шаблонов (нужен PostgreSQL → тема «Базы данных»)."""
    mapping: dict[str, set[str]] = {}
    for template in get_bank().for_spec(specialization):
        for skill in template.skills:
            mapping.setdefault(skill, set()).add(template.topic)
    return {skill: frozenset(topics) for skill, topics in mapping.items()}


def _skill_value(skill: str, facts: CandidateFacts) -> tuple[float, str]:
    rules = get_rules()
    status = facts.skills_status.get(skill)
    if status:
        return rules.skill_value.get(status, rules.skill_value["declared"]), status
    parents = {s.id: s.parent for s in get_catalog().skills}
    parent = parents.get(skill)
    if parent and parent in facts.skills_status:
        return rules.skill_value["parent_only"], "parent_only"
    return 0.0, "missing"


def skills_component(
    facts: CandidateFacts, need: NeedSpec
) -> tuple[float, list[tuple[str, bool, float, str]]]:
    rules = get_rules()
    details = [(skill, True, *_skill_value(skill, facts)) for skill in need.required]
    details += [(skill, False, *_skill_value(skill, facts)) for skill in need.optional]
    total = sum(rules.required_weight if required else rules.optional_weight for _, required, _, _ in details)
    if not total:
        return 1.0, details
    value = (
        sum((rules.required_weight if req else rules.optional_weight) * v for _, req, v, _ in details) / total
    )
    return value, details


def topic_fit(facts: CandidateFacts, need: NeedSpec) -> float:
    topics_by_skill = skill_topics(facts.specialization)
    wanted = set().union(
        *(topics_by_skill.get(skill, frozenset()) for skill in need.required + need.optional)
    )
    scores = [s["score"] for topic, s in facts.topic_scores.items() if not wanted or topic in wanted]
    if not scores:
        scores = [s["score"] for s in facts.topic_scores.values()]
    return sum(scores) / len(scores) if scores else 0.0


def strength_component(facts: CandidateFacts, need: NeedSpec) -> float:
    """0.7·Φ((θ − cut_целевого_грейда)/0.6) + 0.3·topic_fit — θ на общей шкале специализации (§8.3)."""
    rules = get_rules().strength
    cut = get_blueprints().cut(need.grade)
    ability = normal_cdf((facts.theta - cut) / rules["scale"])
    return rules["ability_share"] * ability + (1 - rules["ability_share"]) * topic_fit(facts, need)


def conditions_component(facts: CandidateFacts, need: NeedSpec) -> tuple[float, float, float, list[str]]:
    """(значение, salary_fit, format_fit, причины жёстких фильтров)."""
    rules = get_rules().conditions
    hard: list[str] = []
    salary_fit = 1.0
    if facts.salary_min and need.salary_to and facts.salary_min > need.salary_to:
        over = (facts.salary_min - need.salary_to) / need.salary_to
        salary_fit = max(0.0, 1.0 - over / rules["salary_tolerance"])
        if over > rules["salary_tolerance"]:
            hard.append(f"Ожидания от {facts.salary_min:,} ₽ выше вилки более чем на 30%".replace(",", " "))
    format_fit = 1.0
    if need.work_format:
        if facts.work_formats and need.work_format not in facts.work_formats:
            format_fit = 0.0
            hard.append("Не подходит формат работы")
        elif need.work_format != "remote" and need.city and facts.city and facts.city != need.city:
            if not facts.relocation:
                format_fit = 0.0
                hard.append(f"Другой город ({facts.city}), переезд не рассматривает")
    value = rules["salary_share"] * salary_fit + rules["format_share"] * format_fit
    return value, salary_fit, format_fit, hard


def evaluate(facts: CandidateFacts, need: NeedSpec, labels: dict[str, str]) -> MatchResult | None:
    """labels: skill id → название, category → «Backend · Middle», topic id → название темы."""
    fit = category_fit(facts.specialization, facts.grade, need)
    if fit is None:
        return None
    rules = get_rules()
    skills, details = skills_component(facts, need)
    strength = strength_component(facts, need)
    conditions, salary_fit, format_fit, hard = conditions_component(facts, need)
    components = {
        "skills": round(skills, 4),
        "strength": round(strength, 4),
        "category": rules.category_fit[fit],
        "fsp": round(facts.fsp_score, 4),
        "fresh": round(facts.fresh, 4),
        "conditions": round(conditions, 4),
    }
    total = sum(rules.weights[name] * value for name, value in components.items())
    lines = explain(facts, need, fit, details, salary_fit, format_fit, labels)
    return MatchResult(round(100 * total), components, fit, lines, hard)


def explain(
    facts: CandidateFacts,
    need: NeedSpec,
    fit: Fit,
    details: list[tuple[str, bool, float, str]],
    salary_fit: float,
    format_fit: float,
    labels: dict[str, str],
) -> list[dict]:
    """Строки объяснения строятся из тех же компонентов, что и score (§8.4)."""
    lines: list[dict] = []
    percentile = f" ({round(facts.percentile * 100)}-й перцентиль)" if facts.percentile is not None else ""
    category = labels.get("category", "")
    if fit == "exact":
        lines.append(
            _line("positive", "category", f"Категория совпадает: {category}, подтверждено тестом{percentile}")
        )
    else:
        reason = {
            "adjacent_grade": "соседний грейд",
            "adjacent_specialization": "смежная специализация",
            "adjacent_both": "смежная специализация и соседний грейд",
        }[fit]
        lines.append(_line("neutral", "category", f"{category} — {reason}{percentile}"))

    topics_by_skill = skill_topics(facts.specialization)
    for skill, required, _value, status in details:
        name = labels.get(skill, skill)
        if status == "verified":
            topic = next(
                iter(sorted(topics_by_skill.get(skill, frozenset()) & set(facts.topic_scores))), None
            )
            topic_name = labels.get(f"topic:{topic}", topic)
            extra = f": «{topic_name}» {round(facts.topic_scores[topic]['score'] * 100)}%" if topic else ""
            lines.append(_line("positive", "test", f"{name} — проверено тестом{extra}"))
        elif status in {"fsp_confirmed", "task_confirmed"}:
            source = "ФСП" if status == "fsp_confirmed" else "заданием"
            lines.append(_line("positive", "skills", f"{name} — подтверждено {source}"))
        elif status == "declared":
            lines.append(_line("neutral", "skills", f"{name} — заявлено"))
        elif status == "parent_only":
            lines.append(_line("neutral", "skills", f"{name} — есть базовый навык, сам не указан"))
        elif required:
            lines.append(_line("warning", "skills", f"{name} — нет данных"))

    if facts.best_fsp:
        lines.append(_line("positive", "fsp", f"ФСП: {facts.best_fsp}"))
    if facts.fresh_days is not None and facts.fresh_days <= 30:
        lines.append(_line("neutral", "freshness", f"Свежий результат: {facts.fresh_days} дн. назад"))
    if salary_fit < 1.0 and facts.salary_min:
        lines.append(
            _line(
                "warning",
                "conditions",
                f"Ожидания от {facts.salary_min:,} ₽ — выше вилки (до {need.salary_to:,} ₽)".replace(
                    ",", " "
                ),
            )
        )
    if format_fit < 1.0:
        lines.append(_line("warning", "conditions", "Формат или город не совпадают с потребностью"))
    return _prioritize(lines)


def _line(kind: str, source: str, text: str) -> dict:
    return {"kind": kind, "source": source, "text": text}


def _prioritize(lines: list[dict]) -> list[dict]:
    """Категория, затем предупреждения (важно увидеть сразу), затем плюсы, нейтральное — в конце."""
    limit = get_rules().recommendations["max_explanation_lines"]
    head, rest = lines[:1], lines[1:]
    order = {"warning": 0, "positive": 1, "neutral": 2}
    rest.sort(key=lambda line: order[line["kind"]])
    warnings = [line for line in rest if line["kind"] == "warning"][:2]
    others = [line for line in rest if line["kind"] != "warning"]
    return (head + others[: limit - 1 - len(warnings)] + warnings)[:limit]
