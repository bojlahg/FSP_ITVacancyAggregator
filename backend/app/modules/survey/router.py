from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse
from app.modules.survey.schemas import SpecializationConfirm, SurveyQuestion, SurveyResult, SurveySubmit

router = APIRouter(prefix="/survey", tags=["candidate: onboarding"])


@router.get(
    "/questions",
    response_model=list[SurveyQuestion],
    summary="Вопросы опроса по отрасли и специализации",
    responses=error_responses(401, 403),
)
async def get_questions(user: CurrentCandidate) -> list[SurveyQuestion]:
    raise NotImplementedApiError()


@router.post(
    "/responses",
    response_model=SurveyResult,
    status_code=201,
    summary="Отправить ответы: рекомендуемые специализации и подсказка грейда",
    responses=error_responses(401, 403, 422),
)
async def submit_survey(body: SurveySubmit, user: CurrentCandidate, db: DbSession) -> SurveyResult:
    raise NotImplementedApiError()


@router.post(
    "/specialization",
    response_model=MessageResponse,
    summary="Подтвердить специализацию",
    responses=error_responses(401, 403, 409, 422),
)
async def confirm_specialization(
    body: SpecializationConfirm, user: CurrentCandidate, db: DbSession
) -> MessageResponse:
    raise NotImplementedApiError()
