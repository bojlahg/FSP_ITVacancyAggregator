"""Правила смены грейда (§6.3) — чистые функции над историей попыток, без БД."""

from dataclasses import dataclass
from datetime import datetime, timedelta

GRADES = ["intern", "junior", "middle", "senior"]


@dataclass(frozen=True)
class AttemptRecord:
    grade: str
    purpose: str
    status: str
    result: str | None
    started_at: datetime


@dataclass(frozen=True)
class CurrentCategory:
    grade: str
    assigned_by_attempt_result: str | None
    assigned_at: datetime


@dataclass(frozen=True)
class RuleConfig:
    cooldown_days: int
    failed_retry_days: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    purpose: str
    available_at: datetime | None = None
    reason: str | None = None
    code: str | None = None


def decide(
    grade: str,
    now: datetime,
    current: CurrentCategory | None,
    attempts: list[AttemptRecord],
    config: RuleConfig,
) -> Decision:
    """Можно ли сейчас начать тест на grade; attempts — уже отфильтрованные по сбросу DEMO_MODE."""
    if any(a.status == "in_progress" for a in attempts):
        return Decision(False, "calibration", reason="Есть незавершённый тест", code="attempt_in_progress")

    failed_retry = timedelta(days=config.failed_retry_days)
    failed_same = [a for a in attempts if a.grade == grade and a.status == "completed" and a.result == "fail"]
    retry_at = max((a.started_at + failed_retry for a in failed_same), default=None)

    if current is None:
        if retry_at and retry_at > now:
            return Decision(
                False,
                "calibration",
                retry_at,
                "Повторная попытка на этот грейд — через 30 дней",
                "grade_cooldown",
            )
        return Decision(True, "calibration")

    if grade == current.grade:
        return Decision(False, "calibration", reason="Это ваш текущий грейд", code="same_grade")

    purpose = "upgrade" if GRADES.index(grade) > GRADES.index(current.grade) else "downgrade"
    changes = [a for a in attempts if a.purpose in {"upgrade", "downgrade"}]
    next_grade = GRADES[GRADES.index(current.grade) + 1] if current.grade != GRADES[-1] else None

    # Уверенный проход даёт одну немедленную попытку на грейд выше (§6.2)
    confident_bonus = (
        current.assigned_by_attempt_result == "confident_pass"
        and grade == next_grade
        and not any(a.started_at >= current.assigned_at for a in changes)
    )
    if confident_bonus:
        return Decision(True, "upgrade")

    cooldown = timedelta(days=config.cooldown_days)
    last_change = max((a.started_at for a in changes), default=None)
    blocked_until = max(
        filter(None, [last_change + cooldown if last_change else None, retry_at]), default=None
    )
    if blocked_until and blocked_until > now:
        return Decision(
            False, purpose, blocked_until, "Сменить грейд можно не чаще раза в 90 дней", "grade_cooldown"
        )
    return Decision(True, purpose)
