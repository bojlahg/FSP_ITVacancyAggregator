"""Golden-кейсы ранжирования (§8.3–8.4): осмысленный порядок, а не только отсутствие падений."""

from app.modules.matching.scoring import CandidateFacts, NeedSpec, category_fit, evaluate, get_rules

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
