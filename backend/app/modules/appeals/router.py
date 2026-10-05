from fastapi import APIRouter, Query, status

from app.core.deps import CurrentAdmin, CurrentCandidate, DbSession
from app.core.enums import AppealStatus
from app.core.errors import error_responses
from app.modules.appeals import service
from app.modules.appeals.schemas import AdminAppealOut, AppealCreate, AppealOut, AppealResolve
from app.modules.candidates import service as candidates_service

candidate_router = APIRouter(prefix="/candidates/me/appeals", tags=["candidate: testing"])
admin_router = APIRouter(prefix="/admin/appeals", tags=["admin: appeals"])


@candidate_router.get(
    "",
    response_model=list[AppealOut],
    summary="Мои обращения по результату теста и ответы на них",
    responses=error_responses(401, 403),
)
async def list_my_appeals(user: CurrentCandidate, db: DbSession) -> list[AppealOut]:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.list_own(db, candidate)


@candidate_router.post(
    "",
    response_model=AppealOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оспорить текущую категорию: обращение рассматривает человек, грейд само не меняет",
    responses=error_responses(401, 403, 409, 422),
)
async def create_appeal(body: AppealCreate, user: CurrentCandidate, db: DbSession) -> AppealOut:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.create(db, candidate, body)


@admin_router.get(
    "",
    response_model=list[AdminAppealOut],
    summary="Обращения кандидатов по грейду (роль admin)",
    responses=error_responses(401, 403, 422),
)
async def list_appeals(
    user: CurrentAdmin,
    db: DbSession,
    status_filter: AppealStatus | None = Query(default=None, alias="status"),
) -> list[AdminAppealOut]:
    return await service.list_all(db, status_filter)


@admin_router.post(
    "/{appeal_id}/resolve",
    response_model=AdminAppealOut,
    summary="Ответить на обращение и закрыть его; категорию ответ сам не меняет",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def resolve_appeal(
    appeal_id: int, body: AppealResolve, user: CurrentAdmin, db: DbSession
) -> AdminAppealOut:
    return await service.resolve(db, user.id, appeal_id, body)
