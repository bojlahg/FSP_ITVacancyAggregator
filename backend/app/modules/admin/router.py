from fastapi import APIRouter, Depends

from app.core.deps import CurrentAdmin, CurrentUser, DbSession, require_demo_mode
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.admin import service
from app.modules.candidates import service as candidates_service
from app.modules.categories import service as categories_service

router = APIRouter(prefix="/admin", tags=["service"], dependencies=[Depends(require_demo_mode)])


@router.post(
    "/reseed",
    response_model=MessageResponse,
    summary="Вернуть демо-данные к исходному состоянию (только DEMO_MODE и роль admin)",
    responses=error_responses(401, 403, 404, 409),
)
async def reseed(user: CurrentAdmin) -> MessageResponse:
    return await service.reseed()


@router.post(
    "/demo/reset-cooldowns",
    response_model=MessageResponse,
    summary="Сбросить ограничения смены грейда для текущего кандидата (только DEMO_MODE)",
    responses=error_responses(401, 403, 404),
)
async def reset_cooldowns(user: CurrentUser, db: DbSession) -> MessageResponse:
    candidate = await candidates_service.get_by_user(db, user.id)
    await categories_service.reset_rules(db, candidate)
    return MessageResponse(message="Ограничения смены грейда сброшены")
