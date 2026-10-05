from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentExpert, CurrentExpertOrAdmin, DbSession
from app.core.enums import Grade, Role
from app.core.errors import error_responses
from app.modules.expert import angoff_service, service
from app.modules.expert.schemas import (
    AngoffHofsteeRequest,
    AngoffHofsteeValues,
    AngoffImpact,
    AngoffProgress,
    AngoffRatingRequest,
    AngoffRoundStart,
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
    summary="Modified Angoff: шаблоны у порога грейда с примером экземпляра (без ключей) и оценками раунда",
    description=(
        "Раунд 2 дополнительно отдаёт собственную оценку раунда 1 и медиану и разброс оценок группы. "
        "404 specialization_not_found — для специализации нет теста; "
        "409 round1_incomplete — раунд 2 до полного раунда 1."
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def angoff_tasks(
    user: CurrentExpert,
    db: DbSession,
    specialization: Annotated[str, Query(max_length=32)],
    grade: Annotated[
        Grade, Query(description="Граница грейда: минимально компетентный кандидат этого грейда")
    ],
    round_: Annotated[int, Query(alias="round", ge=1, le=2, description="Раунд оценки")] = 1,
) -> AngoffTasks:
    return await angoff_service.tasks(db, user.id, specialization, grade, round_)


@router.put(
    "/angoff/ratings",
    response_model=AngoffProgress,
    summary="Modified Angoff: оценка шаблона 0–1 в раунде; повторная оценка заменяет прежнюю",
    description=(
        "404 template_not_found — шаблона нет в наборе для этой специализации и грейда; "
        "409 round1_incomplete — оценка раунда 2 до полного раунда 1."
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def angoff_rate(body: AngoffRatingRequest, user: CurrentExpert, db: DbSession) -> AngoffProgress:
    return await angoff_service.rate(db, user.id, body)


@router.post(
    "/angoff/round2",
    response_model=AngoffProgress,
    summary="Modified Angoff: начать раунд 2 — копия оценок раунда 1 для пересмотра",
    description=(
        "Уже поставленные оценки раунда 2 не перезаписываются. 404 specialization_not_found; "
        "409 round1_incomplete — раунд 1 не завершён."
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def angoff_start_round2(body: AngoffRoundStart, user: CurrentExpert, db: DbSession) -> AngoffProgress:
    return await angoff_service.start_round2(db, user.id, body.specialization, body.grade)


@router.get(
    "/angoff/impact",
    response_model=AngoffImpact,
    summary="Modified Angoff: после раунда 1 — доли кандидатов по грейдам и пороги группы",
    description=(
        "Доли — по последней завершённой попытке каждого кандидата специализации, при нехватке результатов — "
        "по синтетической популяции. Доступно после полного раунда 1, чтобы не влиять на первичную оценку. "
        "404 specialization_not_found; 409 round1_incomplete."
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def angoff_impact(
    user: CurrentExpert,
    db: DbSession,
    specialization: Annotated[str, Query(max_length=32)],
    grade: Annotated[Grade, Query(description="Граница грейда")],
) -> AngoffImpact:
    return await angoff_service.impact(db, user.id, specialization, grade)


@router.put(
    "/angoff/hofstee",
    response_model=AngoffHofsteeValues,
    summary="Проверка Hofstee: допустимые порог (доля верных) и доля не дотягивающих до грейда",
    description="Повторная отправка заменяет прежние. 404 specialization_not_found; 422 — min > max.",
    responses=error_responses(401, 403, 404, 422),
)
async def angoff_hofstee(
    body: AngoffHofsteeRequest, user: CurrentExpert, db: DbSession
) -> AngoffHofsteeValues:
    return await angoff_service.save_hofstee(db, user.id, body)


@router.get(
    "/angoff/summary",
    response_model=AngoffSummary,
    summary="Modified Angoff: пороги раундов 1 и 2, проверка Hofstee, рекомендация против действующих",
    description=(
        "Порог эксперта — θ, при котором ожидаемый балл по набору равен сумме его оценок. Рекомендация — "
        "по последнему раунду, который прошёл хотя бы один эксперт. "
        "Пороги в blueprints.yaml автоматически не меняются. 404 specialization_not_found."
    ),
    responses=error_responses(401, 403, 404, 422),
)
async def angoff_summary(
    user: CurrentExpertOrAdmin, db: DbSession, specialization: Annotated[str, Query(max_length=32)]
) -> AngoffSummary:
    expert_id = user.id if user.role == Role.expert else None
    return await angoff_service.summary(db, expert_id, specialization)
