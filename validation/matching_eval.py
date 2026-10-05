"""Качество подбора (§12.2 «Подбор»): синтетические потребности, истинная релевантность 0–3, P@k и nDCG@10.

Ранжирование «наш match» считается чистыми функциями продукта (app/modules/matching/scoring.py).
"""

import math
import random
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, replace

import numpy as np

from app.modules.catalog.service import get_catalog
from app.modules.expert import stats as expert_stats
from app.modules.matching.scoring import CandidateFacts, NeedSpec, evaluate, freshness_from_days, get_rules
from app.modules.testing.engine.bank import GRADE_ORDER
from seed import data
from validation.engine_sim import Attempt, Path
from validation.population import Person
from validation.stats import mean, ndcg_at_k, precision_at_k, spearman

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
        # C1–C3 (docs/research/README.md): вероятность принятия, близкие навыки, интервалы и разметка
        "acceptance": evaluate_acceptance(people, facts, needs, config),
        "similarity": similarity_ablation(people, facts, needs, config),
        "intervals": matching_intervals(rows, config),
        "expert_sim": simulated_labeling(people, facts, needs, config),
    }


# ---------- C1: вероятность принятия приглашения на синтетике (accept@5) ----------


@dataclass
class AcceptanceProfile:
    """Скрытые и наблюдаемые свойства кандидата для симуляции ответа на приглашение (§8.3.1).

    Наблюдаемое (search_status, active_invitations, declines) получает продукт; скрытое (истинная
    зарплатная планка, тип чувствительности, «на самом деле не ищу», личный сдвиг) — только «истина».
    """

    search_status: str
    active_invitations: int
    declines: dict[str, int]
    reservation: float
    sensitivity: str
    not_looking: bool
    intercept: float


def acceptance_profiles(people: list[Person], config: dict) -> dict[int, AcceptanceProfile]:
    cfg = config["acceptance"]
    rng = random.Random(f"acceptance:{config['seed']}")
    other_reasons = ["stack", "company", "other"]
    profiles = {}
    for person in people:
        sensitivity = rng.choices(list(cfg["sensitivity"]), weights=list(cfg["sensitivity"].values()))[0]
        active = rng.random() < cfg["active_share"]
        not_looking = not active and rng.random() < cfg["hidden_not_looking"]
        reasons: Counter = Counter()
        for _ in range(rng.choice(cfg["past_declines"])):
            if not_looking and rng.random() < cfg["reason_fidelity"]:
                reasons["not_looking"] += 1
            elif sensitivity != "none" and rng.random() < cfg["reason_fidelity"]:
                reasons[sensitivity] += 1
            else:
                reasons[rng.choice(other_reasons)] += 1
        profiles[person.pid] = AcceptanceProfile(
            search_status="active" if active else "open",
            active_invitations=rng.choice(cfg["active_invitations"]),
            declines=dict(reasons),
            reservation=person.salary_min * math.exp(rng.gauss(0.0, cfg["reservation_sd"])),
            sensitivity=sensitivity,
            not_looking=not_looking,
            intercept=rng.gauss(0.0, cfg["person_sd"]),
        )
    return profiles


def true_acceptance(person: Person, profile: AcceptanceProfile, need: NeedSpec, config: dict) -> float:
    """«Истинная» вероятность принятия: те же по природе факторы, но другая форма и скрытые величины.

    Предложение — середина вилки (продукт смотрит на верх), планка с шумом, чувствительность к зарплате
    или формату усиливает их эффект, «не ищу» скрыт. Коэффициенты — validation/config.yaml, acceptance.truth.
    """
    cfg = config["acceptance"]["truth"]
    offer = (need.salary_from + need.salary_to) / 2
    gap = max(-0.5, min(0.5, (offer - profile.reservation) / profile.reservation))
    utility = cfg["intercept"] + profile.intercept
    utility += cfg["salary"] * gap * (cfg["sensitive"] if profile.sensitivity == "salary" else 1.0)
    format_factor = cfg["sensitive"] if profile.sensitivity == "work_format" else 1.0
    if need.work_format and need.work_format not in person.work_formats:
        utility += cfg["format_mismatch"] * format_factor
    if need.work_format != "remote" and need.city and person.city != need.city:
        utility += (cfg["relocation"] if person.relocation else cfg["no_relocation"]) * format_factor
    if profile.search_status == "active":
        utility += cfg["active"]
    utility += cfg["busy"] * profile.active_invitations
    if profile.not_looking:
        utility += cfg["not_looking"]
    return 1.0 / (1.0 + math.exp(-utility))


