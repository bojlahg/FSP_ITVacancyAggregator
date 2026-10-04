from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession, require_demo_mode
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse
from app.modules.auth.schemas import (
    DemoLoginRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    summary="Регистрация по email",
    responses=error_responses(409, 422, 429),
)
async def register(body: RegisterRequest, db: DbSession) -> TokenResponse:
    raise NotImplementedApiError()


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Подтверждение адреса по токену из письма",
    responses=error_responses(400, 422),
)
async def verify_email(body: VerifyEmailRequest, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Повторно отправить письмо подтверждения",
    responses=error_responses(401, 429),
)
async def resend_verification(user: CurrentUser, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход: access-токен в ответе, refresh-токен в httpOnly cookie",
    responses=error_responses(401, 422, 429),
)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    raise NotImplementedApiError()


@router.post(
    "/demo-login",
    response_model=TokenResponse,
    summary="Вход под демо-аккаунтом (только DEMO_MODE)",
    dependencies=[Depends(require_demo_mode)],
    responses=error_responses(404),
)
async def demo_login(body: DemoLoginRequest, db: DbSession) -> TokenResponse:
    raise NotImplementedApiError()


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Новый access-токен по refresh cookie (с ротацией)",
    responses=error_responses(401),
)
async def refresh(db: DbSession) -> TokenResponse:
    raise NotImplementedApiError()


@router.post("/logout", response_model=MessageResponse, summary="Выход: отзыв refresh-токена")
async def logout(db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()


me_router = APIRouter(tags=["auth"])


@me_router.get("/me", response_model=UserOut, summary="Текущий пользователь", responses=error_responses(401))
async def me(user: CurrentUser, db: DbSession) -> UserOut:
    raise NotImplementedApiError()
