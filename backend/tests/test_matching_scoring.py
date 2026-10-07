"""Golden-кейсы ранжирования (§8.3–8.4): осмысленный порядок, а не только отсутствие падений."""

import pytest

from app.modules.matching.scoring import (
    CandidateFacts,
    NeedSpec,
    category_fit,
    evaluate,
    freshness_from_days,
    get_rules,
    vps,
)

NEED = NeedSpec(
    specialization="backend",
    grade="middle",
    required=("python", "postgresql", "kafka"),
    optional=("docker",),
    work_format="hybrid",
    city="Москва",
    salary_from=220_000,
    salary_to=280_000,
)
LABELS = {
    "python": "Python",
    "postgresql": "PostgreSQL",
    "kafka": "Kafka",
    "docker": "Docker",
    "category": "Backend · Middle",
    "topic:databases": "Базы данных",
}


def facts(candidate_id: int, **overrides) -> CandidateFacts:
    base = dict(
        candidate_id=candidate_id,
        specialization="backend",
        grade="middle",
        theta=0.7,
        percentile=0.6,
        topic_scores={"databases": {"score": 0.8, "items": 3}, "stack": {"score": 0.7, "items": 4}},
        skills_status={"python": "verified", "postgresql": "verified", "kafka": "declared"},
        fsp_score=0.0,
        fresh=0.8,
        fresh_days=10,
        salary_min=240_000,
        work_formats=["hybrid"],
        city="Москва",
        skill_scores={"postgresql": {"correct": 3, "items": 4}},
    )
    return CandidateFacts(**(base | overrides))


def score(item: CandidateFacts) -> int:
    return evaluate(item, NEED, LABELS).score


def test_weights_sum_to_one():
    assert abs(sum(get_rules().weights.values()) - 1.0) < 1e-9


def test_category_fit_levels():
    assert category_fit("backend", "middle", NEED) == "exact"
    assert category_fit("backend", "senior", NEED) == "adjacent_grade"
    assert category_fit("fullstack", "middle", NEED) == "adjacent_specialization"
    assert category_fit("fullstack", "junior", NEED) == "adjacent_both"
    assert category_fit("frontend", "middle", NEED) is None
    assert category_fit("backend", "intern", NEED) is None


def test_verified_skills_beat_declared():
    verified = facts(1, skills_status={"python": "verified", "postgresql": "verified", "kafka": "verified"})
    declared = facts(2, skills_status={"python": "declared", "postgresql": "declared", "kafka": "declared"})
    assert score(verified) > score(declared)


def test_stronger_test_result_ranks_higher():
    assert score(facts(1, theta=1.1)) > score(facts(2, theta=0.3))


def test_fsp_is_a_bonus_not_a_penalty():
    without = facts(1)
    with_fsp = facts(2, fsp_score=0.8, best_fsp="2 место из 412")
    assert score(with_fsp) > score(without)
    # Отсутствие ФСП не опускает кандидата ниже того, у кого хуже тест
    assert score(without) > score(facts(3, theta=0.25, fsp_score=0.3))


def test_missing_stack_is_not_compensated_by_fsp():
    no_stack = facts(1, skills_status={}, fsp_score=1.0)
    stack = facts(2, fsp_score=0.0)
    assert score(stack) > score(no_stack)


def test_exact_category_beats_adjacent_with_same_profile():
    assert score(facts(1)) > score(facts(2, grade="senior"))


def test_hard_filters_report_reasons():
    office_only = evaluate(facts(1, work_formats=["remote"]), NEED, LABELS)
    assert office_only.out_of_filter == ["Не подходит формат работы"]
    expensive = evaluate(facts(2, salary_min=400_000), NEED, LABELS)
    assert any("выше вилки" in reason for reason in expensive.out_of_filter)
    other_city = evaluate(facts(3, city="Казань", relocation=False), NEED, LABELS)
    assert other_city.out_of_filter
    relocating = evaluate(facts(4, city="Казань", relocation=True), NEED, LABELS)
    assert not relocating.out_of_filter


def test_explanation_matches_components():
    result = evaluate(facts(1, salary_min=300_000, fsp_score=0.5, best_fsp="2 место из 412"), NEED, LABELS)
    texts = [line["text"] for line in result.lines]
    assert texts[0].startswith("Категория совпадает: Backend · Middle")
    assert "PostgreSQL — проверено тестом: 3 из 4 заданий" in texts
    assert any(text.startswith("ФСП: 2 место") for text in texts)
    assert result.lines[-1]["kind"] == "warning" and "выше вилки" in result.lines[-1]["text"]
    assert result.components["conditions"] < 1.0


def test_score_is_deterministic_and_bounded():
    first = evaluate(facts(1), NEED, LABELS)
    second = evaluate(facts(1), NEED, LABELS)
    assert first.score == second.score
    assert 0 <= first.score <= 100


