from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.enums import Role
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False, description="Access JWT из POST /auth/login")
_api_key = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API-ключ работодателя для ATS: выпускается в профиле компании, даёт методы работодателя",
)

DbSession = Annotated[AsyncSession, Depends(get_session)]


@dataclass(frozen=True)
class AuthUser:
    id: int
    role: Role
    email_verified: bool = True


async def get_session_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> AuthUser:
    from app.modules.auth.models import User

    if credentials is None:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Токен недействителен или истёк") from exc
    # Access JWT живёт до истечения срока: удалённый аккаунт отсекаем здесь, до бизнес-логики (§13)
    user = await db.get(User, int(payload["sub"]))
    if user is None or user.deleted_at is not None:
        raise UnauthorizedError("Аккаунт удалён")
    return AuthUser(id=user.id, role=Role(payload["role"]), email_verified=user.email_verified_at is not None)


def _ensure_verified(user: AuthUser) -> AuthUser:
    # §2: при EMAIL_VERIFICATION_REQUIRED без подтверждённой почты доступны только вход, /auth/me и письмо
    if get_settings().email_verification_required and not user.email_verified:
        raise ForbiddenError(
            "Подтвердите почту: перейдите по ссылке из письма, отправленного при регистрации",
            code="email_not_verified",
        )
    return user


async def get_current_user(user: Annotated[AuthUser, Depends(get_session_user)]) -> AuthUser:
    return _ensure_verified(user)


def _require(role: Role):
    def dependency(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role != role:
            raise ForbiddenError()
        return user

    return dependency


def require_debug_tools() -> None:
    """Отладочный раздел есть только при DEBUG_TOOLS=true; иначе его эндпоинтов как будто нет."""
    if not get_settings().debug_tools:
        raise NotFoundError()


def require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise NotFoundError()


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
# Сессия без проверки подтверждения почты — только для /auth/me и повторной отправки письма
SessionUser = Annotated[AuthUser, Depends(get_session_user)]
CurrentCandidate = Annotated[AuthUser, Depends(_require(Role.candidate))]
CurrentEmployerSession = Annotated[AuthUser, Depends(_require(Role.employer))]


async def _employer_or_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    api_key: Annotated[str | None, Depends(_api_key)],
    db: DbSession,
) -> AuthUser:
    """Методы работодателя доступны и из кабинета, и из ATS по ключу X-API-Key."""
    if credentials is None and api_key:
        from app.modules.integrations.service import authenticate_key

        return AuthUser(id=await authenticate_key(db, api_key), role=Role.employer)
    user = _ensure_verified(await get_session_user(credentials, db))
    if user.role != Role.employer:
        raise ForbiddenError()
    return user


CurrentEmployer = Annotated[AuthUser, Depends(_employer_or_api_key)]
CurrentAdmin = Annotated[AuthUser, Depends(_require(Role.admin))]
CurrentExpert = Annotated[AuthUser, Depends(_require(Role.expert))]


def _require_any(*roles: Role):
    def dependency(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role not in roles:
            raise ForbiddenError()
        return user

    return dependency


CurrentExpertOrAdmin = Annotated[AuthUser, Depends(_require_any(Role.expert, Role.admin))]
