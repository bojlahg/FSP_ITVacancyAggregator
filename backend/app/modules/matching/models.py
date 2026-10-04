from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Grade
from app.core.types import enum_type


class CandidateSearchIndex(Base):
    """Денормализованная строка кандидата для быстрой выдачи (§14). Пересчитывается при изменениях профиля."""

    __tablename__ = "candidate_search_index"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    visible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade: Mapped[Grade] = mapped_column(enum_type(Grade), index=True)
    theta: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float | None] = mapped_column(Float)
    vps: Mapped[float] = mapped_column(Float)
    fsp_score: Mapped[float] = mapped_column(Float, default=0.0)
    fresh: Mapped[float] = mapped_column(Float, default=0.0)
    approach: Mapped[float | None] = mapped_column(Float)
    skills_status: Mapped[dict] = mapped_column(JSONB, default=dict)
    topic_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    city: Mapped[str | None] = mapped_column(String(100))
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    has_fsp: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    max_rank: Mapped[str | None] = mapped_column(String(8))
    hidden_employer_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
