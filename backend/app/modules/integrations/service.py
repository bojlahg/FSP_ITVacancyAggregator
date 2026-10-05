"""Интеграция с ATS (docs/anti-fraud-ats.md §2): API-ключи работодателя и подписанные webhook'и.

Событие пишется в `webhook_deliveries` в той же транзакции, что и действие (outbox), и отправляется
после коммита: сразу фоновой задачей запроса и повторно — фоновым циклом с задержками из настроек.
Данные события — те же, что работодатель видит в API: контакты только после записи в contact_unlocks.
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ratelimit
from app.core.audit import audit
from app.core.config import Settings, get_settings
from app.core.db import SessionFactory
from app.core.enums import WebhookDeliveryStatus
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.integrations.models import EmployerApiKey, EmployerWebhook, WebhookDelivery
from app.modules.integrations.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    WebhookDeliveryOut,
    WebhookOut,
    WebhookUpdate,
)

log = logging.getLogger(__name__)

KEY_PREFIX = "itsk"
USER_AGENT = "ITScout-Webhooks/1.0"
DELIVERIES_SHOWN = 30
ERROR_TEXT_LIMIT = 300


class InvalidWebhookUrlError(AppError):
    status_code = 422
    code = "invalid_webhook_url"
    message = "Адрес webhook должен быть публичным HTTPS-адресом"


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# --- API-ключи -------------------------------------------------------------------------------


async def list_keys(db: AsyncSession, user_id: int) -> list[ApiKeyOut]:
    employer = await employers_service.get_by_user(db, user_id)
    query = (
        select(EmployerApiKey)
        .where(EmployerApiKey.employer_id == employer.id, EmployerApiKey.revoked_at.is_(None))
        .order_by(EmployerApiKey.id)
    )
    return [ApiKeyOut.model_validate(key) for key in await db.scalars(query)]


async def _not_demo(db: AsyncSession, user_id: int) -> None:
    """Общий демо-аккаунт открыт любому посетителю: ключ или webhook на нём перехватывали бы чужие отклики."""
    from app.modules.auth import service as auth_service

    user = await auth_service.get_user(db, user_id)
    if user.email.lower() == get_settings().demo_employer_email.lower():
        raise ForbiddenError(
            "В общем демо-аккаунте интеграция с ATS недоступна — зарегистрируйте свою компанию",
            code="demo_account",
        )


async def create_key(db: AsyncSession, user_id: int, body: ApiKeyCreate) -> ApiKeyCreated:
    await _not_demo(db, user_id)
    employer = await employers_service.get_by_user(db, user_id)
    active = await db.scalar(
        select(func.count())
        .select_from(EmployerApiKey)
        .where(EmployerApiKey.employer_id == employer.id, EmployerApiKey.revoked_at.is_(None))
    )
    limit = get_settings().api_keys_per_employer
    if (active or 0) >= limit:
        raise ConflictError(
            f"Не больше {limit} активных ключей — отзовите неиспользуемый", code="api_key_limit"
        )
    prefix = secrets.token_hex(4)
    key = f"{KEY_PREFIX}_{prefix}_{secrets.token_urlsafe(24)}"
    item = EmployerApiKey(employer_id=employer.id, name=body.name.strip(), prefix=prefix, key_hash=_hash(key))
    db.add(item)
    await db.flush()
    audit(db, actor_user_id=user_id, action="api_key.created", object_type="api_key", object_id=item.id)
    await db.commit()
    await db.refresh(item)
    return ApiKeyCreated(**ApiKeyOut.model_validate(item).model_dump(), key=key)


async def revoke_key(db: AsyncSession, user_id: int, key_id: int) -> None:
    employer = await employers_service.get_by_user(db, user_id)
    item = await db.get(EmployerApiKey, key_id)
    if item is None or item.employer_id != employer.id or item.revoked_at is not None:
        raise NotFoundError("Ключ не найден")
    item.revoked_at = _now()
    audit(db, actor_user_id=user_id, action="api_key.revoked", object_type="api_key", object_id=item.id)
    await db.commit()


async def authenticate_key(db: AsyncSession, key: str) -> int:
    """Ключ из заголовка X-API-Key → id пользователя-работодателя или 401."""
    parts = key.strip().split("_", 2)
    if len(parts) != 3 or parts[0] != KEY_PREFIX:
        raise UnauthorizedError("API-ключ недействителен или отозван")
    item = await db.scalar(
        select(EmployerApiKey).where(EmployerApiKey.prefix == parts[1], EmployerApiKey.revoked_at.is_(None))
    )
    if item is None or not hmac.compare_digest(item.key_hash, _hash(key.strip())):
        raise UnauthorizedError("API-ключ недействителен или отозван")
    employer = await db.get(Employer, item.employer_id)
    if employer is None:
        raise UnauthorizedError("API-ключ недействителен или отозван")
    now = _now()
    if item.last_used_at is None or now - item.last_used_at > timedelta(
        seconds=get_settings().api_key_touch_seconds
    ):
        item.last_used_at = now
        await db.commit()
    return employer.user_id


# --- Webhook ---------------------------------------------------------------------------------


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


async def check_url(url: str) -> None:
    """Защита от SSRF: только https и только публичные адреса (в dev можно разрешить локальные)."""
    settings = get_settings()
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        raise InvalidWebhookUrlError()
    if settings.webhook_allow_private_hosts:
        return
    if parts.scheme != "https":
        raise InvalidWebhookUrlError()
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or 443, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise InvalidWebhookUrlError("Не удалось найти адрес webhook в DNS") from exc
    if not infos or not all(_is_public_address(info[4][0]) for info in infos):
        raise InvalidWebhookUrlError()


async def get_webhook(db: AsyncSession, user_id: int) -> WebhookOut | None:
    employer = await employers_service.get_by_user(db, user_id)
    hook = await db.get(EmployerWebhook, employer.id)
    return WebhookOut.model_validate(hook) if hook else None


async def put_webhook(db: AsyncSession, user_id: int, body: WebhookUpdate) -> WebhookOut:
    await _not_demo(db, user_id)
    employer = await employers_service.get_by_user(db, user_id)
    url = body.url.strip()
    await check_url(url)
    hook = await db.get(EmployerWebhook, employer.id)
    if hook is None:
        hook = EmployerWebhook(employer_id=employer.id, secret=secrets.token_hex(32))
        db.add(hook)
    hook.url = url
    hook.enabled = body.enabled
    audit(db, actor_user_id=user_id, action="webhook.updated", object_type="employer", object_id=employer.id)
    await db.commit()
    await db.refresh(hook)
    return WebhookOut.model_validate(hook)


async def _own_webhook(db: AsyncSession, user_id: int) -> EmployerWebhook:
    employer = await employers_service.get_by_user(db, user_id)
    hook = await db.get(EmployerWebhook, employer.id)
    if hook is None:
        raise NotFoundError("Webhook не настроен", code="webhook_not_configured")
    return hook


async def rotate_secret(db: AsyncSession, user_id: int) -> WebhookOut:
    hook = await _own_webhook(db, user_id)
    hook.secret = secrets.token_hex(32)
    await db.commit()
    await db.refresh(hook)
    return WebhookOut.model_validate(hook)


async def delete_webhook(db: AsyncSession, user_id: int) -> None:
    hook = await _own_webhook(db, user_id)
    await db.delete(hook)
    await db.commit()


async def enqueue(db: AsyncSession, employer_id: int, event: str, data: dict) -> None:
    """Событие в outbox, если у работодателя включён webhook. Коммитит вызывающий."""
    hook = await db.get(EmployerWebhook, employer_id)
    if hook is None or not hook.enabled:
        return
    db.add(WebhookDelivery(employer_id=employer_id, event=event, payload=data))


async def send_test(db: AsyncSession, user_id: int) -> WebhookDeliveryOut:
    hook = await _own_webhook(db, user_id)
    await _limit_manual(db, hook.employer_id)
    delivery = WebhookDelivery(
        employer_id=hook.employer_id, event="ping", payload={"message": "Проверка webhook ITScout"}
    )
    db.add(delivery)
    await db.commit()
    await db.refresh(delivery)
    return WebhookDeliveryOut.model_validate(delivery)


async def list_deliveries(db: AsyncSession, user_id: int) -> list[WebhookDeliveryOut]:
    employer = await employers_service.get_by_user(db, user_id)
    query = (
        select(WebhookDelivery)
        .where(WebhookDelivery.employer_id == employer.id)
        .order_by(WebhookDelivery.id.desc())
        .limit(DELIVERIES_SHOWN)
    )
    return [WebhookDeliveryOut.model_validate(item) for item in await db.scalars(query)]


async def retry_delivery(db: AsyncSession, user_id: int, delivery_id: int) -> WebhookDeliveryOut:
    employer = await employers_service.get_by_user(db, user_id)
    item = await db.get(WebhookDelivery, delivery_id)
    if item is None or item.employer_id != employer.id:
        raise NotFoundError("Доставка не найдена")
    if item.status == WebhookDeliveryStatus.delivered:
        raise ConflictError("Событие уже доставлено", code="already_delivered")
    await _limit_manual(db, employer.id)
    item.status = WebhookDeliveryStatus.pending
    item.next_attempt_at = _now()
    await db.commit()
    await db.refresh(item)
    return WebhookDeliveryOut.model_validate(item)


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """Подпись как у Stripe: HMAC-SHA256 от «timestamp.body» — защищает и от подмены, и от повтора."""
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


async def post_webhook(url: str, headers: dict[str, str], body: bytes) -> int:
    """Транспорт отдельно, чтобы тесты подменяли его без сети. Редиректы не выполняются (SSRF).

    Общий тайм-аут на весь вызов (httpx считает тайм-аут на каждое чтение), тело ответа не читается:
    медленный приёмник не может держать доставку бесконечно.
    """
    timeout = get_settings().webhook_timeout_seconds

    async def call() -> int:
        async with (
            httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client,
            client.stream("POST", url, headers=headers, content=body) as response,
        ):
            return response.status_code

    return await asyncio.wait_for(call(), timeout)


async def _send(hook: EmployerWebhook, delivery: WebhookDelivery) -> tuple[int | None, str | None]:
    envelope = {
        "id": delivery.id,
        "event": delivery.event,
        "created_at": delivery.created_at.isoformat(),
        "data": delivery.payload,
    }
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": USER_AGENT,
        "X-ITScout-Event": delivery.event,
        "X-ITScout-Delivery": str(delivery.id),
        "X-ITScout-Signature": sign(hook.secret, int(time.time()), body),
    }
    try:
        await check_url(hook.url)
        status = await post_webhook(hook.url, headers, body)
    except Exception as exc:  # сетевые ошибки и отказ проверки адреса — повод для повтора
        return None, (str(exc) or exc.__class__.__name__)[:ERROR_TEXT_LIMIT]
    return status, None if 200 <= status < 300 else f"HTTP {status}"


# Одна пачка доставок на процесс за раз: фоновые задачи запросов не копятся и не занимают пул БД
_delivery_lock = asyncio.Lock()


async def _claim(settings: Settings) -> list[int]:
    """Аренда пачки короткой транзакцией: строки уходят из выборки на время отправки, без блокировки."""
    async with SessionFactory() as db:
        await db.execute(
            delete(WebhookDelivery).where(
                WebhookDelivery.status != WebhookDeliveryStatus.pending,
                WebhookDelivery.created_at < _now() - timedelta(days=settings.webhook_retention_days),
            )
        )
        query = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == WebhookDeliveryStatus.pending,
                WebhookDelivery.next_attempt_at <= func.now(),
            )
            .order_by(WebhookDelivery.id)
            .limit(settings.webhook_batch_size)
            .with_for_update(skip_locked=True)
        )
        items = list(await db.scalars(query))
        lease_until = _now() + timedelta(seconds=settings.webhook_lease_seconds)
        for item in items:
            item.next_attempt_at = lease_until
        await db.commit()
        return [item.id for item in items]


async def _deliver_one(delivery_id: int, delays: list[int]) -> None:
    async with SessionFactory() as db:
        item = await db.get(WebhookDelivery, delivery_id)
        hook = await db.get(EmployerWebhook, item.employer_id) if item else None
    if item is None:
        return
    # Сетевой вызов — вне транзакции и без открытой сессии
    if hook is None or not hook.enabled:
        status, error = None, "Webhook отключён"
    else:
        status, error = await _send(hook, item)
    async with SessionFactory() as db:
        item = await db.get(WebhookDelivery, delivery_id)
        if item is None:
            return
        if hook is None or not hook.enabled:
            item.status = WebhookDeliveryStatus.failed
            item.last_error = error
        else:
            item.attempts += 1
            item.response_status = status
            item.last_error = error
            if error is None:
                item.status = WebhookDeliveryStatus.delivered
                item.delivered_at = _now()
            elif item.attempts > len(delays):
                item.status = WebhookDeliveryStatus.failed
            else:
                item.next_attempt_at = _now() + timedelta(seconds=delays[item.attempts - 1])
        await db.commit()


async def deliver_pending() -> int:
    """Отправить созревшие события. Аренда строк (SKIP LOCKED) исключает двойную отправку между процессами."""
    if _delivery_lock.locked():
        return 0
    async with _delivery_lock:
        settings = get_settings()
        ids = await _claim(settings)
        for delivery_id in ids:
            await _deliver_one(delivery_id, settings.webhook_retry_delays_seconds)
        return len(ids)


async def forget_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Удаление аккаунта (152-ФЗ): события с данными кандидата не должны пережить его. Коммитит вызывающий."""
    candidate = WebhookDelivery.payload["candidate"]["id"].as_integer()
    await db.execute(delete(WebhookDelivery).where(candidate == candidate_id))


async def _limit_manual(db: AsyncSession, employer_id: int) -> None:
    settings = get_settings()
    if not await ratelimit.hit(db, f"webhook-manual:{employer_id}", settings.webhook_manual_per_hour, 3600):
        raise ratelimit.TooManyRequestsError("Слишком много ручных отправок, попробуйте позже")


async def delivery_loop() -> None:
    """Повторы по расписанию: запускается при старте приложения (не в тестах)."""
    interval = get_settings().webhook_worker_interval_seconds
    while True:
        try:
            await deliver_pending()
        except Exception:
            log.warning("webhook delivery loop failed", exc_info=True)
        await asyncio.sleep(interval)
