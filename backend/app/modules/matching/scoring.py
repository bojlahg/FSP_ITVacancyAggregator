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
    skill_similarity: dict[str, float]
    acceptance: dict[str, float]
    freshness: dict[str, float]
    vps_weights: dict[str, float]
    market: dict[str, float]
    expert: dict[str, float]
    insights: dict[str, float]
    recommendations: dict[str, int]


@lru_cache
def get_rules() -> MatchingRules:
    with (CONTENT_DIR / "matching.yaml").open(encoding="utf-8") as file:
        return MatchingRules.model_validate(yaml.safe_load(file))


@lru_cache
def similar_skills() -> dict[str, dict[str, float]]:
    """Замороженная таблица близости навыков (content/skill_similarity.yaml), симметричная."""
    with (CONTENT_DIR / "skill_similarity.yaml").open(encoding="utf-8") as file:
        pairs = yaml.safe_load(file)["pairs"]
    table: dict[str, dict[str, float]] = {}
    for left, right, value in pairs:
        table.setdefault(left, {})[right] = float(value)
        table.setdefault(right, {})[left] = float(value)
    return table


def freshness_from_days(days: float) -> float:
    """fresh = 0.5^(дней с последнего проверенного действия / полураспад) — §8.3."""
    return 0.5 ** (max(days, 0.0) / get_rules().freshness["half_life_days"])


def vps(percentile: float | None, fsp: float, fresh: float, approach: float | None) -> float:
    """Сила подтверждённого профиля внутри категории — §8.3."""
    w = get_rules().vps_weights
    value = (
        w["percentile"] * (percentile or 0.0)
        + w["fsp"] * fsp
        + w["fresh"] * fresh
        + w["approach"] * (approach or 0.0)
    )
    return round(value, 4)


MarketVerdict = Literal["ok", "below_market", "suspicious_high", "unknown"]


@dataclass(frozen=True)
class SalaryMarket:
    verdict: MarketVerdict
    coverage: float | None
    median: int | None


def salary_market(expectations: list[int], salary_from: int, salary_to: int) -> SalaryMarket:
    """Вилка против ожиданий категории: доля покрытых ожиданий и медиана (§24, фиктивные вакансии)."""
    rules = get_rules().market
    known = sorted(s for s in expectations if s)
    if len(known) < rules["min_candidates"]:
        return SalaryMarket("unknown", None, None)
    coverage = round(sum(s <= salary_to for s in known) / len(known), 3)
    middle = len(known) // 2
    median = known[middle] if len(known) % 2 else (known[middle - 1] + known[middle]) // 2
    if salary_from >= rules["high_ratio"] * median:
        return SalaryMarket("suspicious_high", coverage, median)
    if coverage < rules["low_coverage"]:
        return SalaryMarket("below_market", coverage, median)
    return SalaryMarket("ok", coverage, median)


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
    skill_scores: dict[str, dict] = field(default_factory=dict)
    # Для вероятности принятия приглашения (§8.3.1)
    search_status: str | None = None
    active_invitations: int = 0
    declines: dict[str, int] = field(default_factory=dict)


AcceptanceLevel = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class Acceptance:
    probability: float
    level: AcceptanceLevel
    text: str
    factors: tuple[tuple[str, float, str], ...]


@dataclass
class MatchResult:
    score: int
    components: dict[str, float]
    fit: Fit
    lines: list[dict]
    out_of_filter: list[str]
    acceptance: Acceptance | None = None


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


def _status_value(status: str) -> float:
    values = get_rules().skill_value
    return values.get(status, values["declared"])


def _similar_credit(skill: str, facts: CandidateFacts) -> tuple[float, str | None]:
    """Лучший зачёт за близкий навык: близость × ценность его статуса, не больше max_credit (§8.3)."""
    rules = get_rules().skill_similarity
    if not rules.get("enabled", 0):
        return 0.0, None
    best, source = 0.0, None
    for other, similarity in sorted(similar_skills().get(skill, {}).items()):
        status = facts.skills_status.get(other)
        if status and similarity >= rules["min_similarity"]:
            credit = min(rules["max_credit"], similarity * _status_value(status))
            if credit > best:
                best, source = credit, other
    return best, source


def _skill_value(skill: str, facts: CandidateFacts) -> tuple[float, str, str | None]:
    """(ценность, статус, близкий навык кандидата — только для статуса similar)."""
    status = facts.skills_status.get(skill)
    if status:
        return _status_value(status), status, None
    parents = {s.id: s.parent for s in get_catalog().skills}
    parent = parents.get(skill)
    base = get_rules().skill_value["parent_only"] if parent and parent in facts.skills_status else 0.0
    credit, similar = _similar_credit(skill, facts)
    if similar is not None and credit > base:
        return credit, "similar", similar
    if base:
        return base, "parent_only", None
    return 0.0, "missing", None


