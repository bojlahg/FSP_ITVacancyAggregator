"""Отладочный раздел (DEBUG_TOOLS=true): сброс ограничений и результатов теста, проверка почты, reseed.

Для команды на время тестов. Без флага эндпоинты отвечают 404, раздела в интерфейсе нет.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.errors import ConflictError
from app.core.mail import get_email_sender, is_skipped_address
from app.core.mail_templates import debug_test
from app.core.schemas import MessageResponse
from app.modules.admin import service as admin_service
from app.modules.auth import service as auth_service
from app.modules.candidates import service as candidates_service
from app.modules.categories import service as categories_service
from app.modules.debug.schemas import DebugStatus
from app.modules.matching import service as matching_service

ACTIONS = {
    Role.candidate: ["reset_cooldowns", "reset_test", "test_email"],
    Role.employer: ["test_email"],
    Role.expert: ["test_email"],
    Role.admin: ["test_email", "reseed"],
}


def status(role: Role) -> DebugStatus:
    return DebugStatus(enabled=True, actions=ACTIONS.get(role, []))


async def reset_cooldowns(db: AsyncSession, user_id: int) -> MessageResponse:
    candidate = await candidates_service.get_by_user(db, user_id)
    await categories_service.reset_rules(db, candidate)
    return MessageResponse(message="Ограничения на пересдачу сброшены")


async def reset_test(db: AsyncSession, user_id: int) -> MessageResponse:
    candidate = await candidates_service.get_by_user(db, user_id)
    await categories_service.forget_results(db, candidate)
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    return MessageResponse(message="Результаты теста и категория удалены — можно пройти тест заново")


async def test_email(db: AsyncSession, user_id: int) -> MessageResponse:
    email = (await auth_service.get_user(db, user_id)).email
    if is_skipped_address(email):
        raise ConflictError(
            "На этот адрес письма не отправляются (служебный домен) — укажите свою почту в аккаунте команды",
            code="address_skipped",
        )
    await get_email_sender().send(debug_test(email))
    return MessageResponse(message=f"Письмо отправлено на {email}")


async def reseed() -> MessageResponse:
    return await admin_service.reseed()
