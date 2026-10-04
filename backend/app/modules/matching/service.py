"""Индекс выдачи кандидатов (§14): денормализованная строка на кандидата, пересчитывается при изменениях."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ConsentKind, SearchStatus, SkillSource
from app.modules.auth import service as auth_service
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.categories import service as categories_service
from app.modules.matching.models import CandidateSearchIndex
from app.modules.testing.models import TestAttempt

FRESH_HALF_LIFE_DAYS = 90
SKILL_STATUS_PRIORITY = {
    SkillSource.test: "verified",
    SkillSource.fsp: "fsp_confirmed",
    SkillSource.task: "task_confirmed",
}


def freshness(last_activity: datetime | None, now: datetime) -> float:
    """fresh = 0.5^(дней с последнего проверенного действия / 90) — §8.3."""
    if last_activity is None:
        return 0.0
    days = max((now - last_activity).total_seconds() / 86400, 0.0)
    return 0.5 ** (days / FRESH_HALF_LIFE_DAYS)


def vps(percentile: float | None, fsp: float, fresh: float, approach: float | None) -> float:
    """Сила подтверждённого профиля внутри категории — §8.3."""
    return round(0.60 * (percentile or 0.0) + 0.15 * fsp + 0.15 * fresh + 0.10 * (approach or 0.0), 4)


async def refresh_candidate(db: AsyncSession, candidate_id: int) -> None:
    candidate = await db.get(Candidate, candidate_id)
    current = await categories_service.get_current(db, candidate_id) if candidate else None
    if candidate is None or current is None:
        await db.execute(
            delete(CandidateSearchIndex).where(CandidateSearchIndex.candidate_id == candidate_id)
        )
        return

    now = datetime.now(UTC)
    attempt = await db.get(TestAttempt, current.attempt_id) if current.attempt_id else None
    skills: dict[str, str] = {}
    for skill in await db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)):
        status = SKILL_STATUS_PRIORITY.get(skill.source, "declared")
        if skills.get(skill.skill_id) in (None, "declared"):
            skills[skill.skill_id] = status
    published = await auth_service.has_active_consent(db, candidate.user_id, ConsentKind.profile_publication)
    fresh = freshness(current.assigned_at, now)
    approach = attempt.approach_score if attempt else None

    row = await db.get(CandidateSearchIndex, candidate_id) or CandidateSearchIndex(candidate_id=candidate_id)
    row.visible = published and candidate.search_status != SearchStatus.hidden
    row.specialization = current.specialization
    row.grade = current.grade
    row.theta = current.theta
    row.percentile = current.percentile
    row.fsp_score = row.fsp_score or 0.0
    row.fresh = fresh
    row.approach = approach
    row.vps = vps(current.percentile, row.fsp_score, fresh, approach)
    row.skills_status = skills
    row.topic_scores = (attempt.topic_scores or {}) if attempt else {}
    row.salary_min = candidate.salary_min
    row.work_formats = list(candidate.work_formats or [])
    row.city = candidate.city
    row.relocation = candidate.relocation
    row.hidden_employer_ids = list(candidate.hidden_employer_ids or [])
    row.has_fsp = row.has_fsp or False
    row.last_activity_at = current.assigned_at
    row.updated_at = now
    db.add(row)


async def refresh_category(db: AsyncSession, specialization: str, grade) -> None:
    """Перцентили соседей по категории изменились — обновляем их строки индекса."""
    rows = await db.scalars(
        select(CandidateSearchIndex.candidate_id).where(
            CandidateSearchIndex.specialization == specialization, CandidateSearchIndex.grade == grade
        )
    )
    for candidate_id in list(rows):
        await refresh_candidate(db, candidate_id)