def test_freshness_half_life_golden():
    # §8.3: полураспад 90 дней (content/matching.yaml → freshness.half_life_days)
    assert freshness_from_days(0) == 1.0
    assert freshness_from_days(90) == pytest.approx(0.5)
    assert freshness_from_days(180) == pytest.approx(0.25)
    assert freshness_from_days(-5) == 1.0


def test_vps_golden():
    # §8.3: VPS = 0.60·перцентиль + 0.15·fsp + 0.15·fresh + 0.10·approach
    assert sum(get_rules().vps_weights.values()) == pytest.approx(1.0)
    assert vps(0.8, 0.5, 1.0, 0.4) == pytest.approx(0.48 + 0.075 + 0.15 + 0.04)
    assert vps(None, 0.0, 0.0, None) == 0.0


def test_stronger_within_grade_but_overqualified_drops():
    """§8.3: внутри грейда сильнее — выше; за порогом следующего грейда — штраф и предупреждение."""
    middle_strong = facts(1, theta=1.1)  # порог Senior — 1,2
    middle_weak = facts(2, theta=0.4)
    overqualified = facts(3, theta=2.2)
    assert score(middle_strong) > score(middle_weak)
    assert score(middle_strong) > score(overqualified)
    texts = [line["text"] for line in evaluate(overqualified, NEED, LABELS).lines]
    assert any("ближе к уровню Senior" in text for text in texts)
    # Нейтрально, а не как минус: кандидат сильнее нужного грейда, ему предлагают тест на грейд выше
    notes = [x for x in evaluate(overqualified, NEED, LABELS).lines if "ближе к уровню" in x["text"]]
    assert notes[0]["kind"] == "neutral"
    assert not any("ближе к уровню" in line["text"] for line in evaluate(middle_strong, NEED, LABELS).lines)


def test_top_grade_has_no_overqualification():
    senior_need = NeedSpec(**{**NEED.__dict__, "grade": "senior"})
    strong = evaluate(facts(1, grade="senior", theta=2.5), senior_need, LABELS)
    weaker = evaluate(facts(2, grade="senior", theta=1.5), senior_need, LABELS)
    assert strong.score > weaker.score


def test_salary_market_verdicts_golden():
    """§24: вилка против ожиданий категории — в рынке, ниже рынка, подозрительно выше, мало данных."""
    from app.modules.matching.scoring import salary_market

    expectations = [180_000, 200_000, 220_000, 250_000, 260_000, 300_000]  # медиана 235 000
    ok = salary_market(expectations, 200_000, 260_000)
    assert (ok.verdict, ok.coverage, ok.median) == ("ok", 0.833, 235_000)
    assert salary_market(expectations, 100_000, 150_000).verdict == "below_market"  # покрывает 0%
    assert salary_market(expectations, 500_000, 600_000).verdict == "suspicious_high"  # от ≥ 2 × медианы
    assert salary_market(expectations[:4], 200_000, 260_000).verdict == "unknown"  # меньше 5 ожиданий


# ---------- C2: частичный зачёт близких навыков (§8.3, content/skill_similarity.yaml) ----------

SIMILAR_LABELS = LABELS | {"mysql": "MySQL", "rabbitmq": "RabbitMQ"}


def test_similarity_table_is_valid():
    import yaml

    from app.modules.catalog.service import CONTENT_DIR, get_catalog

    ids = {skill.id for skill in get_catalog().skills}
    with (CONTENT_DIR / "skill_similarity.yaml").open(encoding="utf-8") as file:
        pairs = yaml.safe_load(file)["pairs"]
    assert 40 <= len(pairs) <= 100
    seen = set()
    for left, right, value in pairs:
        assert left in ids and right in ids, (left, right)
        assert left != right and 0 < value <= 1
        key = frozenset((left, right))
        assert key not in seen, (left, right)
        seen.add(key)


def test_similar_skill_partial_credit_golden(monkeypatch):
    # PostgreSQL ← проверенный MySQL: min(0.3, 0.7 · 1.0) = 0.3; Kafka ← заявленный RabbitMQ: 0.5 · 0.5 = 0.25
    # skills = (1.0 + 0.3 + 0.25 + 0.3·0) / 3.3
    candidate = facts(1, skills_status={"python": "verified", "mysql": "verified", "rabbitmq": "declared"})
    result = evaluate(candidate, NEED, SIMILAR_LABELS)
    assert result.components["skills"] == pytest.approx(1.55 / 3.3, abs=1e-4)
    texts = [line["text"] for line in result.lines]
    assert "PostgreSQL — нет, есть близкий MySQL (зачтено 30%)" in texts
    assert "Kafka — нет, есть близкий RabbitMQ (зачтено 25%)" in texts
    without_similar = evaluate(facts(2, skills_status={"python": "verified"}), NEED, SIMILAR_LABELS)
    assert result.score > without_similar.score
    # Близкий навык не дороже самого навыка: проверенный PostgreSQL выше проверенного MySQL
    exact = facts(3, skills_status={"python": "verified", "postgresql": "verified", "rabbitmq": "declared"})
    assert evaluate(exact, NEED, SIMILAR_LABELS).score > result.score

    monkeypatch.setitem(get_rules().skill_similarity, "enabled", False)
    disabled = evaluate(candidate, NEED, SIMILAR_LABELS)
    assert disabled.components["skills"] == pytest.approx(1.0 / 3.3, abs=1e-4)
    assert "PostgreSQL — нет данных" in [line["text"] for line in disabled.lines]