def skill_status(facts: CandidateFacts, skill: str) -> str:
    """Статус навыка так, как его видит skills-компонент: verified … declared, parent_only, missing.

    Зачёт за близкий навык — не сам навык: для кандидата («Рынок категории») это по-прежнему «нет».
    """
    status = _skill_value(skill, facts)[1]
    return "missing" if status == "similar" else status


# (навык, обязательный, ценность v, статус, близкий навык кандидата — для статуса similar)
SkillDetail = tuple[str, bool, float, str, str | None]


def skills_component(facts: CandidateFacts, need: NeedSpec) -> tuple[float, list[SkillDetail]]:
    rules = get_rules()
    details = [(skill, True, *_skill_value(skill, facts)) for skill in need.required]
    details += [(skill, False, *_skill_value(skill, facts)) for skill in need.optional]
    weights = [rules.required_weight if detail[1] else rules.optional_weight for detail in details]
    total = sum(weights)
    if not total:
        return 1.0, details
    value = sum(w * detail[2] for w, detail in zip(weights, details, strict=True)) / total
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


def overqualification(facts: CandidateFacts, need: NeedSpec) -> float:
    """Насколько θ за порогом следующего грейда: max(0, 2·Φ((θ − cut_{G+1})/scale) − 1); 0 для верхнего."""
    blueprints = get_blueprints()
    higher = blueprints.next_grade(need.grade)
    if higher is None:
        return 0.0
    # Только за порогом: до cut_{G+1} более сильный остаётся выше (требование ТЗ к порядку внутри категории)
    over = normal_cdf((facts.theta - blueprints.cut(higher)) / get_rules().strength["scale"])
    return max(0.0, 2 * over - 1)


def strength_component(facts: CandidateFacts, need: NeedSpec) -> float:
    """§8.3: 0.7·ability + 0.3·topic_fit; ability = Φ((θ − cut_G)/0.6) − λ·overqualification.

    Внутри грейда более сильный выше (требование ТЗ), а кандидат, по тесту уже переросший нужный грейд,
    получает штраф λ: работодатель ищет этот грейд, а не следующий.
    """
    rules = get_rules().strength
    cut = get_blueprints().cut(need.grade)
    ability = normal_cdf((facts.theta - cut) / rules["scale"])
    ability = max(0.0, ability - rules["overqualified_penalty"] * overqualification(facts, need))
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
            pct = round(rules["salary_tolerance"] * 100)
            hard.append(f"Ожидания от {facts.salary_min:,} ₽ выше вилки более чем на {pct}%".replace(",", " "))
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


def acceptance_factors(facts: CandidateFacts, need: NeedSpec) -> list[tuple[str, float, str]]:
    """Вклады в логит вероятности принятия: (фактор, вклад, причина по-русски) — §8.3.1."""
    rules = get_rules().acceptance
    factors: list[tuple[str, float, str]] = []
    declines = sum(facts.declines.values())
    shares = (
        {reason: count / declines for reason, count in facts.declines.items()}
        if declines >= rules["min_declines"]
        else {}
    )

    def amplified(reason: str) -> float:
        return 1.0 + rules["decline_amplify"] * shares.get(reason, 0.0)

    def history(reason: str, name: str) -> str:
        return f" (прошлые отказы — чаще из-за {name})" if shares.get(reason, 0.0) >= 0.5 else ""

    if facts.salary_min and need.salary_to:
        clip = rules["salary_clip"]
        gap = max(-clip, min(clip, (need.salary_to - facts.salary_min) / facts.salary_min))
        covered = need.salary_from >= facts.salary_min
        value = (rules["salary_slope"] * gap + (rules["salary_floor_bonus"] if covered else 0.0)) * amplified(
            "salary"
        )
        if gap < 0:
            text = "вилка ниже ожиданий" + history("salary", "зарплаты")
        else:
            text = "вся вилка не ниже ожиданий" if covered else "вилка покрывает ожидания"
        factors.append(("salary", value, text))

    if need.work_format and facts.work_formats:
        if need.work_format in facts.work_formats:
            factors.append(("format", rules["format_match"], "формат работы совпадает"))
        else:
            text = "формат работы не совпадает" + history("work_format", "формата")
            factors.append(("format", rules["format_mismatch"] * amplified("work_format"), text))
    if need.work_format != "remote" and need.city and facts.city and facts.city != need.city:
        if facts.relocation:
            value, text = rules["relocation"], "нужен переезд из другого города"
        else:
            value, text = rules["no_relocation"], "другой город, переезд не рассматривает"
        factors.append(("city", value * amplified("work_format"), text))

    if facts.search_status == "active":
        factors.append(("search", rules["active_search"], "кандидат активно ищет работу"))
    if facts.active_invitations:
        count = min(facts.active_invitations, int(rules["active_invitations_cap"]))
        text = f"у кандидата уже есть активные приглашения ({facts.active_invitations})"
        factors.append(("invitations", rules["active_invitation"] * count, text))
    if shares.get("not_looking"):
        text = "среди прошлых отказов есть «сейчас не ищу»"
        factors.append(("not_looking", rules["not_looking"] * shares["not_looking"], text))
    return factors


