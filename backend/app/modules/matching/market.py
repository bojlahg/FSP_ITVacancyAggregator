"""Рынок категории для кандидата (§8.5): агрегаты по действующим потребностям и «что поможет».

Чистые функции без БД. Навыки оцениваются тем же skills-компонентом, что и score подбора (§8.3),
поэтому «подходящих потребностей станет больше на N» согласовано с выдачей работодателю.
"""

from collections import Counter
from dataclasses import dataclass, replace
from statistics import median

from app.modules.matching import scoring
from app.modules.matching.schemas import (
    CandidateMarketOut,
    MarketGroup,
    MarketSalary,
    MarketSkill,
    MarketSuggestion,
)

FITS = ("exact", "adjacent_grade", "adjacent_specialization", "adjacent_both")
CONFIRMED = {"verified", "fsp_confirmed", "task_confirmed"}


@dataclass(frozen=True)
class MarketNeed:
    """Потребность в выборке: employer_id нужен только для порога числа компаний и наружу не уходит."""

    employer_id: int
    published: bool
    spec: scoring.NeedSpec


def _limits() -> dict[str, float]:
    return scoring.get_rules().insights


def enough(needs: list[MarketNeed]) -> bool:
    """Агрегат можно показать: потребностей и компаний не меньше порогов (иначе узнаётся работодатель)."""
    limits = _limits()
    employers = {need.employer_id for need in needs}
    return len(needs) >= limits["min_needs"] and len(employers) >= limits["min_employers"]


def skills_match(facts: scoring.CandidateFacts, need: scoring.NeedSpec) -> bool:
    value, _ = scoring.skills_component(facts, need)
    return value >= _limits()["skills_match"]


def matching_count(facts: scoring.CandidateFacts, needs: list[MarketNeed]) -> int:
    return sum(skills_match(facts, need.spec) for need in needs)


def counterfactual(facts: scoring.CandidateFacts, needs: list[MarketNeed], skill: str, status: str) -> int:
    """На сколько больше потребностей подойдёт по навыкам, если у навыка будет статус status."""
    changed = replace(facts, skills_status={**facts.skills_status, skill: status})
    return matching_count(changed, needs) - matching_count(facts, needs)


def salary(needs: list[MarketNeed], candidate_min: int | None) -> MarketSalary:
    median_from = round(median(need.spec.salary_from for need in needs))
    median_to = round(median(need.spec.salary_to for need in needs))
    if not candidate_min:
        return MarketSalary(
            median_from=median_from,
            median_to=median_to,
            candidate_min=None,
            position="unknown",
            covered_share=None,
        )
    position = "below" if candidate_min < median_from else "above" if candidate_min > median_to else "within"
    covered = sum(need.spec.salary_to >= candidate_min for need in needs) / len(needs)
    return MarketSalary(
        median_from=median_from,
        median_to=median_to,
        candidate_min=candidate_min,
        position=position,
        covered_share=round(covered, 3),
    )


def top_skills(
    facts: scoring.CandidateFacts, needs: list[MarketNeed], names: dict[str, str]
) -> list[MarketSkill]:
    required = Counter(skill for need in needs for skill in set(need.spec.required))
    optional = Counter(skill for need in needs for skill in set(need.spec.optional))
    total = len(needs)
    ranked = sorted(
        set(required) | set(optional),
        key=lambda skill: (-(required[skill] + optional[skill]), -required[skill], skill),
    )
    return [
        MarketSkill(
            skill_id=skill,
            name=names.get(skill, skill),
            required_share=round(required[skill] / total, 3),
            optional_share=round(optional[skill] / total, 3),
            status=scoring.skill_status(facts, skill),
        )
        for skill in ranked[: int(_limits()["top_skills"])]
    ]


def suggestions(
    facts: scoring.CandidateFacts,
    needs: list[MarketNeed],
    skills: list[MarketSkill],
    confirmable: set[str],
) -> list[MarketSuggestion]:
    """Для навыков из топа, которых нет или они только заявлены: эффект подтверждения или указания в профиле.

    confirmable — навыки, которые проверяют тест и задания специализации кандидата (банк шаблонов).
    """
    result: list[tuple[int, float, MarketSuggestion]] = []
    for skill in skills:
        if skill.status in CONFIRMED:
            continue
        if skill.skill_id in confirmable:
            action, target = "confirm", "verified"
            text = f"Подтвердите {skill.name} тестом или заданием"
        elif skill.status != "declared":
            action, target = "declare", "declared"
            text = f"Если владеете {skill.name}, укажите навык в профиле"
        else:
            continue
        delta = counterfactual(facts, needs, skill.skill_id, target)
        if delta <= 0:
            continue
        text += f" — подходящих потребностей станет больше на {delta}"
        suggestion = MarketSuggestion(
            skill_id=skill.skill_id,
            name=skill.name,
            status=skill.status,
            action=action,
            extra_matches=delta,
            text=text,
        )
        result.append((delta, skill.required_share + skill.optional_share, suggestion))
    result.sort(key=lambda item: (-item[0], -item[1], item[2].skill_id))
    return [item[2] for item in result[: int(_limits()["max_suggestions"])]]


def insights(
    facts: scoring.CandidateFacts,
    needs: list[MarketNeed],
    names: dict[str, str],
    confirmable: set[str],
) -> CandidateMarketOut:
    """Счётчики по своей и соседним категориям видны всегда (компанию по ним не узнать); вилки, навыки
    и «что поможет» — только если выборка проходит порог enough().
    """
    by_fit: dict[str, list[MarketNeed]] = {fit: [] for fit in FITS}
    for need in needs:
        fit = scoring.category_fit(facts.specialization, facts.grade, need.spec)
        if fit is not None:
            by_fit[fit].append(need)
    groups = [
        MarketGroup(fit=fit, needs=len(items), vacancies=sum(need.published for need in items))
        for fit, items in by_fit.items()
    ]
    neighbourhood = [need for items in by_fit.values() for need in items]
    min_needs = int(_limits()["min_needs"])
    if enough(by_fit["exact"]):
        scope, pool = "category", by_fit["exact"]
    elif enough(neighbourhood):
        scope, pool = "neighbourhood", neighbourhood
    else:
        return CandidateMarketOut(
            category=None,
            groups=groups,
            scope=None,
            scope_needs=0,
            suppressed=True,
            min_needs=min_needs,
            salary=None,
            skills=[],
            matching_needs=None,
            suggestions=[],
        )
    skills = top_skills(facts, pool, names)
    return CandidateMarketOut(
        category=None,
        groups=groups,
        scope=scope,
        scope_needs=len(pool),
        suppressed=False,
        min_needs=min_needs,
        salary=salary(pool, facts.salary_min),
        skills=skills,
        matching_needs=matching_count(facts, neighbourhood),
        suggestions=suggestions(facts, neighbourhood, skills, confirmable),
    )
