from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AttemptStatus, SkillSource, SkillStatus
from app.core.errors import ForbiddenError
from app.modules.candidates.models import Candidate, CandidateExperience, CandidateSkill
from app.modules.candidates.schemas import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    ExperienceItem,
    PrivacySettings,
    SkillState,
)
from app.modules.catalog.service import get_catalog

STATUS_BY_SOURCE = {
    SkillSource.test: SkillStatus.verified,
    SkillSource.fsp: SkillStatus.fsp_confirmed,
    SkillSource.task: SkillStatus.task_confirmed,
}
STATUS_ORDER = [
    SkillStatus.verified,
    SkillStatus.fsp_confirmed,
    SkillStatus.task_confirmed,
    SkillStatus.declared,
]


def create_empty_profile(db: AsyncSession, user_id: int) -> Candidate:
    candidate = Candidate(user_id=user_id, work_formats=[], roles=[], privacy={})
    db.add(candidate)
    return candidate


async def get_by_user(db: AsyncSession, user_id: int) -> Candidate:
    candidate = await db.scalar(select(Candidate).where(Candidate.user_id == user_id))
    if candidate is None:
        raise ForbiddenError("Профиль кандидата не найден")
    return candidate


def fsp_skills_count(candidate: Candidate, for_employer: bool) -> bool:
    """Навыки из ФСП — только при подтверждённом владении (§9.3) и, для работодателя, если ФСП не скрыт.

    Одно правило для профиля, карточки, PDF и индекса выдачи: статус на карточке совпадает с тем, что в score.
    """
    from app.modules.fsp import service as fsp_service

    return fsp_service.counts_in_score(candidate) and (not for_employer or privacy_of(candidate).show_fsp)


async def skill_states(db: AsyncSession, candidate_id: int, for_employer: bool = False) -> list[SkillState]:
    names = {skill.id: skill.name for skill in get_catalog().skills}
    candidate = await db.get(Candidate, candidate_id)
    with_fsp = candidate is not None and fsp_skills_count(candidate, for_employer)
    sources: dict[str, set[SkillSource]] = {}
    for row in await db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)):
        if row.source == SkillSource.fsp and not with_fsp:
            continue
        sources.setdefault(row.skill_id, set()).add(row.source)
    states = []
    for skill_id, found in sources.items():
        statuses = [STATUS_BY_SOURCE.get(source, SkillStatus.declared) for source in found]
        status = min(statuses, key=STATUS_ORDER.index)
        states.append(
            SkillState(
                skill_id=skill_id, name=names.get(skill_id, skill_id), status=status, sources=sorted(found)
            )
        )
    return sorted(states, key=lambda state: (STATUS_ORDER.index(state.status), state.name.lower()))


def privacy_of(candidate: Candidate) -> PrivacySettings:
    return PrivacySettings(
        **(candidate.privacy or {}), hidden_employer_ids=list(candidate.hidden_employer_ids or [])
    )


async def _onboarding_step(db: AsyncSession, candidate: Candidate, has_category: bool) -> str:
    from app.modules.survey import service as survey_service
    from app.modules.testing.models import TestAttempt

    if has_category:
        return "done"
    if await survey_service.latest_response(db, candidate.id) is None:
        return "survey"
    if not candidate.specialization:
        return "specialization"
    in_progress = await db.scalar(
        select(TestAttempt.id).where(
            TestAttempt.candidate_id == candidate.id, TestAttempt.status == AttemptStatus.in_progress
        )
    )
    return "test" if in_progress else "grade"


async def profile_out(db: AsyncSession, candidate: Candidate) -> CandidateProfileOut:
    from app.modules.categories import service as categories_service

    current = await categories_service.get_current(db, candidate.id)
    skills = await skill_states(db, candidate.id)
    experience = list(
        await db.scalars(
            select(CandidateExperience)
            .where(CandidateExperience.candidate_id == candidate.id)
            .order_by(CandidateExperience.started_on.desc().nulls_last())
        )
    )
    filled = [
        candidate.first_name,
        candidate.last_name,
        candidate.phone or candidate.telegram or candidate.contact_email,
        candidate.city,
        candidate.work_formats,
        candidate.salary_min,
        candidate.experience_years is not None,
        skills,
        candidate.about,
        current,
    ]
    return CandidateProfileOut(
        **{
            field: getattr(candidate, field)
            for field in CandidateProfileUpdate.model_fields
            if hasattr(candidate, field)
        },
        id=candidate.id,
        specialization=candidate.specialization,
        category=categories_service.category_ref(current.specialization, current.grade.value)
        if current
        else None,
        skills=skills,
        experience=[ExperienceItem.model_validate(row) for row in experience],
        privacy=privacy_of(candidate),
        fsp_id=candidate.fsp_id,
        fsp_link_method=candidate.fsp_link_method,
        profile_completeness=round(sum(bool(value) for value in filled) / len(filled), 2),
        onboarding_step=await _onboarding_step(db, candidate, current is not None),
        updated_at=candidate.updated_at,
    )


async def update_profile(
    db: AsyncSession, candidate: Candidate, body: CandidateProfileUpdate
) -> CandidateProfileOut:
    from app.modules.matching import service as matching_service

    for field, value in body.model_dump(exclude={"declared_skills", "experience"}).items():
        setattr(candidate, field, value)
    candidate.work_formats = [
        value.value if hasattr(value, "value") else value for value in body.work_formats
    ]

    known = {skill.id for skill in get_catalog().skills}
    await db.execute(
        delete(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.id, CandidateSkill.source == SkillSource.declared
        )
    )
    now = datetime.now(UTC)
    for skill_id in dict.fromkeys(item.skill_id for item in body.declared_skills):
        if skill_id in known:
            db.add(
                CandidateSkill(
                    candidate_id=candidate.id, skill_id=skill_id, source=SkillSource.declared, updated_at=now
                )
            )

    await db.execute(delete(CandidateExperience).where(CandidateExperience.candidate_id == candidate.id))
    for item in body.experience:
        db.add(CandidateExperience(candidate_id=candidate.id, **item.model_dump()))
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    await db.refresh(candidate)
    return await profile_out(db, candidate)
