import pytest
from pydantic import ValidationError

from app.core.enums import Role
from app.main import app
from app.modules.invitations.schemas import ContactMethod, InvitationCreate
from tests.conftest import bearer

API = "/api/v1"


async def test_health_responds(client):
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


async def test_protected_endpoint_without_token_returns_unified_401(client):
    response = await client.get(f"{API}/candidates/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_candidate_cannot_call_employer_endpoint(client):
    response = await client.get(f"{API}/talent/categories", headers=bearer(Role.candidate))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_employer_cannot_read_candidate_invitations(client):
    response = await client.get(f"{API}/candidates/me/invitations", headers=bearer(Role.employer))
    assert response.status_code == 403


async def test_invalid_token_rejected(client):
    response = await client.get(f"{API}/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


async def test_validation_error_uses_unified_format(client):
    response = await client.post(f"{API}/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]


def test_every_operation_is_documented():
    spec = app.openapi()
    operations = [
        (method, path, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
    ]
    assert len(operations) >= 78
    for method, path, operation in operations:
        assert operation.get("summary"), f"{method.upper()} {path}: нет summary"
        assert operation.get("tags"), f"{method.upper()} {path}: нет тега"
        success = [code for code in operation["responses"] if code.startswith("2") or code == "302"]
        assert success, f"{method.upper()} {path}: нет успешного ответа"


def test_salary_range_must_be_ordered():
    contact = ContactMethod(name="HR", telegram="@hr")
    with pytest.raises(ValidationError):
        InvitationCreate(
            candidate_id=1,
            title="t",
            message="m",
            salary_from=300_000,
            salary_to=200_000,
            contact_method=contact,
        )
    with pytest.raises(ValidationError):
        InvitationCreate(
            candidate_id=1, title="t", message="m", salary_from=0, salary_to=200_000, contact_method=contact
        )


def test_contact_method_requires_a_channel():
    with pytest.raises(ValidationError):
        ContactMethod(name="HR")
