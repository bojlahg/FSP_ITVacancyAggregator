from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import AssignmentStatus, Grade, GradedBy, TaskKind
from app.core.types import enum_type


class EmployerTask(Base):
    """Короткое задание работодателя (§11): шаблон банка с автопроверкой или вопрос о подходе."""

    __tablename__ = "employer_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    need_id: Mapped[int | None] = mapped_column(ForeignKey("hiring_needs.id", ondelete="SET NULL"))
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade | None] = mapped_column(enum_type(Grade))
    kind: Mapped[TaskKind] = mapped_column(enum_type(TaskKind))
    template_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskAssignment(Base):
    """Задание, предложенное кандидату; payload — экземпляр без ключа, answer_key не уходит на фронт."""

    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("employer_tasks.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AssignmentStatus] = mapped_column(
        enum_type(AssignmentStatus), default=AssignmentStatus.offered
    )
    payload: Mapped[dict | None] = mapped_column(JSONB)
    answer_key: Mapped[dict | None] = mapped_column(JSONB)
    response: Mapped[dict | None] = mapped_column(JSONB)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rubric_hits: Mapped[list | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    graded_by: Mapped[GradedBy | None] = mapped_column(enum_type(GradedBy))
    employer_rating: Mapped[int | None] = mapped_column(Integer)
