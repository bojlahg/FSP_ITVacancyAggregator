"""Возражения против категории (152-ФЗ ст. 16, docs/implementation.md §13.1): грейд определяет тест,
возражение рассматривает человек и отвечает; автоматически категория не меняется."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.enums import AppealStatus
from app.core.errors import ConflictError, NotFoundError
from app.modules.appeals.models import GradeAppeal
from app.modules.appeals.schemas import AdminAppealOut, AppealCreate, AppealOut, AppealResolve
from app.modules.candidates.models import Candidate
from app.modules.categories import service as categories_service

ALREADY_OPEN = "Обращение по этой категории уже на рассмотрении"


def _out(row: GradeAppeal) -> AppealOut:
    return AppealOut(
        id=row.id,
        category=categories_service.category_ref(row.specialization, row.grade.value),
        theta=row.theta,
        comment=row.comment,
        status=row.status,
        reply=row.reply,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


async def list_own(db: AsyncSession, candidate: Candidate) -> list[AppealOut]:
    rows = await db.scalars(
        select(GradeAppeal)
        .where(GradeAppeal.candidate_id == candidate.id)
        .order_by(GradeAppeal.created_at.desc(), GradeAppeal.id.desc())
    )
    return [_out(row) for row in rows]


async def create(db: AsyncSession, candidate: Candidate, body: AppealCreate) -> AppealOut:
    category = await categories_service.get_current(db, candidate.id)
    if category is None:
        raise ConflictError(
            "Оспорить можно только присвоенную категорию — сначала пройдите тест", code="no_category"
        )
    already = await db.scalar(
        select(GradeAppeal.id).where(
            GradeAppeal.category_id == category.id, GradeAppeal.status == AppealStatus.open
        )
    )
    if already is not None:
        raise ConflictError(ALREADY_OPEN, code="appeal_already_open")
    row = GradeAppeal(
        candidate_id=candidate.id,
        category_id=category.id,
        specialization=category.specialization,
        grade=category.grade,
        theta=category.theta,
        comment=body.comment.strip(),
        status=AppealStatus.open,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:  # параллельный запрос успел раньше — сработал уникальный индекс
        await db.rollback()
        raise ConflictError(ALREADY_OPEN, code="appeal_already_open") from exc
    audit(
        db,
        actor_user_id=candidate.user_id,
        action="appeal.created",
        object_type="grade_appeal",
        object_id=row.id,
        meta={"category_id": category.id},
    )
    await db.commit()
    await db.refresh(row)
    return _out(row)


async def _admin_out(db: AsyncSession, row: GradeAppeal) -> AdminAppealOut:
    candidate = await db.get(Candidate, row.candidate_id)
    current = await categories_service.get_current(db, row.candidate_id)
    parts = (candidate.first_name, candidate.last_name) if candidate else ()
    name = " ".join(part for part in parts if part)
    return AdminAppealOut(
        **_out(row).model_dump(),
        candidate_id=row.candidate_id,
        candidate_name=name or f"Кандидат #{row.candidate_id}",
        category_is_current=current is not None and current.id == row.category_id,
    )


async def list_all(db: AsyncSession, status: AppealStatus | None) -> list[AdminAppealOut]:
    query = select(GradeAppeal).order_by(GradeAppeal.created_at.desc(), GradeAppeal.id.desc())
    if status is not None:
        query = query.where(GradeAppeal.status == status)
    return [await _admin_out(db, row) for row in await db.scalars(query)]


async def resolve(
    db: AsyncSession, admin_user_id: int, appeal_id: int, body: AppealResolve
) -> AdminAppealOut:
    row = await db.get(GradeAppeal, appeal_id, with_for_update=True)
    if row is None:
        raise NotFoundError("Обращение не найдено", code="appeal_not_found")
    if row.status == AppealStatus.resolved:
        raise ConflictError("Обращение уже рассмотрено", code="appeal_already_resolved")
    row.status = AppealStatus.resolved
    row.reply = body.reply.strip()
    row.resolved_by_user_id = admin_user_id
    row.resolved_at = datetime.now(UTC)
    audit(
        db,
        actor_user_id=admin_user_id,
        action="appeal.resolved",
        object_type="grade_appeal",
        object_id=row.id,
        meta={"candidate_id": row.candidate_id},
    )
    await db.commit()
    await db.refresh(row)
    return await _admin_out(db, row)


async def forget_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Удаление аккаунта: тексты обращений — тоже ПДн. Коммитит вызывающий."""
    await db.execute(delete(GradeAppeal).where(GradeAppeal.candidate_id == candidate_id))
