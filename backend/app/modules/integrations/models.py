from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.core.enums import WebhookDeliveryStatus
from app.core.types import enum_type


class EmployerApiKey(Base):
    """Ключ ATS: хранится только SHA-256, сам ключ показывается один раз при выпуске."""

    __tablename__ = "employer_api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16), unique=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmployerWebhook(TimestampMixin, Base):
    __tablename__ = "employer_webhooks"

    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    # Секрет подписи HMAC нужен в открытом виде, чтобы подписывать; виден только владельцу
    secret: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WebhookDelivery(Base):
    """Исходящее событие (outbox): пишется в одной транзакции с действием, отправляется после коммита."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        enum_type(WebhookDeliveryStatus), default=WebhookDeliveryStatus.pending, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
