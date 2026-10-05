"""OIDC-клиент «Войти через ФСП ID» (§9.3): authorization code + PKCE, проверка id_token по JWKS.

Состояние флоу (state, code_verifier, nonce, кандидат) хранится в подписанной httpOnly cookie,
которую ставит /fsp/oidc/start: так callback привязан и к браузеру, и к кандидату, а verifier
не уходит в URL. Протокол стандартный — в проде issuer меняется на настоящий ФСП ID настройками.
"""

import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import JWT_ALGORITHM

log = logging.getLogger("itscout.fsp.oidc")

# Подмена транспорта в тестах: сеть к IdP не нужна
http_transport: httpx.AsyncBaseTransport | None = None

# Только асимметричные алгоритмы: HS* с публичным ключом как секретом — классическая подмена алгоритма
ALLOWED_ALGORITHMS = {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "EdDSA"}
FLOW_TOKEN_TYPE = "fsp_oidc_flow"


class OidcError(AppError):
    status_code = 400
    code = "fsp_oidc_failed"
    message = "Не удалось подтвердить ФСП ID"


class IdpUnavailableError(AppError):
    status_code = 503
    code = "fsp_idp_unavailable"
    message = "Сервис ФСП ID временно недоступен, попробуйте позже"


@dataclass(frozen=True)
class Flow:
    candidate_id: int
    state: str
    verifier: str
    nonce: str


def redirect_uri() -> str:
    settings = get_settings()
    default = f"{settings.public_base_url.rstrip('/')}/api/v1/fsp/oidc/callback"
    return settings.fsp_oidc_redirect_uri or default


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10, transport=http_transport)


async def discovery() -> dict:
    try:
        async with _client() as client:
            response = (await client.get(get_settings().fsp_oidc_discovery_url)).raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("fsp idp discovery error: %s", exc)
        raise IdpUnavailableError() from exc


def new_flow(candidate_id: int) -> Flow:
    return Flow(
        candidate_id=candidate_id,
        state=secrets.token_urlsafe(32),
        verifier=secrets.token_urlsafe(64),
        nonce=secrets.token_urlsafe(32),
    )


def encode_flow(flow: Flow) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "type": FLOW_TOKEN_TYPE,
        "cid": flow.candidate_id,
        "state": flow.state,
        "verifier": flow.verifier,
        "nonce": flow.nonce,
        "iat": now,
        "exp": now + timedelta(seconds=settings.fsp_oidc_state_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_flow(cookie: str | None, state: str | None) -> Flow:
    """Cookie флоу должна быть цела, не просрочена и совпадать со state из callback."""
    invalid = OidcError("Сессия входа через ФСП ID устарела, начните заново", code="fsp_oidc_state_invalid")
    if not cookie or not state:
        raise invalid
    try:
        payload = jwt.decode(cookie, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise invalid from exc
    if payload.get("type") != FLOW_TOKEN_TYPE or not hmac.compare_digest(str(payload.get("state")), state):
        raise invalid
    return Flow(
        candidate_id=int(payload["cid"]),
        state=payload["state"],
        verifier=payload["verifier"],
        nonce=payload["nonce"],
    )


def authorization_url(config: dict, flow: Flow) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(flow.verifier.encode()).digest()).rstrip(b"=")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": get_settings().fsp_oidc_client_id,
            "redirect_uri": redirect_uri(),
            "scope": "openid",
            "state": flow.state,
            "nonce": flow.nonce,
            "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
        }
    )
    return f"{config['authorization_endpoint']}?{query}"


async def exchange_code(code: str, flow: Flow) -> str:
    """Обменивает код на токены и возвращает fsp_id из проверенного id_token."""
    settings = get_settings()
    config = await discovery()
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "client_id": settings.fsp_oidc_client_id,
        "code_verifier": flow.verifier,
    }
    if settings.fsp_oidc_client_secret:
        form["client_secret"] = settings.fsp_oidc_client_secret
    try:
        async with _client() as client:
            response = await client.post(config["token_endpoint"], data=form)
            if response.status_code >= 400:
                log.warning("fsp idp token error %s: %s", response.status_code, response.text[:300])
                raise OidcError(
                    "ФСП ID не подтвердил вход, попробуйте ещё раз", code="fsp_oidc_code_rejected"
                )
            id_token = response.json().get("id_token")
            jwks = (await client.get(config["jwks_uri"])).raise_for_status().json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("fsp idp error: %s", exc)
        raise IdpUnavailableError() from exc
    if not id_token:
        raise OidcError("ФСП ID не вернул id_token", code="fsp_oidc_token_invalid")
    claims = verify_id_token(id_token, jwks, issuer=config["issuer"], nonce=flow.nonce)
    fsp_id = claims.get("fsp_id")
    if not isinstance(fsp_id, str) or not fsp_id.strip():
        raise OidcError("В учётной записи ФСП ID нет номера участника", code="fsp_oidc_no_fsp_id")
    return fsp_id.strip()


def verify_id_token(id_token: str, jwks: dict, *, issuer: str, nonce: str) -> dict:
    """Подпись по JWKS IdP, iss, aud = наш client_id, срок действия и nonce этого флоу."""
    invalid = OidcError("Ответ ФСП ID не прошёл проверку", code="fsp_oidc_token_invalid")
    try:
        header = jwt.get_unverified_header(id_token)
        algorithm = header.get("alg")
        if algorithm not in ALLOWED_ALGORITHMS:
            raise invalid
        keys = [key for key in jwks.get("keys", []) if key.get("kid") == header.get("kid")]
        if len(keys) != 1:
            raise invalid
        claims = jwt.decode(
            id_token,
            jwt.PyJWK(keys[0], algorithm=algorithm).key,
            algorithms=[algorithm],
            audience=get_settings().fsp_oidc_client_id,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except (jwt.InvalidTokenError, jwt.PyJWKError) as exc:
        raise invalid from exc
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise invalid
    return claims
