"""Качество подбора (§12.2 «Подбор»): синтетические потребности, истинная релевантность 0–3, P@k и nDCG@10.

Ранжирование «наш match» считается чистыми функциями продукта (app/modules/matching/scoring.py).
"""

import random
from dataclasses import dataclass

from app.modules.catalog.service import get_catalog
from app.modules.matching.scoring import CandidateFacts, NeedSpec, evaluate, freshness_from_days, get_rules
from app.modules.testing.engine.bank import GRADE_ORDER
from seed import data
from validation.engine_sim import Attempt, Path
from validation.population import Person
from validation.stats import mean, ndcg_at_k, precision_at_k

# match_grouped — выдача по умолчанию (группы категорий, внутри по score); match — «общий топ» по score;
# test_category / declared_grade — категория по тесту или заявленный грейд, внутри — ключевые слова
# резюме; keywords — только ключевые слова резюме
RANKERS = ("match_grouped", "match", "test_category", "declared_grade", "keywords")
# Порядок групп категорий — как FIT_ORDER в app/modules/matching/service.py
FIT_ORDER = {"exact": 0, "adjacent_grade": 1, "adjacent_specialization": 2, "adjacent_both": 3}


@dataclass
class Need:
    spec: NeedSpec
    label: str


def build_needs(config: dict) -> list[Need]:
    cfg = config["matching"]
    rng = random.Random(f"needs:{config['seed']}")
    specs = sorted(data.SPEC_STACKS)
    needs = []
    for index in range(cfg["needs"]):
        spec = specs[index % len(specs)]
        grade = rng.choice(cfg["need_grades"])
        module = rng.choice(sorted(data.SPEC_STACKS[spec]))
        stack = data.SPEC_STACKS[spec][module]
        required = rng.sample(stack, rng.randint(*cfg["required"]))
        others = sorted({s for m in data.SPEC_STACKS[spec].values() for s in m} - set(required))
        optional = rng.sample(others, min(len(others), rng.randint(*cfg["optional"])))
        low, high = data.SALARY[grade]
        factor = data.SPEC_SALARY_FACTOR[spec]
        work_format = rng.choice(["remote", "hybrid", "office"])
        needs.append(
            Need(
                NeedSpec(
                    specialization=spec,
                    grade=grade,
                    required=tuple(required),
                    optional=tuple(optional),
                    work_format=work_format,
                    city="Москва",
                    salary_from=int(low * factor) * 1000,
                    salary_to=int(high * factor) * 1000,
                ),
                f"{spec} · {grade} · {', '.join(required)}",
            )
        )
    return needs


def category_attempt(path: Path) -> Attempt | None:
    """Попытка, которая выдала категорию (последняя непроваленная на грейд категории)."""
    for attempt in reversed(path.attempts):
        if attempt.grade == path.category and attempt.decision != "fail":
            return attempt
    return None


def build_facts(people: list[Person], paths: dict[int, Path], config: dict) -> dict[int, CandidateFacts]:
    facts: dict[int, CandidateFacts] = {}
    for person in people:
        path = paths[person.pid]
        attempt = category_attempt(path)
        if attempt is None:
            continue
        status = dict.fromkeys(person.resume_stack, "declared")
        status.update(dict.fromkeys(attempt.summary.verified_skills, "verified"))
        facts[person.pid] = CandidateFacts(
            candidate_id=person.pid,
            specialization=person.spec,
            grade=path.category,
            theta=attempt.theta,
            percentile=None,
            topic_scores=attempt.summary.topic_scores,
            skills_status=status,
            fsp_score=person.fsp_score,
            has_fsp=person.has_fsp,
            fresh=freshness_from_days(person.fresh_days),
            fresh_days=person.fresh_days,
            salary_min=person.salary_min,
            work_formats=list(person.work_formats),
            city=person.city,
            relocation=person.relocation,
            skill_scores=attempt.summary.skill_scores,
        )
    by_category: dict[tuple[str, str], list[CandidateFacts]] = {}
    for item in facts.values():
        by_category.setdefault((item.specialization, item.grade), []).append(item)
    for members in by_category.values():
        ordered = sorted(members, key=lambda f: f.theta)
        for rank, item in enumerate(ordered):
            item.percentile = (rank + 0.5) / len(ordered)
    return facts


