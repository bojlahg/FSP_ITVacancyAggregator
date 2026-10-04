from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.categories.schemas import GradeStatus

router = APIRouter(prefix="/candidates/me", tags=["candidate: testing"])


@router.get(
    "/grade-status",
    response_model=GradeStatus,
    summary="Категория и грейд: текущий статус, история, доступные действия и сроки",
    responses=error_responses(401, 403),
)
async def get_grade_status(user: CurrentCandidate, db: DbSession) -> GradeStatus:
    raise NotImplementedApiError()
