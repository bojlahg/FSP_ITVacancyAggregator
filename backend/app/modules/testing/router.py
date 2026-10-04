from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import error_responses
from app.modules.candidates import service as candidates_service
from app.modules.testing import service
from app.modules.testing.schemas import (
    AnswerAck,
    AnswerRequest,
    AttemptCreate,
    AttemptOut,
    AttemptResultOut,
    CurrentItem,
)

router = APIRouter(prefix="/tests/attempts", tags=["candidate: testing"])


@router.post(
    "",
    response_model=AttemptOut,
    status_code=201,
    summary="Начать тест на грейд (409 — действует ограничение по частоте)",
    responses=error_responses(401, 403, 409, 422),
)
async def start_attempt(body: AttemptCreate, user: CurrentCandidate, db: DbSession) -> AttemptOut:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.start(db, candidate, body)


@router.get(
    "/{attempt_id}",
    response_model=AttemptOut,
    summary="Состояние попытки",
    responses=error_responses(401, 403, 404),
)
async def get_attempt(attempt_id: int, user: CurrentCandidate, db: DbSession) -> AttemptOut:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.get_attempt(db, candidate, attempt_id)


@router.get(
    "/{attempt_id}/current",
    response_model=CurrentItem,
    summary="Текущее задание (по одному, без возврата назад)",
    responses=error_responses(401, 403, 404),
)
async def get_current_item(attempt_id: int, user: CurrentCandidate, db: DbSession) -> CurrentItem:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.current_item(db, candidate, attempt_id)


@router.post(
    "/{attempt_id}/answer",
    response_model=AnswerAck,
    summary="Ответ на текущее задание",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def answer_item(
    attempt_id: int, body: AnswerRequest, user: CurrentCandidate, db: DbSession
) -> AnswerAck:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.answer(db, candidate, attempt_id, body)


@router.get(
    "/{attempt_id}/result",
    response_model=AttemptResultOut,
    summary="Результат: грейд, θ, перцентиль, разбор по темам, следующие шаги",
    responses=error_responses(401, 403, 404, 409),
)
async def get_result(attempt_id: int, user: CurrentCandidate, db: DbSession) -> AttemptResultOut:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.result(db, candidate, attempt_id)
