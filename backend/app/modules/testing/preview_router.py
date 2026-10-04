from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.testing.schemas import VacancyTestPreview, VacancyTestPreviewRequest

router = APIRouter(prefix="/vacancy-tests", tags=["employer: vacancy test preview"])


@router.post(
    "/preview",
    response_model=VacancyTestPreview,
    summary="Как система соберёт тест под вакансию: blueprint, примеры заданий, черновики LLM",
    responses=error_responses(401, 403, 404, 422),
)
async def preview_vacancy_test(
    body: VacancyTestPreviewRequest, user: CurrentEmployer, db: DbSession
) -> VacancyTestPreview:
    raise NotImplementedApiError()
