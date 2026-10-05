from fastapi import APIRouter, Query

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.candidates import privacy, service
from app.modules.candidates.schemas import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    CompanyRef,
    ConsentOut,
    ConsentUpdate,
    PrivacySettings,
    SearchStatusUpdate,
)

router = APIRouter(prefix="/candidates/me", tags=["candidate: profile"])

AUTH_ERRORS = error_responses(401, 403)


@router.get("", response_model=CandidateProfileOut, summary="Свой профиль", responses=AUTH_ERRORS)
async def get_my_profile(user: CurrentCandidate, db: DbSession) -> CandidateProfileOut:
    return await service.profile_out(db, await service.get_by_user(db, user.id))


@router.put(
    "",
    response_model=CandidateProfileOut,
    summary="Обновить профиль (форма или подтверждённое предзаполнение из резюме)",
    responses=error_responses(401, 403, 422),
)
async def update_my_profile(
    body: CandidateProfileUpdate, user: CurrentCandidate, db: DbSession
) -> CandidateProfileOut:
    return await service.update_profile(db, await service.get_by_user(db, user.id), body)


@router.put(
    "/privacy",
    response_model=PrivacySettings,
    summary="Настройки приватности",
    responses=error_responses(401, 403, 422),
)
async def update_privacy(body: PrivacySettings, user: CurrentCandidate, db: DbSession) -> PrivacySettings:
    return await privacy.update_privacy(db, await service.get_by_user(db, user.id), body)


@router.put(
    "/search-status",
    response_model=CandidateProfileOut,
    summary="Статус поиска: активно ищу, открыт к предложениям, не ищу (профиль скрыт)",
    responses=error_responses(401, 403, 422),
)
async def update_search_status(
    body: SearchStatusUpdate, user: CurrentCandidate, db: DbSession
) -> CandidateProfileOut:
    candidate = await service.get_by_user(db, user.id)
    await privacy.update_search_status(db, candidate, body)
    return await service.profile_out(db, candidate)


@router.get(
    "/companies",
    response_model=list[CompanyRef],
    summary="Найти компании по названию (для списка скрытых) или получить названия по id",
    responses=AUTH_ERRORS,
)
async def find_companies(
    user: CurrentCandidate,
    db: DbSession,
    q: str | None = Query(default=None, min_length=2, max_length=100),
    ids: list[int] = Query(default=[]),
) -> list[CompanyRef]:
    return await privacy.find_companies(db, q, ids)


@router.get("/consents", response_model=list[ConsentOut], summary="Состояние согласий", responses=AUTH_ERRORS)
async def list_consents(user: CurrentCandidate, db: DbSession) -> list[ConsentOut]:
    return await privacy.list_consents(db, await service.get_by_user(db, user.id))


@router.put(
    "/consents",
    response_model=list[ConsentOut],
    summary="Дать или отозвать согласие (152-ФЗ); согласие на обработку ПДн отзывается удалением аккаунта",
    responses=error_responses(401, 403, 409, 422),
)
async def update_consent(body: ConsentUpdate, user: CurrentCandidate, db: DbSession) -> list[ConsentOut]:
    return await privacy.update_consent(db, await service.get_by_user(db, user.id), body)


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Удалить аккаунт: мягкое удаление с обезличиванием ПДн",
    responses=AUTH_ERRORS,
)
async def delete_my_account(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    await privacy.delete_account(db, await service.get_by_user(db, user.id))
    return MessageResponse(message="Аккаунт удалён, персональные данные обезличены")
