from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InvitationStatus
from app.core.errors import AppError, ForbiddenError
from app.modules.applications.models import Application
from app.modules.catalog.service import get_catalog
from app.modules.employers.models import Employer
from app.modules.employers.schemas import (
    CompanyPublic,
    EmployerProfileFields,
    EmployerProfileOut,
    EmployerProfileUpdate,
    EmployerReputation,
)
from app.modules.invitations.models import Invitation
from app.modules.needs.models import HiringNeed

SECONDS_PER_HOUR = 3600


class ProfileValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Ошибка валидации данных"


def create_empty_profile(db: AsyncSession, user_id: int, company_name: str | None = None) -> Employer:
    employer = Employer(user_id=user_id, company_name=company_name)
    db.add(employer)
    return employer


async def get_by_user(db: AsyncSession, user_id: int) -> Employer:
    employer = await db.scalar(select(Employer).where(Employer.user_id == user_id))
    if employer is None:
        raise ForbiddenError("Профиль работодателя не найден")
    return employer


async def reputation(db: AsyncSession, employer_id: int) -> EmployerReputation:
    """Сигналы добросовестности для кандидата (§8.6 п.4): считаются по фактическим приглашениям и откликам."""
    rows = await db.execute(
        select(Invitation.status, func.count())
        .where(Invitation.employer_id == employer_id)
        .group_by(Invitation.status)
    )
    counts = {status: count for status, count in rows.all()}
    total = sum(counts.values())
    accepted = counts.get(InvitationStatus.accepted, 0)
    declined = counts.get(InvitationStatus.declined, 0)
    withdrawn = counts.get(InvitationStatus.withdrawn, 0)

    responded = await db.execute(
        select(Application.created_at, Application.responded_at)
        .join(HiringNeed, HiringNeed.id == Application.need_id)
        .where(HiringNeed.employer_id == employer_id, Application.responded_at.is_not(None))
    )
    hours = [(answered - created).total_seconds() / SECONDS_PER_HOUR for created, answered in responded.all()]
    return EmployerReputation(
        invitations_sent=total,
        acceptance_rate=accepted / (accepted + declined) if accepted + declined else None,
        withdrawn_rate=withdrawn / total if total else None,
        median_response_hours=round(median(hours), 1) if hours else None,
    )


async def company_public(db: AsyncSession, employer: Employer) -> CompanyPublic:
    """Что кандидат видит о компании в приглашении и вакансии."""
    return CompanyPublic(
        id=employer.id,
        company_name=employer.company_name or "Компания",
        industry=employer.industry,
        website=employer.website,
        description=employer.description,
        reputation=await reputation(db, employer.id),
    )


async def _out(db: AsyncSession, employer: Employer) -> EmployerProfileOut:
    fields = {name: getattr(employer, name) for name in EmployerProfileFields.model_fields}
    return EmployerProfileOut(
        id=employer.id,
        company_name=employer.company_name,
        reputation=await reputation(db, employer.id),
        updated_at=employer.updated_at,
        **fields,
    )


async def get_profile(db: AsyncSession, user_id: int) -> EmployerProfileOut:
    return await _out(db, await get_by_user(db, user_id))


async def update_profile(db: AsyncSession, user_id: int, body: EmployerProfileUpdate) -> EmployerProfileOut:
    if body.industry is not None and body.industry not in {item.slug for item in get_catalog().industries}:
        raise ProfileValidationError(
            details=[{"loc": ["body", "industry"], "msg": "Неизвестная отрасль", "type": "unknown_industry"}]
        )
    employer = await get_by_user(db, user_id)
    for name, value in body.model_dump().items():
        setattr(employer, name, value)
    await db.commit()
    await db.refresh(employer)
    return await _out(db, employer)
