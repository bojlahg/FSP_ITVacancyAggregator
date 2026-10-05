from fastapi import APIRouter, Query

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.modules.candidates import service as candidates_service
from app.modules.tasks import service
from app.modules.tasks.schemas import (
    EmployerTaskCreate,
    EmployerTaskOut,
    TaskAssignmentForCandidate,
    TaskRating,
    TaskSubmissionForEmployer,
    TaskSubmit,
    TaskTemplateOption,
)

candidate_router = APIRouter(tags=["candidate: tasks"])
employer_router = APIRouter(prefix="/employer-tasks", tags=["employer: tasks"])


@candidate_router.get(
    "/candidates/me/tasks",
    response_model=list[TaskAssignmentForCandidate],
    summary="Регулярные задания от работодателей",
    description=(
        "Кандидату с категорией раз в неделю предлагается одно задание по его специализации и грейду, "
        "не больше одного активного; просроченные помечаются expired."
    ),
    responses=error_responses(401, 403),
)
async def list_my_tasks(user: CurrentCandidate, db: DbSession) -> list[TaskAssignmentForCandidate]:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.my_tasks(db, candidate)


@candidate_router.post(
    "/tasks/assignments/{assignment_id}/submit",
    response_model=TaskAssignmentForCandidate,
    summary="Отправить решение или подход",
    description=(
        "kind=auto проверяется сразу; верное решение подтверждает навыки шаблона (task_confirmed). "
        "kind=approach — по чек-листу (LLM отмечает критерии) или ждёт оценки работодателя. "
        "409 assignment_closed — задание уже решено, пропущено или просрочено."
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def submit_task(
    assignment_id: int, body: TaskSubmit, user: CurrentCandidate, db: DbSession
) -> TaskAssignmentForCandidate:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.submit(db, candidate, user.id, assignment_id, body)


@candidate_router.post(
    "/tasks/assignments/{assignment_id}/skip",
    response_model=TaskAssignmentForCandidate,
    summary="Пропустить задание",
    responses=error_responses(401, 403, 404, 409),
)
async def skip_task(assignment_id: int, user: CurrentCandidate, db: DbSession) -> TaskAssignmentForCandidate:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.skip(db, candidate, assignment_id)


@employer_router.get(
    "", response_model=list[EmployerTaskOut], summary="Мои задания", responses=error_responses(401, 403)
)
async def list_employer_tasks(user: CurrentEmployer, db: DbSession) -> list[EmployerTaskOut]:
    return await service.list_tasks(db, user.id)


@employer_router.post(
    "",
    response_model=EmployerTaskOut,
    status_code=201,
    summary="Создать короткое задание для кандидатов категории",
    responses=error_responses(401, 403, 404, 422),
)
async def create_employer_task(
    body: EmployerTaskCreate, user: CurrentEmployer, db: DbSession
) -> EmployerTaskOut:
    return await service.create_task(db, user.id, body)


@employer_router.get(
    "/templates",
    response_model=list[TaskTemplateOption],
    summary="Шаблоны банка для автопроверяемого задания",
    description="С need_id — специализация из потребности, сначала шаблоны с её навыками.",
    responses=error_responses(401, 403, 404, 422),
)
async def list_task_templates(
    user: CurrentEmployer,
    db: DbSession,
    specialization: str | None = Query(default=None),
    need_id: int | None = Query(default=None),
) -> list[TaskTemplateOption]:
    return await service.template_options(db, user.id, specialization, need_id)


@employer_router.get(
    "/{task_id}/submissions",
    response_model=list[TaskSubmissionForEmployer],
    summary="Ответы кандидатов (обезличенно)",
    responses=error_responses(401, 403, 404),
)
async def list_task_submissions(
    task_id: int, user: CurrentEmployer, db: DbSession
) -> list[TaskSubmissionForEmployer]:
    return await service.submissions(db, user.id, task_id)


@employer_router.post(
    "/{task_id}/submissions/{assignment_id}/rate",
    response_model=TaskSubmissionForEmployer,
    summary="Оценить ответ 1–5",
    description="Для решений без автопроверки и чек-листа оценка становится score: (оценка − 1) / 4.",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def rate_submission(
    task_id: int, assignment_id: int, body: TaskRating, user: CurrentEmployer, db: DbSession
) -> TaskSubmissionForEmployer:
    return await service.rate(db, user.id, task_id, assignment_id, body)
