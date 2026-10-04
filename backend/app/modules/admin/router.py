from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_demo_mode
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse

router = APIRouter(prefix="/admin", tags=["service"], dependencies=[Depends(require_demo_mode)])


@router.post(
    "/reseed",
    response_model=MessageResponse,
    summary="Вернуть демо-данные к исходному состоянию (только DEMO_MODE)",
    responses=error_responses(401, 404),
)
async def reseed(user: CurrentUser, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()


@router.post(
    "/demo/reset-cooldowns",
    response_model=MessageResponse,
    summary="Сбросить ограничения смены грейда для текущего пользователя (только DEMO_MODE)",
    responses=error_responses(401, 404),
)
async def reset_cooldowns(user: CurrentUser, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()
