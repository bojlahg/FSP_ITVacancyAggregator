from datetime import datetime

from pydantic import Field

from app.core.enums import WebhookDeliveryStatus
from app.core.schemas import ApiModel

WEBHOOK_EVENTS = ["invitation.accepted", "invitation.declined", "application.created"]


class ApiKeyCreate(ApiModel):
    name: str = Field(min_length=1, max_length=100, description="Где используется ключ, например «Huntflow»")


class ApiKeyOut(ApiModel):
    id: int
    name: str
    prefix: str = Field(description="Начало ключа — чтобы узнать его в списке")
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="Ключ целиком — показывается один раз, передаётся в заголовке X-API-Key")


class WebhookUpdate(ApiModel):
    url: str = Field(min_length=8, max_length=500, description="HTTPS-адрес приёма событий в ATS")
    enabled: bool = True


class WebhookOut(ApiModel):
    url: str
    enabled: bool
    secret: str = Field(description="Секрет подписи HMAC-SHA256 (заголовок X-ITScout-Signature)")
    events: list[str] = Field(default_factory=lambda: list(WEBHOOK_EVENTS))
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryOut(ApiModel):
    id: int
    event: str
    status: WebhookDeliveryStatus
    attempts: int
    response_status: int | None
    last_error: str | None
    created_at: datetime
    next_attempt_at: datetime | None
    delivered_at: datetime | None
