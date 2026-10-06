from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import ChallengeAttemptStatus, ChallengeStatus, Grade
from app.core.types import enum_type


class Challenge(Base):
    """Челлендж компании (§11.1): вопросы пишет работодатель, ключи хранятся здесь и наружу не уходят."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade | None] = mapped_column(enum_type(Grade))
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    time_per_question_sec: Mapped[int] = mapped_column(Integer)
    questions_per_attempt: Mapped[int | None] = mapped_column(Integer)
    # [{id, kind, text, code, options: [{id, text}], key: {choice_ids | number, tolerance}, rubric: [...]}]
    questions: Mapped[list] = mapped_column(JSONB)
    status: Mapped[ChallengeStatus] = mapped_column(enum_type(ChallengeStatus), default=ChallengeStatus.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChallengeAttempt(Base):
    """Одна попытка кандидата на челлендж: порядок вопросов, перемешанные варианты и ответы."""

    __tablename__ = "challenge_attempts"
    __table_args__ = (UniqueConstraint("challenge_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    status: Mapped[ChallengeAttemptStatus] = mapped_column(
        enum_type(ChallengeAttemptStatus), default=ChallengeAttemptStatus.in_progress
    )
    # [{question_id, option_map: {показанный id: исходный id}, shown_at, answered_at, response, score, late}]
    items: Mapped[list] = mapped_column(JSONB)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    scored_total: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