def _adjacent(spec: str) -> set[str]:
    return next((set(s.adjacent) for s in get_catalog().specializations if s.slug == spec), set())


def relevance(person: Person, need: NeedSpec, config: dict) -> int:
    """Истинная релевантность 0–3 из истинных специализации, грейда и стека (а не из теста или резюме)."""
    if person.true_grade is None:
        return 0
    same = person.spec == need.specialization
    near = person.spec in _adjacent(need.specialization)
    distance = abs(GRADE_ORDER.index(person.true_grade) - GRADE_ORDER.index(need.grade))
    if same and distance == 0:
        value = 3
    elif (same and distance == 1) or (near and distance == 0):
        value = 2
    elif near and distance == 1:
        value = 1
    else:
        return 0
    coverage = sum(skill in person.true_stack for skill in need.required) / max(len(need.required), 1)
    if coverage < config["matching"]["coverage_threshold"]:
        value -= 1
    return max(value, 0)


def _keywords(person: Person, need: NeedSpec) -> float:
    resume = set(person.resume_stack)
    return sum(1.0 for s in need.required if s in resume) + sum(0.3 for s in need.optional if s in resume)


def rank(
    ranker: str,
    need: NeedSpec,
    people: list[Person],
    facts: dict[int, CandidateFacts],
    tiebreak: dict[int, float],
) -> list[int]:
    if ranker in {"match", "match_grouped"}:
        scored = []
        for pid, item in facts.items():
            result = evaluate(item, need, {})
            if result is not None:
                # Вне фильтров — после основной выдачи; при равенстве ФСП, свежесть (как в service.py)
                group = FIT_ORDER[result.fit] if ranker == "match_grouped" else 0
                key = (bool(result.out_of_filter), group, -result.score, -item.fsp_score, -item.fresh, pid)
                scored.append((key, pid))
        return [pid for _, pid in sorted(scored)]

    def claimed(p: Person) -> bool:
        if ranker == "test_category":
            item = facts.get(p.pid)
            return (
                item is not None and item.specialization == need.specialization and item.grade == need.grade
            )
        if ranker == "declared_grade":
            return p.spec == need.specialization and p.declared == need.grade
        return True

    return [
        p.pid for p in sorted(people, key=lambda p: (not claimed(p), -_keywords(p, need), tiebreak[p.pid]))
    ]


def evaluate_matching(people: list[Person], paths: dict[int, Path], config: dict) -> dict:
    cfg = config["matching"]
    facts = build_facts(people, paths, config)
    rng = random.Random(f"tiebreak:{config['seed']}")
    tiebreak = {p.pid: rng.random() for p in people}
    by_pid = {p.pid: p for p in people}
    needs = build_needs(config)
    rows = []
    for need in needs:
        truth = {p.pid: relevance(p, need.spec, config) for p in people}
        all_rel = list(truth.values())
        row = {"need": need.label, "relevant": sum(r >= cfg["relevant_from"] for r in all_rel)}
        for ranker in RANKERS:
            order = rank(ranker, need.spec, people, facts, tiebreak)
            rels = [truth[pid] for pid in order]
            for k in cfg["top_k"]:
                row[f"{ranker}_p@{k}"] = precision_at_k(rels, k, cfg["relevant_from"])
            row[f"{ranker}_ndcg@10"] = ndcg_at_k(rels, all_rel, 10)
            row[f"{ranker}_overqualified@10"] = mean(
                [
                    by_pid[pid].true_grade is not None
                    and GRADE_ORDER.index(by_pid[pid].true_grade) > GRADE_ORDER.index(need.spec.grade)
                    for pid in order[:10]
                ]
            )
        rows.append(row)
    metrics = [f"p@{k}" for k in cfg["top_k"]] + ["ndcg@10", "overqualified@10"]
    summary = {
        ranker: {metric: mean([row[f"{ranker}_{metric}"] for row in rows]) for metric in metrics}
        for ranker in RANKERS
    }
    rules = get_rules()
    return {
        "needs": rows,
        "summary": summary,
        "metrics": metrics,
        "with_category": len(facts),
        "rules": {
            "category_weight": rules.weights["category"],
            "adjacent_grade_fit": rules.category_fit["adjacent_grade"],
        },
    }
