from fastapi import APIRouter, Depends

from app.core.deps import CurrentAdmin, CurrentCandidate, CurrentUser, DbSession, require_debug_tools
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.debug import service
from app.modules.debug.schemas import DebugStatus

router = APIRouter(prefix="/debug", tags=["debug"], dependencies=[Depends(require_debug_tools)])

ERRORS = error_responses(401, 403, 404)


@router.get(
    "/status",
    response_model=DebugStatus,
    summary="Включён ли отладочный раздел и что в нём доступно",
    responses=ERRORS,
)
async def debug_status(user: CurrentUser) -> DebugStatus:
    return service.status(user.role)


@router.post(
    "/reset-cooldowns",
    response_model=MessageResponse,
    summary="Сбросить ограничения на пересдачу",
    responses=ERRORS,
)
async def reset_cooldowns(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    return await service.reset_cooldowns(db, user.id)


@router.post(
    "/reset-test",
    response_model=MessageResponse,
    summary="Удалить свои попытки теста и категорию",
    responses=ERRORS,
)
async def reset_test(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    return await service.reset_test(db, user.id)


@router.post(
    "/test-email",
    response_model=MessageResponse,
    summary="Отправить себе тестовое письмо",
    responses=error_responses(401, 403, 404, 409),
)
async def test_email(user: CurrentUser, db: DbSession) -> MessageResponse:
    return await service.test_email(db, user.id)


@router.post(
    "/reseed",
    response_model=MessageResponse,
    summary="Пересоздать демо-данные (роль admin)",
    responses=error_responses(401, 403, 404, 409),
)
async def reseed(user: CurrentAdmin) -> MessageResponse:
    return await service.reseed()
