from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession, SessionUser, require_demo_mode
from app.core.errors import AppError, app_error_response, error_responses
from app.core.mail import send_safely
from app.core.ratelimit import limit_auth_requests, limit_login_email
from app.core.schemas import MessageResponse
from app.modules.auth import service
from app.modules.auth.schemas import (
    DemoLoginRequest,
    LoginRequest,
    NotificationSettings,
    RegisterExpertRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)

REFRESH_COOKIE_PATH = "/api/v1/auth"

router = APIRouter(prefix="/auth", tags=["auth"])
RateLimited = [Depends(limit_auth_requests)]
RefreshCookie = Annotated[
    str | None, Cookie(alias=get_settings().refresh_cookie_name, include_in_schema=False)
]


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().refresh_cookie_name, path=REFRESH_COOKIE_PATH)


def _finish(response: Response, background: BackgroundTasks, session: service.Session) -> TokenResponse:
    _set_refresh_cookie(response, session.refresh_token)
    if session.verification_mail is not None:
        background.add_task(send_safely, session.verification_mail)
    return session.response


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Регистрация по email: согласия, письмо подтверждения, сразу выдаётся сессия",
    dependencies=RateLimited,
    responses=error_responses(400, 409, 422, 429),
)
async def register(
    body: RegisterRequest, response: Response, background: BackgroundTasks, db: DbSession
) -> TokenResponse:
    return _finish(response, background, await service.register(db, body))


@router.post(
    "/register-expert",
    response_model=TokenResponse,
    status_code=201,
    summary="Регистрация эксперта разметки по коду-приглашению (экспертная валидация подбора)",
    dependencies=RateLimited,
    responses=error_responses(403, 404, 409, 422, 429),
)
async def register_expert(body: RegisterExpertRequest, response: Response, db: DbSession) -> TokenResponse:
    session = await service.register_expert(db, body)
    _set_refresh_cookie(response, session.refresh_token)
    return session.response


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Подтверждение адреса по токену из письма",
    dependencies=RateLimited,
    responses=error_responses(400, 422, 429),
)
async def verify_email(body: VerifyEmailRequest, db: DbSession) -> MessageResponse:
    await service.verify_email(db, body.token)
    return MessageResponse(message="Почта подтверждена")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Повторно отправить письмо подтверждения",
    dependencies=RateLimited,
    responses=error_responses(401, 429),
)
async def resend_verification(
    user: SessionUser, background: BackgroundTasks, db: DbSession
) -> MessageResponse:
    mail = await service.resend_verification(db, user.id)
    if mail is None:
        return MessageResponse(message="Почта уже подтверждена")
    background.add_task(send_safely, mail)
    return MessageResponse(message="Письмо отправлено")


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход: access-токен в ответе, refresh-токен в httpOnly cookie",
    dependencies=RateLimited,
    responses=error_responses(401, 422, 429),
)
async def login(
    body: LoginRequest, response: Response, background: BackgroundTasks, db: DbSession
) -> TokenResponse:
    await limit_login_email(db, body.email)
    return _finish(response, background, await service.login(db, body.email, body.password))


@router.post(
    "/demo-login",
    response_model=TokenResponse,
    summary="Вход под демо-аккаунтом (только DEMO_MODE)",
    dependencies=[Depends(require_demo_mode), *RateLimited],
    responses=error_responses(404, 429),
)
async def demo_login(
    body: DemoLoginRequest, response: Response, background: BackgroundTasks, db: DbSession
) -> TokenResponse:
    return _finish(response, background, await service.demo_login(db, body.persona))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Новый access-токен по refresh cookie (с ротацией; повторное использование отзывает все сессии)",
    responses=error_responses(401),
)
async def refresh(
    response: Response, background: BackgroundTasks, db: DbSession, refresh_token: RefreshCookie = None
) -> TokenResponse | JSONResponse:
    try:
        session = await service.refresh(db, refresh_token)
    except AppError as exc:
        # Ответ с ошибкой создаётся заново — cookie чистим прямо на нём
        error = app_error_response(exc)
        _clear_refresh_cookie(error)
        return error
    return _finish(response, background, session)


@router.post("/logout", response_model=MessageResponse, summary="Выход: отзыв refresh-токена")
async def logout(response: Response, db: DbSession, refresh_token: RefreshCookie = None) -> MessageResponse:
    await service.logout(db, refresh_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Вы вышли")


me_router = APIRouter(tags=["auth"])


@me_router.get("/me", response_model=UserOut, summary="Текущий пользователь", responses=error_responses(401))
async def me(user: SessionUser, db: DbSession) -> UserOut:
    return await service.me(db, user.id)


@me_router.put(
    "/me/notifications",
    response_model=UserOut,
    summary="Включить или выключить письма о приглашениях и откликах",
    responses=error_responses(401, 422),
)
async def update_notifications(body: NotificationSettings, user: CurrentUser, db: DbSession) -> UserOut:
    return await service.update_notifications(db, user.id, body)