@contextmanager
def _rule(section: str, key: str, value: float):
    """Временно поменять параметр content/matching.yaml — тот же объект, что читает scoring."""
    rules = getattr(get_rules(), section)
    before = rules[key]
    rules[key] = value
    try:
        yield
    finally:
        rules[key] = before


def _tiebreak(people: list[Person], config: dict) -> dict[int, float]:
    rng = random.Random(f"tiebreak:{config['seed']}")
    return {p.pid: rng.random() for p in people}


def evaluate_acceptance(
    people: list[Person], facts: dict[int, CandidateFacts], needs: list[Need], config: dict
) -> dict:
    """accept@5 — ожидаемая доля принявших приглашение в топ-5 (как InMail Accept у LinkedIn) для выдачи
    ITScout с множителем вероятности принятия разной силы, категории по тесту и ключевых слов (§8.3.1)."""
    cfg = config["matching"]
    profiles = acceptance_profiles(people, config)
    by_pid = {p.pid: p for p in people}
    observed = {
        pid: replace(
            item,
            search_status=profiles[pid].search_status,
            active_invitations=profiles[pid].active_invitations,
            declines=profiles[pid].declines,
        )
        for pid, item in facts.items()
    }
    tiebreak = _tiebreak(people, config)
    variants = [("match_grouped", 0.0)] + [("match_grouped", w) for w in config["acceptance"]["rank_weights"]]
    variants += [("test_category", 0.0), ("keywords", 0.0)]
    rows: dict[str, list[dict]] = {}
    predicted, actual = [], []
    for need in needs:
        truth = {p.pid: relevance(p, need.spec, config) for p in people}
        for ranker, weight in variants:
            name = f"{ranker}_w{weight:g}" if weight else ranker
            with _rule("acceptance", "rank_weight", weight):
                order = rank(ranker, need.spec, people, observed, tiebreak)[:5]
            accept = [true_acceptance(by_pid[pid], profiles[pid], need.spec, config) for pid in order]
            rows.setdefault(name, []).append(
                {
                    "accept@5": mean(accept),
                    "p@5": precision_at_k([truth[pid] for pid in order], 5, cfg["relevant_from"]),
                    # Ожидаемое число точных совпадений, принявших приглашение, в топ-5 потребности
                    "hires@5": sum(p for p, pid in zip(accept, order, strict=True) if truth[pid] >= 3),
                }
            )
        # Качество самой оценки: все пары, попавшие в выдачу потребности (категория и соседние)
        for pid, item in observed.items():
            result = evaluate(item, need.spec, {})
            if result is not None and result.acceptance is not None:
                predicted.append(result.acceptance.probability)
                actual.append(true_acceptance(by_pid[pid], profiles[pid], need.spec, config))
    return {
        "summary": {
            name: {metric: mean([row[metric] for row in values]) for metric in ("accept@5", "p@5", "hires@5")}
            for name, values in rows.items()
        },
        "spearman": spearman(predicted, actual),
        "pairs": len(predicted),
        "mean_true": mean(actual),
        "rank_weight": get_rules().acceptance["rank_weight"],
    }


# ---------- C2: вклад частичного зачёта близких навыков ----------


def similarity_ablation(
    people: list[Person], facts: dict[int, CandidateFacts], needs: list[Need], config: dict
) -> dict:
    """P@5 и nDCG@10 выдачи по категориям с зачётом близких навыков и без него (skill_similarity.enabled)."""
    cfg = config["matching"]
    tiebreak = _tiebreak(people, config)
    result = {}
    for enabled in (True, False):
        values: dict[str, list[float]] = {"p@5": [], "ndcg@10": []}
        with _rule("skill_similarity", "enabled", enabled):
            for need in needs:
                truth = {p.pid: relevance(p, need.spec, config) for p in people}
                rels = [truth[pid] for pid in rank("match_grouped", need.spec, people, facts, tiebreak)]
                values["p@5"].append(precision_at_k(rels, 5, cfg["relevant_from"]))
                values["ndcg@10"].append(ndcg_at_k(rels, list(truth.values()), 10))
        result["on" if enabled else "off"] = {metric: mean(v) for metric, v in values.items()}
    return result


# ---------- C3: интервалы, парное сравнение и симуляция экспертной разметки ----------


