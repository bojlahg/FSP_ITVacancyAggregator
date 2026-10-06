"""Категории «специализация × грейд»: правила смены, присвоение по тесту, перцентили (§6.3, §10.4)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import AttemptStatus, Grade
from app.core.schemas import CategoryRef
from app.modules.candidates.models import Candidate
from app.modules.catalog.service import get_catalog
from app.modules.categories.models import CandidateCategory
from app.modules.categories.rules import GRADES, AttemptRecord, CurrentCategory, Decision, RuleConfig, decide
from app.modules.categories.schemas import (
    AttemptSummary,
    CategoryRecord,
    GradeAction,
    GradeDecision,
    GradeExplanation,
    GradeStatus,
)
from app.modules.testing.engine.bank import get_blueprints
from app.modules.testing.models import TestAttempt


def category_label(specialization: str, grade: str) -> str:
    specs = {spec.slug: spec.short_name for spec in get_catalog().specializations}
    grades = {item.slug.value: item.name for item in get_catalog().grades}
    return f"{specs.get(specialization, specialization)} · {grades.get(grade, grade)}"


def category_ref(specialization: str, grade: str) -> CategoryRef:
    return CategoryRef(
        specialization=specialization, grade=Grade(grade), label=category_label(specialization, grade)
    )


async def get_current(db: AsyncSession, candidate_id: int) -> CandidateCategory | None:
    return await db.scalar(
        select(CandidateCategory).where(
            CandidateCategory.candidate_id == candidate_id, CandidateCategory.is_current.is_(True)
        )
    )


async def _attempts(db: AsyncSession, candidate: Candidate) -> list[TestAttempt]:
    query = (
        select(TestAttempt).where(TestAttempt.candidate_id == candidate.id).order_by(TestAttempt.started_at)
    )
    return list(await db.scalars(query))


def _records(candidate: Candidate, attempts: list[TestAttempt]) -> list[AttemptRecord]:
    reset_at = candidate.grade_rules_reset_at
    return [
        AttemptRecord(
            grade=a.grade_target.value,
            purpose=a.purpose.value,
            status=a.status.value,
            result=a.result.value if a.result else None,
            started_at=a.started_at,
        )
        for a in attempts
        if reset_at is None or a.started_at >= reset_at or a.status == AttemptStatus.in_progress
    ]


async def _current_view(db: AsyncSession, current: CandidateCategory | None) -> CurrentCategory | None:
    if current is None:
        return None
    result = None
    if current.attempt_id:
        attempt = await db.get(TestAttempt, current.attempt_id)
        result = attempt.result.value if attempt and attempt.result else None
    return CurrentCategory(
        grade=current.grade.value,
        assigned_by_attempt_result=result,
        assigned_at=current.assigned_at,
        valid_until=current.valid_until,
    )


def _config() -> RuleConfig:
    settings = get_settings()
    return RuleConfig(settings.grade_change_cooldown_days, settings.failed_grade_retry_days)


async def check_can_start(db: AsyncSession, candidate: Candidate, grade: str) -> Decision:
    current = await _current_view(db, await get_current(db, candidate.id))
    return decide(
        grade, datetime.now(UTC), current, _records(candidate, await _attempts(db, candidate)), _config()
    )


async def grade_status(db: AsyncSession, candidate: Candidate) -> GradeStatus:
    now = datetime.now(UTC)
    history_rows = list(
        await db.scalars(
            select(CandidateCategory)
            .where(CandidateCategory.candidate_id == candidate.id)
            .order_by(CandidateCategory.assigned_at.desc())
        )
    )
    attempts = await _attempts(db, candidate)
    current_row = next((row for row in history_rows if row.is_current), None)
    current = await _current_view(db, current_row)
    records = _records(candidate, attempts)

    actions = []
    if candidate.specialization:
        for grade in GRADES:
            decision = decide(grade, now, current, records, _config())
            if decision.code == "same_grade":
                continue
            action = "calibrate" if current is None else decision.purpose
            if current is not None and grade == current.grade:
                action = "reconfirm"  # истёкшая категория (§6.3)
            if decision.code == "grade_cooldown" and current is None:
                action = "retry"
            actions.append(
                GradeAction(
                    action=action,
                    grade=Grade(grade),
                    allowed=decision.allowed,
                    available_at=decision.available_at,
                    reason=decision.reason,
                )
            )

    def record(row: CandidateCategory) -> CategoryRecord:
        return CategoryRecord(
            category=category_ref(row.specialization, row.grade.value),
            theta=row.theta,
            percentile=row.percentile,
            assigned_at=row.assigned_at,
            valid_until=row.valid_until,
            is_current=row.is_current,
            needs_reconfirmation=row.valid_until < now,
        )

    current_record = None
    if current_row is not None:
        from app.modules.testing import service as testing_service

        current_record = record(current_row)
        current_record.evidence = await testing_service.grade_evidence(
            db, current_row.attempt_id, current_row.grade.value, current_row.valid_until, for_candidate=True
        )
    return GradeStatus(
        current=current_record,
        history=[record(row) for row in history_rows],
        attempts=[
            AttemptSummary(
                id=a.id,
                specialization=a.specialization,
                grade_target=a.grade_target,
                purpose=a.purpose,
                status=a.status,
                result=a.result,
                started_at=a.started_at,
                finished_at=a.finished_at,
            )
            for a in reversed(attempts)
        ],
        actions=actions,
        cooldown_days=get_settings().grade_change_cooldown_days,
    )


async def grade_explanation(db: AsyncSession, candidate: Candidate) -> GradeExplanation:
    """Блок «Как определён грейд» (152-ФЗ ст. 16): решение принимает тест, см. §10.4."""
    current = await get_current(db, candidate.id)
    if current is None:
        return GradeExplanation(current=None)
    attempt = await db.get(TestAttempt, current.attempt_id) if current.attempt_id else None
    blueprints = get_blueprints()
    grade = current.grade.value
    next_grade = blueprints.next_grade(grade)
    return GradeExplanation(
        current=GradeDecision(
            category=category_ref(current.specialization, grade),
            theta=current.theta,
            se=attempt.se if attempt else None,
            cut=blueprints.cut(grade),
            next_grade=Grade(next_grade) if next_grade else None,
            next_cut=blueprints.cut(next_grade) if next_grade else None,
            result=attempt.result if attempt else None,
            percentile=current.percentile,
            attempt_id=current.attempt_id,
            tested_at=(attempt.finished_at if attempt and attempt.finished_at else current.assigned_at),
            valid_until=current.valid_until,
        )
    )


async def apply_attempt_result(db: AsyncSession, attempt: TestAttempt) -> CandidateCategory | None:
    """Пройденный тест присваивает категорию; непройденный не понижает текущую (§6.3). Коммитит вызывающий."""
    if attempt.result is None or attempt.result.value == "fail" or attempt.candidate_id is None:
        return None
    now = datetime.now(UTC)
    await db.execute(
        update(CandidateCategory)
        .where(CandidateCategory.candidate_id == attempt.candidate_id, CandidateCategory.is_current.is_(True))
        .values(is_current=False)
    )
    category = CandidateCategory(
        candidate_id=attempt.candidate_id,
        specialization=attempt.specialization,
        grade=attempt.grade_target,
        theta=attempt.theta,
        attempt_id=attempt.id,
        assigned_at=now,
        valid_until=now + timedelta(days=get_settings().category_valid_days),
        is_current=True,
    )
    db.add(category)
    await db.flush()
    await recompute_percentiles(db, attempt.specialization, attempt.grade_target)
    return category


async def retire_current(db: AsyncSession, candidate_id: int) -> tuple[str, Grade] | None:
    """Снять текущую категорию (удаление аккаунта): перцентили соседей пересчитываются без кандидата.

    Возвращает (специализация, грейд) снятой категории. Коммитит вызывающий.
    """
    current = await get_current(db, candidate_id)
    if current is None:
        return None
    current.is_current = False
    await db.flush()
    await recompute_percentiles(db, current.specialization, current.grade)
    return current.specialization, current.grade


async def recompute_percentiles(db: AsyncSession, specialization: str, grade: Grade) -> None:
    """Перцентиль θ внутри категории: доля ниже + половина равных (mid-rank)."""
    rows = list(
        await db.scalars(
            select(CandidateCategory).where(
                CandidateCategory.specialization == specialization,
                CandidateCategory.grade == grade,
                CandidateCategory.is_current.is_(True),
            )
        )
    )
    thetas = [row.theta for row in rows]
    for row in rows:
        below = sum(theta < row.theta for theta in thetas)
        equal = sum(theta == row.theta for theta in thetas)
        row.percentile = round((below + 0.5 * equal) / len(thetas), 4)


async def forget_results(db: AsyncSession, candidate: Candidate) -> None:
    """Отладка: попытки и категории кандидата удаляются, как будто теста не было. Коммитит вызывающий."""
    await db.execute(delete(CandidateCategory).where(CandidateCategory.candidate_id == candidate.id))
    await db.execute(delete(TestAttempt).where(TestAttempt.candidate_id == candidate.id))
    candidate.grade_rules_reset_at = datetime.now(UTC)


async def reset_rules(db: AsyncSession, candidate: Candidate) -> None:
    candidate.grade_rules_reset_at = datetime.now(UTC)
    await db.commit()
