from fastapi import APIRouter, Query

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.enums import ApplicationStatus, Grade
from app.core.errors import error_responses
from app.modules.applications import service
from app.modules.applications.schemas import (
    ApplicationForCandidate,
    ApplicationForEmployer,
    ApplyRequest,
    VacancyOut,
)

candidate_router = APIRouter(tags=["candidate: vacancies"])
employer_router = APIRouter(tags=["employer: vacancies"])

TRANSITION = error_responses(401, 403, 404, 409)


@candidate_router.get(
    "/vacancies",
    response_model=list[VacancyOut],
    summary="Опубликованные вакансии; при match=true — сначала подходящие моей категории",
    responses=error_responses(401, 403),
)
async def list_vacancies(
    user: CurrentCandidate,
    db: DbSession,
    match: bool = Query(default=True),
    specialization: str | None = Query(default=None),
    grade: Grade | None = Query(default=None),
    q: str | None = Query(default=None, description="Поиск по названию и навыкам"),
) -> list[VacancyOut]:
    return await service.list_vacancies(db, user.id, match, specialization, grade, q)


@candidate_router.get(
    "/vacancies/{vacancy_id}",
    response_model=VacancyOut,
    summary="Вакансия",
    responses=error_responses(401, 403, 404),
)
async def get_vacancy(vacancy_id: int, user: CurrentCandidate, db: DbSession) -> VacancyOut:
    return await service.get_vacancy(db, user.id, vacancy_id)


@candidate_router.post(
    "/vacancies/{vacancy_id}/apply",
    response_model=ApplicationForCandidate,
    status_code=201,
    summary="Откликнуться — контакты раскрываются работодателю",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def apply_to_vacancy(
    vacancy_id: int, body: ApplyRequest, user: CurrentCandidate, db: DbSession
) -> ApplicationForCandidate:
    return await service.apply(db, user.id, vacancy_id, body)


@candidate_router.get(
    "/candidates/me/applications",
    response_model=list[ApplicationForCandidate],
    summary="Мои отклики и их статусы",
    responses=error_responses(401, 403),
)
async def list_my_applications(user: CurrentCandidate, db: DbSession) -> list[ApplicationForCandidate]:
    return await service.list_mine(db, user.id)


@employer_router.get(
    "/needs/{need_id}/applications",
    response_model=list[ApplicationForEmployer],
    summary="Отклики на вакансию, отсортированы по совпадению",
    responses=error_responses(401, 403, 404),
)
async def list_need_applications(
    need_id: int, user: CurrentEmployer, db: DbSession
) -> list[ApplicationForEmployer]:
    return await service.list_for_need(db, user.id, need_id)


@employer_router.post(
    "/applications/{application_id}/view",
    response_model=ApplicationForEmployer,
    summary="Отметить просмотренным",
    responses=TRANSITION,
)
async def view_application(
    application_id: int, user: CurrentEmployer, db: DbSession
) -> ApplicationForEmployer:
    return await service.view(db, user.id, application_id)


@employer_router.post(
    "/applications/{application_id}/accept",
    response_model=ApplicationForEmployer,
    summary="Принять отклик (пригласить на общение)",
    responses=TRANSITION,
)
async def accept_application(
    application_id: int, user: CurrentEmployer, db: DbSession
) -> ApplicationForEmployer:
    return await service.decide(db, user.id, application_id, ApplicationStatus.accepted)


@employer_router.post(
    "/applications/{application_id}/reject",
    response_model=ApplicationForEmployer,
    summary="Отклонить отклик",
    responses=TRANSITION,
)
async def reject_application(
    application_id: int, user: CurrentEmployer, db: DbSession
) -> ApplicationForEmployer:
    return await service.decide(db, user.id, application_id, ApplicationStatus.rejected)
