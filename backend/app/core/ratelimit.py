import time
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import DateTime, Integer, String, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base
from app.core.deps import DbSession
from app.core.errors import AppError

# Счётчики старше этого срока удаляются при открытии нового окна
RETENTION = timedelta(days=1)


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
    message = "Слишком много запросов, попробуйте позже"


class RateLimitHit(Base):
    """Счётчик запросов по ключу (IP и путь) в окне: общий для всех процессов backend."""

    __tablename__ = "rate_limit_hits"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)


async def hit(db, key: str, limit: int, window_seconds: int) -> bool:
    """Скользящее окно по двум фиксированным: текущее + доля предыдущего, пропорциональная остатку."""
    now = time.time()
    start = now - now % window_seconds
    current_start = datetime.fromtimestamp(start, UTC)
    previous_start = datetime.fromtimestamp(start - window_seconds, UTC)
    current = await db.scalar(
        insert(RateLimitHit)
        .values(key=key, window_start=current_start, hits=1)
        .on_conflict_do_update(
            index_elements=[RateLimitHit.key, RateLimitHit.window_start],
            set_={"hits": RateLimitHit.hits + 1},
        )
        .returning(RateLimitHit.hits)
    )
    previous = await db.scalar(
        select(RateLimitHit.hits).where(RateLimitHit.key == key, RateLimitHit.window_start == previous_start)
    )
    if current == 1:
        await db.execute(delete(RateLimitHit).where(RateLimitHit.window_start < current_start - RETENTION))
    await db.commit()
    weight = 1 - (now - start) / window_seconds
    # Сам запрос уже посчитан в current, поэтому сравниваем строго больше лимита
    return current + (previous or 0) * weight <= limit


async def limit_auth_requests(request: Request, db: DbSession) -> None:
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    demo = request.url.path.endswith("/demo-login")
    limit = settings.demo_login_rate_limit if demo else settings.auth_rate_limit
    if not await hit(db, key, limit, settings.auth_rate_window_seconds):
        raise TooManyRequestsError()


async def limit_login_email(db: AsyncSession, email: str) -> None:
    settings = get_settings()
    key = f"login-email:{email.strip().lower()}"
    if not await hit(db, key, settings.login_email_rate_limit, settings.auth_rate_window_seconds):
        raise TooManyRequestsError()
