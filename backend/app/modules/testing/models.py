from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade, TemplateStatus
from app.core.types import enum_type


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    specialization: Mapped[str] = mapped_column(String(32))
    grade_target: Mapped[Grade] = mapped_column(enum_type(Grade))
    purpose: Mapped[AttemptPurpose] = mapped_column(enum_type(AttemptPurpose))
    blueprint: Mapped[dict] = mapped_column(JSONB)
    seed: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[AttemptStatus] = mapped_column(enum_type(AttemptStatus), default=AttemptStatus.in_progress)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    theta: Mapped[float | None] = mapped_column(Float)
    se: Mapped[float | None] = mapped_column(Float)
    result: Mapped[AttemptResult | None] = mapped_column(enum_type(AttemptResult))
    topic_scores: Mapped[dict | None] = mapped_column(JSONB)
    skill_scores: Mapped[dict | None] = mapped_column(JSONB)
    approach_score: Mapped[float | None] = mapped_column(Float)
    flags: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestAttemptItem(Base):
    __tablename__ = "test_attempt_items"
    # Одна позиция — одно задание: защита от двойной выдачи при параллельных запросах (§10.3)
    __table_args__ = (UniqueConstraint("attempt_id", "position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[str] = mapped_column(String(128), index=True)
    template_version: Mapped[int] = mapped_column(Integer, default=1)
    instance_seed: Mapped[int] = mapped_column(BigInteger)
    stage: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    scored: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    # Ключ ответа хранится только на сервере и никогда не отдаётся во фронт
    answer_key: Mapped[dict] = mapped_column(JSONB)
    response: Mapped[dict | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_ms: Mapped[int | None] = mapped_column(Integer)


class TemplateStat(Base):
    __tablename__ = "template_stats"

    template_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[TemplateStatus] = mapped_column(enum_type(TemplateStatus))
    irt_a: Mapped[float] = mapped_column(Float)
    irt_b: Mapped[float] = mapped_column(Float)
    irt_c: Mapped[float] = mapped_column(Float, default=0.0)
    exposures: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_calibrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
