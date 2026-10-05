import asyncio
import sys
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

if sys.platform == "win32":
    # psycopg async не работает с ProactorEventLoop — только локальная разработка на Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.db import SessionFactory, engine  # noqa: E402
from app.core.enums import Role  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session")
async def db_schema() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def db(db_schema) -> AsyncIterator[None]:
    """Чистая БД для теста: таблицы очищаются после него."""
    yield
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session(db) -> AsyncIterator:
    async with SessionFactory() as db_session:
        yield db_session


@pytest.fixture
async def client(db_schema) -> AsyncIterator[AsyncClient]:
    # Счётчики лимита частоты общие (в БД): каждый тест начинает с нуля
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM rate_limit_hits"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


def bearer(role: Role, user_id: int = 1) -> dict[str, str]:
    token, _ = create_access_token(user_id, role.value)
    return {"Authorization": f"Bearer {token}"}
