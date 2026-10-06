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
    specialization: str = ""


@dataclass(frozen=True)
class CurrentCategory:
    grade: str
    assigned_by_attempt_result: str | None
    assigned_at: datetime
    valid_until: datetime | None = None
    specialization: str = ""


@dataclass(frozen=True)
class RuleConfig:
    cooldown_days: int
    failed_retry_days: int
    retest_can_downgrade: bool = False


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
    specialization: str = "",
) -> Decision:
    """Можно ли сейчас начать тест на grade по specialization.

    attempts — уже отфильтрованные по сбросу DEMO_MODE.
    """
    if any(a.status == "in_progress" for a in attempts):
        return Decision(False, "calibration", reason="Есть незавершённый тест", code="attempt_in_progress")
    # Правила считаются внутри специализации: провал Backend · Middle не блокирует Frontend · Middle,
    # а тест по новой специализации — калибровка, как будто категории ещё нет
    attempts = [a for a in attempts if a.specialization == specialization]
    if current is not None and current.specialization != specialization:
        current = None

    failed_retry = timedelta(days=config.failed_retry_days)
    failed_same = [a for a in attempts if a.grade == grade and a.status == "completed" and a.result == "fail"]
    retry_at = max((a.started_at + failed_retry for a in failed_same), default=None)

    # §6.3: через 12 месяцев результат требует подтверждения — тест на тот же грейд идёт как калибровка
    expired = current is not None and current.valid_until is not None and current.valid_until <= now
    if current is None or (expired and grade == current.grade):
        if retry_at and retry_at > now:
            return Decision(
                False,
                "calibration",
                retry_at,
                f"Повторная попытка на этот грейд — через {config.failed_retry_days} дней",
                "grade_cooldown",
            )
        return Decision(True, "calibration")

    if grade == current.grade:
        if not config.retest_can_downgrade:
            return Decision(False, "calibration", reason="Это ваш текущий грейд", code="same_grade")
        # Перепроверка своего грейда (настройка платформы): не чаще смены грейда, провал понижает
        cooldown = timedelta(days=config.cooldown_days)
        last = max([current.assigned_at, *(a.started_at for a in attempts if a.grade == grade)])
        available = last + cooldown
        if available > now:
            reason = f"Перепроверить грейд можно не чаще раза в {config.cooldown_days} дней"
            return Decision(False, "calibration", available, reason, "grade_cooldown")
        return Decision(True, "calibration")

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
            False,
            purpose,
            blocked_until,
            f"Сменить грейд можно не чаще раза в {config.cooldown_days} дней",
            "grade_cooldown",
        )
    return Decision(True, purpose)