def test_similarity_does_not_change_market_status():
    from app.modules.matching.scoring import skill_status

    candidate = facts(1, skills_status={"mysql": "verified"})
    assert skill_status(candidate, "postgresql") == "missing"


def test_similarity_respects_cap_and_parent_only(monkeypatch):
    # Нужен CI/CD, у кандидата проверенный GitLab CI: min(0.3, 0.6 × 1.0) = 0.3 (без близости — 0: parent_only
    # работает только в сторону «есть родитель, нужен потомок»)
    need = NeedSpec(specialization="devops", grade="middle", required=("ci_cd",))
    candidate = facts(1, specialization="devops", skills_status={"gitlab_ci": "verified"})
    assert evaluate(candidate, need, {}).components["skills"] == pytest.approx(0.3)
    monkeypatch.setitem(get_rules().skill_similarity, "max_credit", 1.0)
    assert evaluate(candidate, need, {}).components["skills"] == pytest.approx(0.6)


# ---------- C1: вероятность принятия приглашения (§8.3.1) ----------


def test_acceptance_high_golden():
    # Логит: 0.2 + 4·(280 − 240)/240 + 0.3 (формат) = 1.1667 → p = 0.763
    accept = evaluate(facts(1), NEED, LABELS).acceptance
    assert accept.probability == pytest.approx(0.763, abs=1e-3)
    assert accept.level == "high"
    assert accept.text == (
        "Вероятность, что кандидат примет приглашение: высокая — вилка покрывает ожидания, "
        "формат работы совпадает"
    )


def test_acceptance_low_golden_with_decline_history():
    # Зарплата: 4·(280 − 320)/320 = −0.5, отказы по зарплате 3 из 4 → × 1.75 = −0.875;
    # формат +0.3; 3 активных приглашения −0.45. Логит −0.825 → p = 0.305
    candidate = facts(1, salary_min=320_000, active_invitations=3, declines={"salary": 3, "other": 1})
    accept = evaluate(candidate, NEED, LABELS).acceptance
    assert accept.probability == pytest.approx(0.305, abs=1e-3)
    assert accept.level == "low"
    assert accept.text == (
        "Вероятность, что кандидат примет приглашение: низкая — вилка ниже ожиданий (прошлые отказы — чаще "
        "из-за зарплаты), у кандидата уже есть активные приглашения (3)"
    )
    # Одного отказа мало для вывода: история не учитывается
    single = facts(2, salary_min=320_000, declines={"salary": 1})
    factors = {name: value for name, value, _ in evaluate(single, NEED, LABELS).acceptance.factors}
    assert factors["salary"] == pytest.approx(-0.5)


def test_acceptance_factors_direction():
    base = evaluate(facts(1), NEED, LABELS).acceptance.probability
    assert evaluate(facts(2, search_status="active"), NEED, LABELS).acceptance.probability > base
    relocating = evaluate(facts(3, city="Казань", relocation=True), NEED, LABELS).acceptance.probability
    assert relocating < base
    assert evaluate(facts(4, city="Казань"), NEED, LABELS).acceptance.probability < relocating
    assert evaluate(facts(5, declines={"not_looking": 2}), NEED, LABELS).acceptance.probability < base
    covered = evaluate(facts(6, salary_min=200_000), NEED, LABELS).acceptance
    assert covered.probability > base and "вся вилка не ниже ожиданий" in covered.text


def test_acceptance_is_shown_only_by_default(monkeypatch):
    unlikely = facts(1, salary_min=320_000, active_invitations=5)
    shown = evaluate(unlikely, NEED, LABELS)
    assert get_rules().acceptance["rank_weight"] == 0.0
    monkeypatch.setitem(get_rules().acceptance, "enabled", False)
    hidden = evaluate(unlikely, NEED, LABELS)
    assert hidden.acceptance is None and hidden.score == shown.score


def test_acceptance_multiplier_behind_flag(monkeypatch):
    likely, unlikely = facts(1, search_status="active"), facts(2, theta=0.9, active_invitations=5)
    assert score(unlikely) > score(likely)
    monkeypatch.setitem(get_rules().acceptance, "rank_weight", 0.5)
    result = evaluate(unlikely, NEED, LABELS)
    plain = sum(get_rules().weights[name] * value for name, value in result.components.items())
    assert result.score == round(100 * plain * (0.5 + 0.5 * result.acceptance.probability))
    assert score(likely) > score(unlikely)
