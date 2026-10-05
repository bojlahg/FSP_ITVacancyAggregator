from fastapi import APIRouter, Depends

from app.core.deps import CurrentAdmin, require_demo_mode
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.admin import service

router = APIRouter(prefix="/admin", tags=["service"], dependencies=[Depends(require_demo_mode)])


@router.post(
    "/reseed",
    response_model=MessageResponse,
    summary="Вернуть демо-данные к исходному состоянию (только DEMO_MODE и роль admin)",
    responses=error_responses(401, 403, 404, 409),
)
async def reseed(user: CurrentAdmin) -> MessageResponse:
    return await service.reseed()
