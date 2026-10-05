from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentExpert, CurrentExpertOrAdmin, DbSession
from app.core.enums import Grade, Role
from app.core.errors import error_responses
from app.modules.expert import angoff_service, service
from app.modules.expert.schemas import (
    AngoffProgress,
    AngoffRatingRequest,
    AngoffSummary,
    AngoffTasks,
    ExpertLabelRequest,
    ExpertProgress,
    ExpertSummary,
    ExpertTask,
)

router = APIRouter(prefix="/expert", tags=["expert"])


@router.get(
    "/next",
    response_model=ExpertTask,
    summary="Следующая пара «потребность — кандидат» для разметки (карточка без score и места в выдаче)",
    responses=error_responses(401, 403),
)
async def next_pair(user: CurrentExpert, db: DbSession) -> ExpertTask:
    return await service.next_task(db, user.id)


@router.post(
    "/pairs/{pair_id}/label",
    response_model=ExpertProgress,
    summary="Оценка пары по шкале 0–3; повторная оценка заменяет прежнюю",
    responses=error_responses(401, 403, 404, 422),
)
async def label_pair(
    pair_id: int, body: ExpertLabelRequest, user: CurrentExpert, db: DbSession
) -> ExpertProgress:
    return await service.label(db, user.id, pair_id, body.label)


@router.get(
    "/summary",
    response_model=ExpertSummary,
    summary="Метрики подбора на экспертных оценках: P@5 ITScout и ключевых слов, Спирмен, согласие экспертов",
    responses=error_responses(401, 403),
)
async def summary(user: CurrentExpertOrAdmin, db: DbSession) -> ExpertSummary:
    return await service.summary(db)


@router.get(
    "/angoff/tasks",
    response_model=AngoffTasks,
    summary="Modified Angoff: шаблоны у порога грейда с примером экземпляра (без ключей) и оценками",
    description="404 specialization_not_found — для специализации нет теста.",
    responses=error_responses(401, 403, 404, 422),
)
async def angoff_tasks(
    user: CurrentExpert,
    db: DbSession,
    specialization: Annotated[str, Query(max_length=32)],
    grade: Annotated[
        Grade, Query(description="Граница грейда: минимально компетентный кандидат этого грейда")
    ],
) -> AngoffTasks:
    return await angoff_service.tasks(db, user.id, specialization, grade)


@router.put(
    "/angoff/ratings",
    response_model=AngoffProgress,
    summary="Modified Angoff: оценка шаблона 0–1; повторная оценка заменяет прежнюю",
    description="404 template_not_found — шаблона нет в наборе для этой специализации и грейда.",
    responses=error_responses(401, 403, 404, 422),
)
async def angoff_rate(body: AngoffRatingRequest, user: CurrentExpert, db: DbSession) -> AngoffProgress:
    return await angoff_service.rate(db, user.id, body)


@router.get(
    "/angoff/summary",
    response_model=AngoffSummary,
    summary="Modified Angoff: рекомендуемые пороги грейдов по оценкам экспертов против действующих",
    description=(
        "Порог эксперта — θ, при котором ожидаемый балл по набору равен сумме его оценок. "
        "Пороги в blueprints.yaml автоматически не меняются. 404 specialization_not_found."
    ),
    responses=error_responses(401, 403, 404, 422),
)
async def angoff_summary(
    user: CurrentExpertOrAdmin, db: DbSession, specialization: Annotated[str, Query(max_length=32)]
) -> AngoffSummary:
    expert_id = user.id if user.role == Role.expert else None
    return await angoff_service.summary(db, expert_id, specialization)
