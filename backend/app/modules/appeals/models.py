from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import AppealStatus, Grade
from app.core.types import enum_type


class GradeAppeal(Base):
    """Возражение кандидата против категории (152-ФЗ ст. 16): рассматривает человек, грейд само не меняет."""

    __tablename__ = "grade_appeals"
    __table_args__ = (
        # Не больше одного открытого обращения на категорию
        Index("uq_grade_appeals_open", "category_id", unique=True, postgresql_where=text("status = 'open'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("candidate_categories.id", ondelete="CASCADE"))
    # Снимок категории на момент обращения: админ видит, что именно оспаривалось
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade] = mapped_column(enum_type(Grade))
    theta: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(Text)
    status: Mapped[AppealStatus] = mapped_column(enum_type(AppealStatus), default=AppealStatus.open)
    reply: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
