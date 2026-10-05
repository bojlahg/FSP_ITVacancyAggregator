"""Привязка ФСП ID через OIDC (§9.3): IdP (Keycloak) и реестр подменены, сеть не нужна."""

import base64
import hashlib
import json
import time
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import ConsentKind, FspLinkMethod
from app.modules.auth.models import Consent
from app.modules.candidates.models import Candidate
from app.modules.fsp import oidc
from app.modules.fsp import service as fsp_service
from app.modules.fsp.evidence import RankRecord, ResultRecord
from tests.test_testing_flow import signup

pytestmark = pytest.mark.usefixtures("db")

API = "/api/v1"
ISSUER = "https://itscout.test/fsp-id/realms/fsp"
INTERNAL = "http://keycloak:8080/fsp-id/realms/fsp"
REGISTRY = {
    "FSP-2026-7781": (
        [
            ResultRecord(
                competition_id="C1",
                competition_name="Кубок России по продуктовому программированию",
                discipline="product",
                level="national",
                format="team",
                held_on=date(2026, 4, 12),
                place=2,
                participants=40,
                team_role="backend",
                prize="prize",
            )
        ],
        [RankRecord("algorithmic", "I", date(2026, 3, 1))],
    ),
    "FSP-2026-1002": ([], [RankRecord("algorithmic", "II", date(2025, 5, 1))]),
}


def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


IDP_KEY = _private_key()
FOREIGN_KEY = _private_key()


class FakeIdp:
    """Discovery, token и JWKS Keycloak. Проверяет PKCE: verifier должен соответствовать challenge."""

    def __init__(self) -> None:
        self.claims: dict = {}
        self.signing_key = IDP_KEY
        self.challenge: str | None = None
        self.nonce: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
                    "token_endpoint": f"{INTERNAL}/protocol/openid-connect/token",
                    "jwks_uri": f"{INTERNAL}/protocol/openid-connect/certs",
                },
            )
        if url.endswith("/certs"):
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(IDP_KEY.public_key()))
            return httpx.Response(200, json={"keys": [{**jwk, "kid": "k1", "alg": "RS256", "use": "sig"}]})
        if url.endswith("/token"):
            form = parse_qs(request.content.decode())
            verifier = form["code_verifier"][0]
            digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
            if form["code"] != ["good-code"] or digest.decode() != self.challenge:
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = int(time.time())
            claims = {
                "iss": ISSUER,
                "aud": "itscout",
                "sub": "user-1",
                "iat": now,
                "exp": now + 300,
                "nonce": self.nonce,
                **self.claims,
            }
            token = jwt.encode(claims, self.signing_key, algorithm="RS256", headers={"kid": "k1"})
            return httpx.Response(200, json={"id_token": token, "access_token": "x", "token_type": "Bearer"})
        return httpx.Response(404)


@pytest.fixture
def idp(monkeypatch) -> FakeIdp:
    fake = FakeIdp()
    monkeypatch.setattr(oidc, "http_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(
        get_settings(), "fsp_oidc_discovery_url", f"{INTERNAL}/.well-known/openid-configuration"
    )
    monkeypatch.setattr(get_settings(), "public_base_url", "https://itscout.test")

    async def registry(fsp_id: str):
        return REGISTRY.get(fsp_id)

    monkeypatch.setattr(fsp_service, "fetch_from_registry", registry)
    return fake


async def start(client, idp: FakeIdp, headers) -> str:
    """Старт флоу: cookie флоу остаётся в клиенте, возвращается state из адреса IdP."""
    response = await client.get(f"{API}/fsp/oidc/start", params={"consent": "true"}, headers=headers)
    assert response.status_code == 200, response.text
    url = urlparse(response.json()["authorization_url"])
    assert url.geturl().startswith(f"{ISSUER}/protocol/openid-connect/auth")
    query = {key: values[0] for key, values in parse_qs(url.query).items()}
    assert query["code_challenge_method"] == "S256"
    assert query["redirect_uri"] == "https://itscout.test/api/v1/fsp/oidc/callback"
    assert "code_verifier" not in query
    idp.challenge, idp.nonce = query["code_challenge"], query["nonce"]
    return query["state"]


async def callback(client, state: str, code: str = "good-code") -> dict[str, str]:
    response = await client.get(f"{API}/fsp/oidc/callback", params={"code": code, "state": state})
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert location.path == "/candidate/settings"
    return {key: values[0] for key, values in parse_qs(location.query).items()}


async def test_oidc_link_imports_achievements(client, session, idp):
    headers = await signup(client, "oidc@example.com")
    idp.claims = {"fsp_id": "FSP-2026-7781"}
    state = await start(client, idp, headers)

    assert await callback(client, state) == {"fsp_oidc": "linked"}

    profile = (await client.get(f"{API}/candidates/me/fsp", headers=headers)).json()
    assert profile["linked"] and profile["fsp_id"] == "FSP-2026-7781"
    assert profile["method"] == "oidc" and profile["ownership_verified"] is True
    assert len(profile["achievements"]) == 1 and profile["ranks"][0]["rank"] == "I"
    candidate = await session.scalar(select(Candidate).where(Candidate.fsp_id == "FSP-2026-7781"))
    assert candidate.fsp_link_method == FspLinkMethod.oidc
    consent = await session.scalar(
        select(Consent).where(Consent.user_id == candidate.user_id, Consent.kind == ConsentKind.fsp_import)
    )
    assert consent is not None

    # Cookie флоу одноразовая: повтор того же callback не проходит
    assert (await callback(client, state))["reason"] == "fsp_oidc_state_invalid"


