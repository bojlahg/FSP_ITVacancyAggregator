from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import error_responses
from app.modules.candidates import service as candidates_service
from app.modules.categories import service
from app.modules.categories.schemas import GradeExplanation, GradeStatus

router = APIRouter(prefix="/candidates/me", tags=["candidate: testing"])


@router.get(
    "/grade-status",
    response_model=GradeStatus,
    summary="Категория и грейд: текущий статус, история, доступные действия и сроки",
    responses=error_responses(401, 403),
)
async def get_grade_status(user: CurrentCandidate, db: DbSession) -> GradeStatus:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.grade_status(db, candidate)


@router.get(
    "/grade-explanation",
    response_model=GradeExplanation,
    summary="Как определён грейд: θ̂, SE, порог грейда, дата теста (решение принимает только тест)",
    responses=error_responses(401, 403),
)
async def get_grade_explanation(user: CurrentCandidate, db: DbSession) -> GradeExplanation:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.grade_explanation(db, candidate)
