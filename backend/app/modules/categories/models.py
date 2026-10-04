from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Grade
from app.core.types import enum_type


class CandidateCategory(Base):
    __tablename__ = "candidate_categories"
    __table_args__ = (
        # У кандидата не больше одной действующей категории
        Index(
            "uq_candidate_categories_current",
            "candidate_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade] = mapped_column(enum_type(Grade))
    theta: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float | None] = mapped_column(Float)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("test_attempts.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
