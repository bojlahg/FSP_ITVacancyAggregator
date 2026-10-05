from fastapi import APIRouter, BackgroundTasks, Response, status

from app.core.deps import CurrentEmployerSession, DbSession
from app.core.errors import error_responses
from app.modules.integrations import service
from app.modules.integrations.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    WebhookDeliveryOut,
    WebhookOut,
    WebhookUpdate,
)

# Управление ключами и webhook — только из кабинета (вход по паролю), не по API-ключу
router = APIRouter(prefix="/employers/me", tags=["employer: integrations"])

AUTH = error_responses(401, 403)
OWNED = error_responses(401, 403, 404)


@router.get("/api-keys", response_model=list[ApiKeyOut], summary="Активные API-ключи ATS", responses=AUTH)
async def list_api_keys(user: CurrentEmployerSession, db: DbSession) -> list[ApiKeyOut]:
    return await service.list_keys(db, user.id)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Выпустить API-ключ (ключ показывается один раз)",
    responses=error_responses(401, 403, 409, 422),
)
async def create_api_key(body: ApiKeyCreate, user: CurrentEmployerSession, db: DbSession) -> ApiKeyCreated:
    return await service.create_key(db, user.id, body)


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Отозвать API-ключ",
    responses=OWNED,
)
async def revoke_api_key(key_id: int, user: CurrentEmployerSession, db: DbSession) -> Response:
    await service.revoke_key(db, user.id, key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/webhook",
    response_model=WebhookOut | None,
    summary="Настройки webhook (null — не настроен)",
    responses=AUTH,
)
async def get_webhook(user: CurrentEmployerSession, db: DbSession) -> WebhookOut | None:
    return await service.get_webhook(db, user.id)


@router.put(
    "/webhook",
    response_model=WebhookOut,
    summary="Задать адрес webhook (секрет подписи создаётся при первом сохранении)",
    responses=error_responses(401, 403, 422),
)
async def put_webhook(body: WebhookUpdate, user: CurrentEmployerSession, db: DbSession) -> WebhookOut:
    return await service.put_webhook(db, user.id, body)


@router.delete(
    "/webhook",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить webhook",
    responses=OWNED,
)
async def delete_webhook(user: CurrentEmployerSession, db: DbSession) -> Response:
    await service.delete_webhook(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/webhook/rotate-secret",
    response_model=WebhookOut,
    summary="Выпустить новый секрет подписи",
    responses=OWNED,
)
async def rotate_webhook_secret(user: CurrentEmployerSession, db: DbSession) -> WebhookOut:
    return await service.rotate_secret(db, user.id)


@router.post(
    "/webhook/test",
    response_model=WebhookDeliveryOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Отправить тестовое событие ping",
    responses=error_responses(401, 403, 404, 429),
)
async def test_webhook(
    user: CurrentEmployerSession, db: DbSession, background: BackgroundTasks
) -> WebhookDeliveryOut:
    delivery = await service.send_test(db, user.id)
    background.add_task(service.deliver_pending)
    return delivery


@router.get(
    "/webhook/deliveries",
    response_model=list[WebhookDeliveryOut],
    summary="Последние доставки событий",
    responses=AUTH,
)
async def list_webhook_deliveries(user: CurrentEmployerSession, db: DbSession) -> list[WebhookDeliveryOut]:
    return await service.list_deliveries(db, user.id)


@router.post(
    "/webhook/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Повторить недоставленное событие",
    responses=error_responses(401, 403, 404, 409, 429),
)
async def retry_webhook_delivery(
    delivery_id: int, user: CurrentEmployerSession, db: DbSession, background: BackgroundTasks
) -> WebhookDeliveryOut:
    delivery = await service.retry_delivery(db, user.id, delivery_id)
    background.add_task(service.deliver_pending)
    return delivery
