from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.enums import Role
from app.core.security import create_access_token
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


def bearer(role: Role, user_id: int = 1) -> dict[str, str]:
    token, _ = create_access_token(user_id, role.value)
    return {"Authorization": f"Bearer {token}"}
