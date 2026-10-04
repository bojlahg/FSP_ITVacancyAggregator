from fastapi import APIRouter

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse
from app.modules.candidates.schemas import (
    CandidateProfileOut,
    CandidateProfileUpdate,
    ConsentOut,
    ConsentUpdate,
    PrivacySettings,
)

router = APIRouter(prefix="/candidates/me", tags=["candidate: profile"])

AUTH_ERRORS = error_responses(401, 403)


@router.get("", response_model=CandidateProfileOut, summary="Свой профиль", responses=AUTH_ERRORS)
async def get_my_profile(user: CurrentCandidate, db: DbSession) -> CandidateProfileOut:
    raise NotImplementedApiError()


@router.put(
    "",
    response_model=CandidateProfileOut,
    summary="Обновить профиль (форма или подтверждённое предзаполнение из резюме)",
    responses=error_responses(401, 403, 422),
)
async def update_my_profile(
    body: CandidateProfileUpdate, user: CurrentCandidate, db: DbSession
) -> CandidateProfileOut:
    raise NotImplementedApiError()


@router.put(
    "/privacy",
    response_model=PrivacySettings,
    summary="Настройки приватности",
    responses=error_responses(401, 403, 422),
)
async def update_privacy(body: PrivacySettings, user: CurrentCandidate, db: DbSession) -> PrivacySettings:
    raise NotImplementedApiError()


@router.get("/consents", response_model=list[ConsentOut], summary="Состояние согласий", responses=AUTH_ERRORS)
async def list_consents(user: CurrentCandidate, db: DbSession) -> list[ConsentOut]:
    raise NotImplementedApiError()


@router.put(
    "/consents",
    response_model=list[ConsentOut],
    summary="Дать или отозвать согласие (152-ФЗ)",
    responses=error_responses(401, 403, 422),
)
async def update_consent(body: ConsentUpdate, user: CurrentCandidate, db: DbSession) -> list[ConsentOut]:
    raise NotImplementedApiError()


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Удалить аккаунт: мягкое удаление с обезличиванием ПДн",
    responses=AUTH_ERRORS,
)
async def delete_my_account(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()