async def test_start_requires_consent_and_candidate(client, idp):
    headers = await signup(client, "noconsent@example.com")
    response = await client.get(f"{API}/fsp/oidc/start", params={"consent": "false"}, headers=headers)
    assert response.status_code == 400 and response.json()["error"]["code"] == "consent_required"
    assert (await client.get(f"{API}/fsp/oidc/start", params={"consent": "true"})).status_code == 401


async def test_wrong_state_is_rejected(client, idp):
    headers = await signup(client, "state@example.com")
    idp.claims = {"fsp_id": "FSP-2026-7781"}
    await start(client, idp, headers)
    assert await callback(client, "forged-state") == {"fsp_oidc": "error", "reason": "fsp_oidc_state_invalid"}


async def test_expired_state_is_rejected(client, idp):
    headers = await signup(client, "expired@example.com")
    idp.claims = {"fsp_id": "FSP-2026-7781"}
    state = await start(client, idp, headers)
    settings = get_settings()
    flow = jwt.decode(
        client.cookies[settings.fsp_oidc_cookie_name], settings.jwt_secret, algorithms=["HS256"]
    )
    expired = jwt.encode({**flow, "exp": int(time.time()) - 5}, settings.jwt_secret, algorithm="HS256")
    for cookie in client.cookies.jar:
        if cookie.name == settings.fsp_oidc_cookie_name:
            cookie.value = expired
    assert (await callback(client, state))["reason"] == "fsp_oidc_state_invalid"


async def test_callback_without_flow_cookie_is_rejected(client, idp):
    client.cookies.clear()
    assert (await callback(client, "any"))["reason"] == "fsp_oidc_state_invalid"


@pytest.mark.parametrize(
    ("claims", "key"),
    [
        ({"fsp_id": "FSP-2026-7781", "aud": "someone-else"}, IDP_KEY),
        ({"fsp_id": "FSP-2026-7781", "iss": "https://evil.example/realms/fsp"}, IDP_KEY),
        ({"fsp_id": "FSP-2026-7781", "nonce": "replayed"}, IDP_KEY),
        ({"fsp_id": "FSP-2026-7781"}, FOREIGN_KEY),
    ],
    ids=["foreign-audience", "foreign-issuer", "wrong-nonce", "wrong-signature"],
)
async def test_invalid_id_token_is_rejected(client, session, idp, claims, key):
    headers = await signup(client, "token@example.com")
    state = await start(client, idp, headers)
    idp.claims, idp.signing_key = claims, key
    assert (await callback(client, state))["reason"] == "fsp_oidc_token_invalid"
    assert await session.scalar(select(Candidate.id).where(Candidate.fsp_id.is_not(None))) is None


async def test_rejected_code_and_denied_login(client, idp):
    headers = await signup(client, "code@example.com")
    idp.claims = {"fsp_id": "FSP-2026-7781"}
    state = await start(client, idp, headers)
    assert (await callback(client, state, code="stolen-code"))["reason"] == "fsp_oidc_code_rejected"

    state = await start(client, idp, headers)
    response = await client.get(f"{API}/fsp/oidc/callback", params={"error": "access_denied", "state": state})
    assert "reason=fsp_oidc_denied" in response.headers["location"]


async def test_token_without_fsp_id_is_rejected(client, idp):
    headers = await signup(client, "nofsp@example.com")
    state = await start(client, idp, headers)
    assert (await callback(client, state))["reason"] == "fsp_oidc_no_fsp_id"


async def test_fsp_id_of_another_candidate_cannot_be_linked(client, session, idp):
    owner = await signup(client, "owner@example.com")
    linked = await client.post(
        f"{API}/candidates/me/fsp/link", json={"fsp_id": "FSP-2026-1002", "consent": True}, headers=owner
    )
    assert linked.status_code == 200, linked.text

    other = await signup(client, "other@example.com")
    idp.claims = {"fsp_id": "FSP-2026-1002"}
    state = await start(client, idp, other)
    assert (await callback(client, state))["reason"] == "fsp_id_taken"
    other_profile = (await client.get(f"{API}/candidates/me/fsp", headers=other)).json()
    assert other_profile["linked"] is False


async def test_manual_link_upgrades_to_verified_ownership(client, idp):
    headers = await signup(client, "upgrade@example.com")
    manual = await client.post(
        f"{API}/candidates/me/fsp/link", json={"fsp_id": "FSP-2026-1002", "consent": True}, headers=headers
    )
    assert manual.json()["ownership_verified"] is False
    idp.claims = {"fsp_id": "FSP-2026-1002"}
    state = await start(client, idp, headers)
    assert await callback(client, state) == {"fsp_oidc": "linked"}
    profile = (await client.get(f"{API}/candidates/me/fsp", headers=headers)).json()
    assert profile["ownership_verified"] is True
