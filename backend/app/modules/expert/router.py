from fastapi import APIRouter

from app.core.deps import CurrentExpert, CurrentExpertOrAdmin, DbSession
from app.core.errors import error_responses
from app.modules.expert import service
from app.modules.expert.schemas import ExpertLabelRequest, ExpertProgress, ExpertSummary, ExpertTask

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