def matching_intervals(rows: list[dict], config: dict) -> dict:
    """95% bootstrap-интервалы по потребностям и парное сравнение выдачи ITScout с базовыми линиями."""
    cfg = config["expert_sim"]
    resamples, seed = cfg["resamples"], config["seed"]
    intervals = {
        f"{ranker}_{metric}": expert_stats.bootstrap_ci(
            [row[f"{ranker}_{metric}"] for row in rows], resamples, seed
        )
        for ranker in RANKERS
        for metric in ("p@5", "ndcg@10")
    }
    comparisons = {}
    for baseline in ("test_category", "keywords"):
        for metric in ("p@5", "ndcg@10"):
            ours = [row[f"match_grouped_{metric}"] for row in rows]
            other = [row[f"{baseline}_{metric}"] for row in rows]
            paired = expert_stats.paired_bootstrap(ours, other, resamples, seed)
            wins, losses, ties, sign_p = expert_stats.sign_test(ours, other)
            diffs = [a - b for a, b in zip(ours, other, strict=True)]
            sd = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
            comparisons[f"{baseline}_{metric}"] = {
                "difference": paired[0] if paired else None,
                "ci": list(paired[1:3]) if paired else None,
                "p_value": paired[3] if paired else None,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "sign_p": sign_p,
                "sd_diff": sd,
                "needs_for_power": expert_stats.needs_for_power(sd, cfg["detect_difference"]),
            }
    return {"intervals": intervals, "comparisons": comparisons}


def simulated_labeling(
    people: list[Person], facts: dict[int, CandidateFacts], needs: list[Need], config: dict
) -> dict:
    """Цель «20 потребностей / 200 меток» с шумными экспертами — теми же функциями, что /expert/summary.

    Эксперт видит истинную релевантность с ошибкой (σ из config), оценка округляется в 0–3; часть пар
    размечают двое. Показывает, какой ширины интервалы и какую κ ждать на целевом объёме разметки.
    """
    cfg = config["expert_sim"]
    rng = random.Random(f"expert:{config['seed']}")
    tiebreak = _tiebreak(people, config)
    by_pid = {p.pid: p for p in people}

    def rate(true: int) -> int:
        return max(0, min(3, round(true + rng.gauss(0.0, cfg["rater_sd"]))))

    precision: dict[str, list[float]] = {"ours": [], "keyword": []}
    ndcg: dict[str, list[float]] = {"ours": [], "keyword": []}
    rater_pairs: list[tuple[int, int]] = []
    units: list[list[int]] = []
    for need in needs[: cfg["needs"]]:
        ours = rank("match_grouped", need.spec, people, facts, tiebreak)[: cfg["top_k"]]
        keyword = rank("keywords", need.spec, people, facts, tiebreak)[: cfg["top_k"]]
        means = {}
        for pid in dict.fromkeys(ours + keyword):
            true = relevance(by_pid[pid], need.spec, config)
            values = [rate(true)]
            if rng.random() < cfg["double_share"]:
                values.append(rate(true))
                rater_pairs.append((values[0], values[1]))
            units.append(values)
            means[pid] = sum(values) / len(values)
        for name, order in (("ours", ours), ("keyword", keyword)):
            top = [means[pid] for pid in order[:5]]
            precision[name].append(sum(m >= cfg["relevant_from"] for m in top) / 5)
            ndcg[name].append(expert_stats.ndcg(top, list(means.values()), 5) or 0.0)
    resamples, seed = cfg["resamples"], config["seed"]
    kappa = expert_stats.weighted_kappa(rater_pairs)
    return {
        "needs": len(precision["ours"]),
        "labels": sum(len(values) for values in units),
        "precision": {name: mean(values) for name, values in precision.items()},
        "precision_ci": {
            name: expert_stats.bootstrap_ci(v, resamples, seed) for name, v in precision.items()
        },
        "ndcg": {name: mean(values) for name, values in ndcg.items()},
        "ndcg_ci": {name: expert_stats.bootstrap_ci(v, resamples, seed) for name, v in ndcg.items()},
        "precision_paired": expert_stats.paired_bootstrap(
            precision["ours"], precision["keyword"], resamples, seed
        ),
        "ndcg_paired": expert_stats.paired_bootstrap(ndcg["ours"], ndcg["keyword"], resamples, seed),
        "kappa": kappa,
        "kappa_level": expert_stats.landis_koch(kappa),
        "alpha": expert_stats.krippendorff_alpha(units),
        "double_pairs": len(rater_pairs),
    }
