from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.enums import Role
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False, description="Access JWT из POST /auth/login")

DbSession = Annotated[AsyncSession, Depends(get_session)]


@dataclass(frozen=True)
class AuthUser:
    id: int
    role: Role


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser:
    if credentials is None:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Токен недействителен или истёк") from exc
    return AuthUser(id=int(payload["sub"]), role=Role(payload["role"]))


def _require(role: Role):
    def dependency(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role != role:
            raise ForbiddenError()
        return user

    return dependency


def require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise NotFoundError()


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
CurrentCandidate = Annotated[AuthUser, Depends(_require(Role.candidate))]
CurrentEmployer = Annotated[AuthUser, Depends(_require(Role.employer))]
CurrentAdmin = Annotated[AuthUser, Depends(_require(Role.admin))]
