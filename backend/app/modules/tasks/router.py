from fastapi import APIRouter

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.tasks.schemas import (
    EmployerTaskCreate,
    EmployerTaskOut,
    TaskAssignmentForCandidate,
    TaskRating,
    TaskSubmissionForEmployer,
    TaskSubmit,
)

candidate_router = APIRouter(tags=["candidate: tasks"])
employer_router = APIRouter(prefix="/employer-tasks", tags=["employer: tasks"])


@candidate_router.get(
    "/candidates/me/tasks",
    response_model=list[TaskAssignmentForCandidate],
    summary="Регулярные задания от работодателей",
    responses=error_responses(401, 403),
)
async def list_my_tasks(user: CurrentCandidate, db: DbSession) -> list[TaskAssignmentForCandidate]:
    raise NotImplementedApiError()


@candidate_router.post(
    "/tasks/assignments/{assignment_id}/submit",
    response_model=TaskAssignmentForCandidate,
    summary="Отправить решение или подход",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def submit_task(
    assignment_id: int, body: TaskSubmit, user: CurrentCandidate, db: DbSession
) -> TaskAssignmentForCandidate:
    raise NotImplementedApiError()


@employer_router.get(
    "", response_model=list[EmployerTaskOut], summary="Мои задания", responses=error_responses(401, 403)
)
async def list_employer_tasks(user: CurrentEmployer, db: DbSession) -> list[EmployerTaskOut]:
    raise NotImplementedApiError()


@employer_router.post(
    "",
    response_model=EmployerTaskOut,
    status_code=201,
    summary="Создать короткое задание для кандидатов категории",
    responses=error_responses(401, 403, 422),
)
async def create_employer_task(
    body: EmployerTaskCreate, user: CurrentEmployer, db: DbSession
) -> EmployerTaskOut:
    raise NotImplementedApiError()


@employer_router.get(
    "/{task_id}/submissions",
    response_model=list[TaskSubmissionForEmployer],
    summary="Ответы кандидатов (обезличенно)",
    responses=error_responses(401, 403, 404),
)
async def list_task_submissions(
    task_id: int, user: CurrentEmployer, db: DbSession
) -> list[TaskSubmissionForEmployer]:
    raise NotImplementedApiError()


@employer_router.post(
    "/{task_id}/submissions/{assignment_id}/rate",
    response_model=TaskSubmissionForEmployer,
    summary="Оценить ответ 1–5",
    responses=error_responses(401, 403, 404, 422),
)
async def rate_submission(
    task_id: int, assignment_id: int, body: TaskRating, user: CurrentEmployer, db: DbSession
) -> TaskSubmissionForEmployer:
    raise NotImplementedApiError()
