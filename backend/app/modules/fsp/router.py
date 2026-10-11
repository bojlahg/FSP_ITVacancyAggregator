from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import AppError, error_responses
from app.core.schemas import MessageResponse
from app.modules.candidates import service as candidates_service
from app.modules.fsp import service
from app.modules.fsp.schemas import FspLinkRequest, FspProfileOut, OidcStartOut

router = APIRouter(tags=["candidate: fsp"])

OIDC_COOKIE_PATH = "/api/v1/fsp/oidc"


@router.get(
    "/candidates/me/fsp",
    response_model=FspProfileOut,
    summary="Мои данные ФСП (без истории — linked=false)",
    responses=error_responses(401, 403),
)
async def get_my_fsp(user: CurrentCandidate, db: DbSession) -> FspProfileOut:
    return await service.profile(db, await candidates_service.get_by_user(db, user.id))


@router.post(
    "/candidates/me/fsp/link",
    response_model=FspProfileOut,
    summary="Ручная привязка ФСП ID с согласием на импорт",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def link_fsp(body: FspLinkRequest, user: CurrentCandidate, db: DbSession) -> FspProfileOut:
    return await service.link_manual(db, await candidates_service.get_by_user(db, user.id), body)


@router.delete(
    "/candidates/me/fsp",
    response_model=MessageResponse,
    summary="Отвязать ФСП и удалить импортированные данные",
    responses=error_responses(401, 403),
)
async def unlink_fsp(user: CurrentCandidate, db: DbSession) -> MessageResponse:
    await service.unlink_own(db, await candidates_service.get_by_user(db, user.id))
    return MessageResponse(message="Данные ФСП удалены")


@router.get(
    "/fsp/oidc/start",
    response_model=OidcStartOut,
    summary="Начать привязку через ФСП ID (OIDC, Keycloak)",
    description=(
        "Возвращает адрес входа ФСП ID (authorization code + PKCE), фронт переводит туда браузер. "
        "State, code_verifier и nonce сохраняются в подписанной httpOnly cookie на время флоу. "
        "503 `fsp_idp_unavailable` — IdP недоступен."
    ),
    responses=error_responses(400, 401, 403, 422),
)
async def oidc_start(
    response: Response,
    user: CurrentCandidate,
    db: DbSession,
    consent: bool = Query(description="Согласие на импорт данных из реестра ФСП"),
) -> OidcStartOut:
    candidate = await candidates_service.get_by_user(db, user.id)
    url, flow_cookie = await service.oidc_start(candidate, consent)
    settings = get_settings()
    response.set_cookie(
        settings.fsp_oidc_cookie_name,
        flow_cookie,
        max_age=settings.fsp_oidc_state_ttl_seconds,
        path=OIDC_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return OidcStartOut(authorization_url=url)


@router.get(
    "/fsp/oidc/callback",
    response_class=RedirectResponse,
    status_code=302,
    summary="Callback OIDC: проверка state, обмен кода, импорт достижений, редирект в кабинет",
    description=(
        "Всегда редиректит в кабинет кандидата: `?fsp_oidc=linked` или `?fsp_oidc=error&reason=<код>` "
        "(fsp_oidc_state_invalid, fsp_oidc_denied, fsp_oidc_code_rejected, fsp_oidc_token_invalid, "
        "fsp_oidc_no_fsp_id, fsp_id_taken, fsp_participant_not_found, fsp_idp_unavailable, "
        "fsp_registry_unavailable)."
    ),
)
async def oidc_callback(
    request: Request,
    db: DbSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None, description="Ошибка от IdP, например access_denied"),
) -> RedirectResponse:
    settings = get_settings()
    try:
        await service.oidc_complete(
            db, request.cookies.get(settings.fsp_oidc_cookie_name), None if error else code, state
        )
        outcome = {"fsp_oidc": "linked"}
    except AppError as exc:
        await db.rollback()
        outcome = {"fsp_oidc": "error", "reason": exc.code}
    target = f"{settings.public_base_url.rstrip('/')}{settings.fsp_oidc_return_path}?{urlencode(outcome)}"
    redirect = RedirectResponse(target, status_code=302)
    redirect.delete_cookie(settings.fsp_oidc_cookie_name, path=OIDC_COOKIE_PATH)
    return redirect
