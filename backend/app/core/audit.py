from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuditLog


def audit(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    object_type: str,
    object_id: int | None = None,
    meta: dict | None = None,
) -> None:
    """Журнал юридически значимых действий: согласия, раскрытие контактов (§13). Коммитит вызывающий."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            meta=meta,
        )
    )