ACCEPTANCE_LEVEL_NAMES = {"high": "высокая", "medium": "средняя", "low": "низкая"}


def acceptance(facts: CandidateFacts, need: NeedSpec) -> Acceptance:
    """p = σ(intercept + Σ вкладов); текст — из тех же вкладов, поэтому совпадает с числом (§8.3.1)."""
    rules = get_rules().acceptance
    factors = acceptance_factors(facts, need)
    probability = 1.0 / (1.0 + math.exp(-(rules["intercept"] + sum(value for _, value, _ in factors))))
    level: AcceptanceLevel = "low"
    if probability >= rules["high_from"]:
        level = "high"
    elif probability >= rules["medium_from"]:
        level = "medium"
    if level == "high":
        reasons = sorted((f for f in factors if f[1] > 0), key=lambda f: -f[1])
    elif level == "low":
        reasons = sorted((f for f in factors if f[1] < 0), key=lambda f: f[1])
    else:
        reasons = sorted(factors, key=lambda f: -abs(f[1]))
    because = ", ".join(text for _, _, text in reasons[:2]) or "явных причин за или против нет"
    text = f"Вероятность, что кандидат примет приглашение: {ACCEPTANCE_LEVEL_NAMES[level]} — {because}"
    return Acceptance(round(probability, 3), level, text, tuple(factors))


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
    accept = acceptance(facts, need) if rules.acceptance.get("enabled", 0) else None
    weight = rules.acceptance.get("rank_weight", 0.0)
    if accept is not None and weight > 0:
        # Множитель за флагом (§8.3.1): тот же accept уходит в ответ — строка и score не расходятся
        total *= (1 - weight) + weight * accept.probability
    lines = explain(facts, need, fit, details, salary_fit, format_fit, labels)
    return MatchResult(round(100 * total), components, fit, lines, hard, accept)


def explain(
    facts: CandidateFacts,
    need: NeedSpec,
    fit: Fit,
    details: list[SkillDetail],
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

    # Та же величина, что штрафует ability в strength_component: объяснение совпадает со score
    if get_rules().strength["overqualified_penalty"] > 0 and overqualification(facts, need) >= 0.3:
        higher = get_blueprints().next_grade(need.grade) or ""
        name = next((g.name for g in get_catalog().grades if g.slug.value == higher), higher)
        text = f"По тесту уже ближе к уровню {name} — задачи и ожидания могут быть выше"
        lines.append(_line("warning", "test", text))

    for skill, required, value, status, similar in details:
        name = labels.get(skill, skill)
        if status == "verified":
            stats = facts.skill_scores.get(skill)
            extra = f": {int(stats['correct'])} из {stats['items']} заданий" if stats else ""
            lines.append(_line("positive", "test", f"{name} — проверено тестом{extra}"))
        elif status in {"fsp_confirmed", "task_confirmed"}:
            source = "ФСП" if status == "fsp_confirmed" else "заданием"
            lines.append(_line("positive", "skills", f"{name} — подтверждено {source}"))
        elif status == "declared":
            lines.append(_line("neutral", "skills", f"{name} — заявлено"))
        elif status == "similar":
            other = labels.get(similar or "", similar or "")
            text = f"{name} — нет, есть близкий {other} (зачтено {round(value * 100)}%)"
            lines.append(_line("neutral", "skills", text))
        elif status == "parent_only":
            lines.append(_line("neutral", "skills", f"{name} — есть базовый навык, сам не указан"))
        elif required:
            lines.append(_line("warning", "skills", f"{name} — нет данных"))

    if facts.best_fsp:
        # Без вклада в score (ФСП не по профилю или владение не подтверждено) — нейтральная строка
        lines.append(_line("positive" if facts.fsp_score > 0 else "neutral", "fsp", f"ФСП: {facts.best_fsp}"))
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
