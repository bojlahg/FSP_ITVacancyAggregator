"""Потребности работодателя: версии, шорт-лист, публикация как вакансии (§8.1, §8.7)."""

from datetime import UTC, datetime

from sqlalchemy import Select, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.enums import InvitationStatus, NeedStatus
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.schemas import MessageResponse
from app.modules.applications.models import Application
from app.modules.candidates.models import Candidate
from app.modules.catalog.service import get_catalog
from app.modules.categories.service import category_ref
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.invitations.models import Invitation
from app.modules.needs.models import HiringNeed, NeedShortlist
from app.modules.needs.schemas import NeedFields, NeedOut, NeedStats

ACTIVE_INVITATION_STATUSES = (InvitationStatus.sent, InvitationStatus.viewed)


class NeedValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Ошибка валидации данных"


class NeedSupersededError(ConflictError):
    code = "need_superseded"
    message = "Эта версия потребности уже уточнена — откройте последнюю версию"


def _issue(field: str, msg: str, kind: str = "value_error", index: int | None = None) -> dict:
    loc: list[str | int] = ["body", field] if index is None else ["body", field, index]
    return {"loc": loc, "msg": msg, "type": kind}


def validate_fields(body: NeedFields) -> None:
    """Значения из справочников: специализация, навыки, отрасль (§5)."""
    catalog = get_catalog()
    specs = {spec.slug for spec in catalog.specializations}
    skills = {skill.id for skill in catalog.skills}
    industries = {item.slug for item in catalog.industries}
    issues = []
    if body.specialization not in specs:
        issues.append(_issue("specialization", "Неизвестная специализация", "unknown_specialization"))
    for field in ("required_skills", "optional_skills"):
        for index, skill_id in enumerate(getattr(body, field)):
            if skill_id not in skills:
                issues.append(_issue(field, f"Неизвестный навык: {skill_id}", "unknown_skill", index))
    overlap = set(body.required_skills) & set(body.optional_skills)
    if overlap:
        issues.append(
            _issue("optional_skills", "Навык не может быть одновременно обязательным и желательным")
        )
    if body.industry is not None and body.industry not in industries:
        issues.append(_issue("industry", "Неизвестная отрасль", "unknown_industry"))
    if issues:
        raise NeedValidationError(details=issues)


def _latest_only(query: Select) -> Select:
    """Только последние версии: у строки нет потомка с parent_id на неё."""
    child = aliased(HiringNeed)
    return query.where(~exists(select(child.id).where(child.parent_id == HiringNeed.id)))


async def _employer(db: AsyncSession, user_id: int) -> Employer:
    return await employers_service.get_by_user(db, user_id)


async def get_own_need(db: AsyncSession, user_id: int, need_id: int) -> HiringNeed:
    """Потребность текущего работодателя; чужая — 404, чтобы не раскрывать её существование."""
    employer = await _employer(db, user_id)
    need = await db.get(HiringNeed, need_id)
    if need is None or need.employer_id != employer.id:
        raise NotFoundError("Потребность не найдена")
    return need


async def is_latest(db: AsyncSession, need_id: int) -> bool:
    child = await db.scalar(select(HiringNeed.id).where(HiringNeed.parent_id == need_id).limit(1))
    return child is None


async def _get_latest_own(db: AsyncSession, user_id: int, need_id: int) -> HiringNeed:
    need = await get_own_need(db, user_id, need_id)
    if not await is_latest(db, need.id):
        raise NeedSupersededError()
    return need


async def version_chain_ids(db: AsyncSession, need: HiringNeed) -> list[int]:
    """id этой версии и всех предыдущих: приглашения и отклики могут ссылаться на старые версии."""
    ids = [need.id]
    parent_id = need.parent_id
    while parent_id is not None:
        ids.append(parent_id)
        parent_id = await db.scalar(select(HiringNeed.parent_id).where(HiringNeed.id == parent_id))
    return ids


async def shortlist_candidate_ids(db: AsyncSession, need_id: int) -> list[int]:
    query = select(NeedShortlist.candidate_id).where(NeedShortlist.need_id == need_id)
    return list(await db.scalars(query.order_by(NeedShortlist.pinned_at)))


async def _stats(db: AsyncSession, need: HiringNeed) -> NeedStats:
    chain = await version_chain_ids(db, need)
    shortlisted = await db.scalar(
        select(func.count()).select_from(NeedShortlist).where(NeedShortlist.need_id == need.id)
    )
    invitations = await db.execute(
        select(
            func.count(),
            func.count().filter(Invitation.status.in_(ACTIVE_INVITATION_STATUSES)),
        ).where(Invitation.need_id.in_(chain))
    )
    total, active = invitations.one()
    applications = await db.scalar(
        select(func.count()).select_from(Application).where(Application.need_id.in_(chain))
    )
    return NeedStats(
        shortlisted=shortlisted or 0,
        invitations_active=active or 0,
        invitations_total=total or 0,
        invitations_limit=get_settings().max_active_invites_per_need,
        applications=applications or 0,
    )


