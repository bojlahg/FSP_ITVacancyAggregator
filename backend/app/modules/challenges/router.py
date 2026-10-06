from fastapi import APIRouter

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.modules.candidates import service as candidates_service
from app.modules.challenges import service
from app.modules.challenges.schemas import (
    ChallengeAttemptResult,
    ChallengeCard,
    ChallengeCreate,
    ChallengeOut,
    ChallengeSolver,
)
from app.modules.testing.schemas import AnswerAck, AnswerRequest, CurrentItem

candidate_router = APIRouter(tags=["candidate: challenges"])
employer_router = APIRouter(prefix="/employer-challenges", tags=["employer: challenges"])


# ---------- работодатель ----------


@employer_router.get(
    "", response_model=list[ChallengeOut], summary="Мои челленджи", responses=error_responses(401, 403)
)
async def list_challenges(user: CurrentEmployer, db: DbSession) -> list[ChallengeOut]:
    return await service.list_own(db, user.id)


@employer_router.post(
    "",
    response_model=ChallengeOut,
    status_code=201,
    summary="Создать черновик челленджа со своими вопросами",
    description=(
        "Вопросы: single_choice, multi_choice, numeric, open_approach. Лимиты — content/challenges.yaml. "
        "Результат не влияет на грейд и статусы навыков кандидата."
    ),
    responses=error_responses(401, 403, 422),
)
async def create_challenge(body: ChallengeCreate, user: CurrentEmployer, db: DbSession) -> ChallengeOut:
    return await service.create(db, user.id, body)


@employer_router.get(
    "/{challenge_id}",
    response_model=ChallengeOut,
    summary="Челлендж с вопросами и ключами (только автору)",
    responses=error_responses(401, 403, 404),
)
async def get_challenge(challenge_id: int, user: CurrentEmployer, db: DbSession) -> ChallengeOut:
    return await service.get_own(db, user.id, challenge_id)


@employer_router.put(
    "/{challenge_id}",
    response_model=ChallengeOut,
    summary="Изменить черновик",
    description="409 challenge_not_draft — опубликованный челлендж не меняется.",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_challenge(
    challenge_id: int, body: ChallengeCreate, user: CurrentEmployer, db: DbSession
) -> ChallengeOut:
    return await service.update(db, user.id, challenge_id, body)


@employer_router.post(
    "/{challenge_id}/publish",
    response_model=ChallengeOut,
    summary="Опубликовать: челлендж увидят кандидаты подходящей категории",
    description=(
        "Тексты проверяются теми же правилами, что и потребность (content/need_text_rules.yaml): "
        "409 challenge_text_discriminatory — есть запрещённые требования, details.issues — что исправить."
    ),
    responses=error_responses(401, 403, 404, 409),
)
async def publish_challenge(challenge_id: int, user: CurrentEmployer, db: DbSession) -> ChallengeOut:
    return await service.publish(db, user.id, challenge_id)


@employer_router.post(
    "/{challenge_id}/close",
    response_model=ChallengeOut,
    summary="Закрыть: новые кандидаты не начнут, начатые попытки можно завершить",
    responses=error_responses(401, 403, 404),
)
async def close_challenge(challenge_id: int, user: CurrentEmployer, db: DbSession) -> ChallengeOut:
    return await service.close(db, user.id, challenge_id)


@employer_router.get(
    "/{challenge_id}/solvers",
    response_model=list[ChallengeSolver],
    summary="Решившие по убыванию результата",
    description="Карточки обезличены; контакты в открытых ответах скрыты, пока нет записи в contact_unlocks.",
    responses=error_responses(401, 403, 404),
)
async def list_solvers(challenge_id: int, user: CurrentEmployer, db: DbSession) -> list[ChallengeSolver]:
    return await service.solvers(db, user.id, challenge_id)


# ---------- кандидат ----------


@candidate_router.get(
    "/challenges",
    response_model=list[ChallengeCard],
    summary="Челленджи компаний по вашей категории",
    description="Опубликованные челленджи вашей специализации и грейда и те, что вы уже начинали.",
    responses=error_responses(401, 403),
)
async def list_available(user: CurrentCandidate, db: DbSession) -> list[ChallengeCard]:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.available(db, candidate)


@candidate_router.post(
    "/challenges/{challenge_id}/start",
    response_model=ChallengeAttemptResult,
    summary="Начать челлендж (одна попытка; повторный вызов возвращает её же)",
    responses=error_responses(401, 403, 404),
)
async def start_challenge(challenge_id: int, user: CurrentCandidate, db: DbSession) -> ChallengeAttemptResult:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.start(db, candidate, challenge_id)


@candidate_router.get(
    "/challenge-attempts/{attempt_id}",
    response_model=ChallengeAttemptResult,
    summary="Попытка: прогресс и результат",
    responses=error_responses(401, 403, 404),
)
async def get_attempt(attempt_id: int, user: CurrentCandidate, db: DbSession) -> ChallengeAttemptResult:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.result(db, candidate, attempt_id)


@candidate_router.get(
    "/challenge-attempts/{attempt_id}/current",
    response_model=CurrentItem,
    summary="Текущий вопрос (без ключа); время считает сервер",
    responses=error_responses(401, 403, 404),
)
async def current_question(attempt_id: int, user: CurrentCandidate, db: DbSession) -> CurrentItem:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.current(db, candidate, attempt_id)


@candidate_router.post(
    "/challenge-attempts/{attempt_id}/answer",
    response_model=AnswerAck,
    summary="Ответ на текущий вопрос",
    description="409 not_current_item — вопрос уже не текущий; 409 attempt_finished — челлендж пройден.",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def answer_question(
    attempt_id: int, body: AnswerRequest, user: CurrentCandidate, db: DbSession
) -> AnswerAck:
    candidate = await candidates_service.get_by_user(db, user.id)
    return await service.answer(db, candidate, attempt_id, body)
