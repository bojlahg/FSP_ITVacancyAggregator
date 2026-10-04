from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.candidates import service as candidates_service
from app.modules.survey import service
from app.modules.survey.schemas import SpecializationConfirm, SurveyQuestion, SurveyResult, SurveySubmit

router = APIRouter(prefix="/survey", tags=["candidate: onboarding"])


@router.get(
    "/questions",
    response_model=list[SurveyQuestion],
    summary="Вопросы опроса по отрасли и специализации",
    responses=error_responses(401, 403),
)
async def get_questions(user: CurrentCandidate) -> list[SurveyQuestion]:
    return service.get_questions()


@router.post(
    "/responses",
    response_model=SurveyResult,
    status_code=201,
    summary="Отправить ответы: рекомендуемые специализации, подсказка грейда, стек-модули теста",
    responses=error_responses(401, 403, 422),
)
async def submit_survey(body: SurveySubmit, user: CurrentCandidate, db: DbSession) -> SurveyResult:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.submit(db, candidate, body.answers)


@router.get(
    "/responses/latest",
    response_model=SurveyResult | None,
    summary="Последний результат опроса (null, если опрос не пройден)",
    responses=error_responses(401, 403),
)
async def latest_survey(user: CurrentCandidate, db: DbSession) -> SurveyResult | None:
    candidate = await candidates_service.get_by_user(db, user.id)
    response = await service.latest_response(db, candidate.id)
    return service.result_of(response) if response else None


@router.post(
    "/specialization",
    response_model=MessageResponse,
    summary="Подтвердить специализацию (409 — закреплена действующей категорией или нет опроса)",
    responses=error_responses(400, 401, 403, 409, 422),
)
async def confirm_specialization(
    body: SpecializationConfirm, user: CurrentCandidate, db: DbSession
) -> MessageResponse:
    candidate = await candidates_service.get_by_user(db, user.id)
    await service.confirm_specialization(db, candidate, body.specialization)
    return MessageResponse(message="Специализация сохранена")