async def to_out(db: AsyncSession, need: HiringNeed) -> NeedOut:
    return NeedOut(
        id=need.id,
        version=need.version,
        parent_id=need.parent_id,
        status=need.status,
        published=need.published,
        published_at=need.published_at,
        created_at=need.created_at,
        title=need.title,
        raw_text=need.raw_text,
        specialization=need.specialization,
        grade=need.grade,
        required_skills=list(need.required_skills or []),
        optional_skills=list(need.optional_skills or []),
        industry=need.industry,
        team_description=need.team_description,
        work_format=need.work_format,
        city=need.city,
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        category=category_ref(need.specialization, need.grade.value),
        stats=await _stats(db, need),
    )


def _apply_fields(need: HiringNeed, body: NeedFields) -> None:
    for name in NeedFields.model_fields:
        setattr(need, name, getattr(body, name))
    need.required_skills = list(body.required_skills)
    need.optional_skills = list(body.optional_skills)


async def list_needs(db: AsyncSession, user_id: int) -> list[NeedOut]:
    employer = await _employer(db, user_id)
    query = _latest_only(select(HiringNeed).where(HiringNeed.employer_id == employer.id)).order_by(
        HiringNeed.created_at.desc(), HiringNeed.id.desc()
    )
    return [await to_out(db, need) for need in await db.scalars(query)]


async def create_need(db: AsyncSession, user_id: int, body: NeedFields) -> NeedOut:
    validate_fields(body)
    employer = await _employer(db, user_id)
    need = HiringNeed(employer_id=employer.id, version=1, status=NeedStatus.active, published=False)
    _apply_fields(need, body)
    db.add(need)
    await db.commit()
    await db.refresh(need)
    return await to_out(db, need)


async def get_need(db: AsyncSession, user_id: int, need_id: int) -> NeedOut:
    return await to_out(db, await get_own_need(db, user_id, need_id))


async def update_need(db: AsyncSession, user_id: int, need_id: int, body: NeedFields) -> NeedOut:
    """Правка — новая версия; шорт-лист переезжает на неё, старая версия остаётся в истории (§8.1 п.4)."""
    validate_fields(body)
    old = await _get_latest_own(db, user_id, need_id)
    need = HiringNeed(
        employer_id=old.employer_id,
        version=old.version + 1,
        parent_id=old.id,
        status=old.status,
        published=old.published,
        published_at=old.published_at,
    )
    _apply_fields(need, body)
    db.add(need)
    # Вакансией остаётся только последняя версия — старую снимаем, чтобы не было дублей в списке
    old.published = False
    await db.flush()
    await db.execute(update(NeedShortlist).where(NeedShortlist.need_id == old.id).values(need_id=need.id))
    await db.commit()
    await db.refresh(need)
    return await to_out(db, need)


async def set_published(db: AsyncSession, user_id: int, need_id: int, published: bool) -> NeedOut:
    need = await _get_latest_own(db, user_id, need_id)
    if published and not need.published:
        employer = await _employer(db, user_id)
        if not employer.company_name:
            raise ConflictError(
                "Заполните название компании в профиле перед публикацией вакансии",
                code="company_profile_required",
            )
        if need.status == NeedStatus.closed:
            raise ConflictError("Закрытую потребность нельзя опубликовать", code="need_closed")
        need.published = True
        need.published_at = datetime.now(UTC)
    elif not published:
        need.published = False
    await db.commit()
    await db.refresh(need)
    return await to_out(db, need)


async def add_to_shortlist(
    db: AsyncSession, user_id: int, need_id: int, candidate_id: int, note: str | None
) -> MessageResponse:
    need = await _get_latest_own(db, user_id, need_id)
    if await db.get(Candidate, candidate_id) is None:
        raise NotFoundError("Кандидат не найден")
    row = await db.get(NeedShortlist, (need.id, candidate_id))
    if row is None:
        db.add(NeedShortlist(need_id=need.id, candidate_id=candidate_id, note=note))
    elif note is not None:
        row.note = note
    await db.commit()
    return MessageResponse(message="Кандидат в шорт-листе")


async def remove_from_shortlist(
    db: AsyncSession, user_id: int, need_id: int, candidate_id: int
) -> MessageResponse:
    need = await _get_latest_own(db, user_id, need_id)
    row = await db.get(NeedShortlist, (need.id, candidate_id))
    if row is not None:
        await db.delete(row)
        await db.commit()
    return MessageResponse(message="Кандидат убран из шорт-листа")
