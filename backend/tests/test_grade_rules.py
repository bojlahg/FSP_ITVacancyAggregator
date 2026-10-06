"""Все переходы из таблицы §6.3."""

from datetime import UTC, datetime, timedelta

from app.modules.categories.rules import AttemptRecord, CurrentCategory, RuleConfig, decide

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)
CONFIG = RuleConfig(cooldown_days=90, failed_retry_days=30)


def attempt(grade, result, days_ago, purpose="calibration", status="completed"):
    return AttemptRecord(grade, purpose, status, result, NOW - timedelta(days=days_ago))


def current(grade, result="pass", days_ago=1):
    return CurrentCategory(grade, result, NOW - timedelta(days=days_ago))


def test_calibration_without_history_allows_any_grade():
    for grade in ("intern", "junior", "middle", "senior"):
        assert decide(grade, NOW, None, [], CONFIG).allowed


def test_calibration_fail_allows_lower_immediately_but_blocks_same_for_30_days():
    history = [attempt("middle", "fail", 0)]
    assert decide("junior", NOW, None, history, CONFIG).allowed
    blocked = decide("middle", NOW, None, history, CONFIG)
    assert not blocked.allowed and blocked.code == "grade_cooldown"
    assert blocked.available_at == history[0].started_at + timedelta(days=30)
    assert decide("middle", NOW + timedelta(days=31), None, history, CONFIG).allowed


def test_in_progress_attempt_blocks_new_one():
    history = [attempt("junior", None, 0, status="in_progress")]
    assert decide("junior", NOW, None, history, CONFIG).code == "attempt_in_progress"


def test_confident_pass_gives_one_immediate_upgrade():
    history = [attempt("middle", "confident_pass", 0)]
    category = current("middle", "confident_pass", days_ago=0)
    decision = decide("senior", NOW, category, history, CONFIG)
    assert decision.allowed and decision.purpose == "upgrade"

    used = history + [attempt("senior", "fail", 0, purpose="upgrade")]
    again = decide("senior", NOW + timedelta(minutes=5), category, used, CONFIG)
    assert not again.allowed and again.code == "grade_cooldown"


def test_plain_pass_upgrade_and_downgrade_respect_90_days_after_last_change():
    category = current("middle", "pass", days_ago=200)
    assert decide("senior", NOW, category, [attempt("middle", "pass", 200)], CONFIG).allowed
    assert decide("junior", NOW, category, [attempt("middle", "pass", 200)], CONFIG).purpose == "downgrade"

    recent_change = [attempt("middle", "pass", 200), attempt("senior", "fail", 10, purpose="upgrade")]
    blocked = decide("senior", NOW, category, recent_change, CONFIG)
    assert not blocked.allowed
    assert blocked.available_at == recent_change[1].started_at + timedelta(days=90)


def test_failed_upgrade_never_lowers_current_grade_and_same_grade_is_not_an_action():
    category = current("middle", "pass", days_ago=200)
    assert decide("middle", NOW, category, [], CONFIG).code == "same_grade"


def test_reconfirm_after_cooldown_expires():
    category = current("middle", "pass", days_ago=200)
    history = [attempt("senior", "fail", 95, purpose="upgrade")]
    assert decide("senior", NOW, category, history, CONFIG).allowed


def test_expired_category_can_be_reconfirmed_on_same_grade():
    """Ревью 06.10, №7: через 12 месяцев тест на текущий грейд снова доступен (§6.3)."""
    expired = CurrentCategory("middle", "pass", NOW - timedelta(days=370), NOW - timedelta(days=5))
    assert decide("middle", NOW, expired, [], CONFIG) == decide("middle", NOW, None, [], CONFIG)
    assert decide("middle", NOW, expired, [], CONFIG).allowed
    valid = CurrentCategory("middle", "pass", NOW - timedelta(days=200), NOW + timedelta(days=165))
    assert decide("middle", NOW, valid, [], CONFIG).code == "same_grade"


def test_failed_reconfirmation_waits_30_days():
    expired = CurrentCategory("middle", "pass", NOW - timedelta(days=370), NOW - timedelta(days=5))
    decision = decide("middle", NOW, expired, [attempt("middle", "fail", 3)], CONFIG)
    assert not decision.allowed and decision.code == "grade_cooldown"
    assert decision.available_at == NOW + timedelta(days=27)


def test_rules_are_counted_within_specialization():
    failed_backend = AttemptRecord("middle", "calibration", "completed", "fail", NOW, "backend")
    assert decide("middle", NOW, None, [failed_backend], CONFIG, "frontend").allowed
    blocked = decide("middle", NOW, None, [failed_backend], CONFIG, "backend")
    assert blocked.code == "grade_cooldown" and "30 дней" in blocked.reason
    # Незавершённый тест блокирует любой новый — по любой специализации
    running = AttemptRecord("junior", "calibration", "in_progress", None, NOW, specialization="backend")
    assert decide("junior", NOW, None, [running], CONFIG, "frontend").code == "attempt_in_progress"
