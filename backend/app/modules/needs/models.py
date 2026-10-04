from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Grade, NeedStatus, WorkFormat
from app.core.types import enum_type


class HiringNeed(Base):
    """Потребность работодателя; с published=true она же — публичная вакансия (§8.7)."""

    __tablename__ = "hiring_needs"
    __table_args__ = (CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("hiring_needs.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSONB)
    specialization: Mapped[str] = mapped_column(String(32), index=True)
    grade: Mapped[Grade] = mapped_column(enum_type(Grade))
    required_skills: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    optional_skills: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    industry: Mapped[str | None] = mapped_column(String(32))
    team_description: Mapped[str | None] = mapped_column(Text)
    work_format: Mapped[WorkFormat | None] = mapped_column(enum_type(WorkFormat))
    city: Mapped[str | None] = mapped_column(String(100))
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[NeedStatus] = mapped_column(enum_type(NeedStatus), default=NeedStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NeedShortlist(Base):
    __tablename__ = "need_shortlist"

    need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id", ondelete="CASCADE"), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)
