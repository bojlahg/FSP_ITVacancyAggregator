from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse
from app.modules.fsp.schemas import FspLinkRequest, FspProfileOut, OidcStartOut

router = APIRouter(tags=["candidate: fsp"])


@router.get(
    "/candidates/me/fsp",
    response_model=FspProfileOut,
    summary="Мои данные ФСП (без истории — linked=false)",
    responses=error_responses(401, 403),
)
async def get_my_fsp(user: CurrentCandidate, db: DbSession) -> FspProfileOut:
    raise NotImplementedApiError()


@router.post(
    "/candidates/me/fsp/link",
    response_model=FspProfileOut,
    summary="Ручная привязка ФСП ID с согласием на импорт",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def link_fsp(body: FspLinkRequest, user: CurrentCandidate, db: DbSession) -> FspProfileOut:
    raise NotImplementedApiError()


@router.delete(
    "/candidates/me/fsp",
    response_model=MessageResponse,
    summary="Отвязать ФСП и удалить импортированные данные",
    responses=error_responses(401, 403),
)
async def unlink_fsp(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    raise NotImplementedApiError()


@router.get(
    "/fsp/oidc/start",
    response_model=OidcStartOut,
    summary="Начать привязку через ФСП ID (OIDC, Keycloak)",
    responses=error_responses(401, 403),
)
async def oidc_start(user: CurrentCandidate) -> OidcStartOut:
    raise NotImplementedApiError()


@router.get(
    "/fsp/oidc/callback",
    response_class=RedirectResponse,
    status_code=302,
    summary="Callback OIDC: проверка state, обмен кода, импорт достижений, редирект в кабинет",
)
async def oidc_callback(db: DbSession, code: str = Query(), state: str = Query()) -> RedirectResponse:
    raise NotImplementedApiError()
