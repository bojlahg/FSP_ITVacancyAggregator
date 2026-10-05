from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import DeclineReason, InvitationStatus, ReportReason, ReportStatus, UnlockSource
from app.core.types import enum_type


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (CheckConstraint("salary_from > 0 AND salary_from <= salary_to", name="salary_range"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    need_id: Mapped[int | None] = mapped_column(
        ForeignKey("hiring_needs.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    contact_method: Mapped[dict] = mapped_column(JSONB)
    match_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[InvitationStatus] = mapped_column(
        enum_type(InvitationStatus), default=InvitationStatus.sent
    )
    decline_reason: Mapped[DeclineReason | None] = mapped_column(enum_type(DeclineReason))
    decline_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContactUnlock(Base):
    """Единственный источник правды о раскрытии контактов кандидата работодателю."""

    __tablename__ = "contact_unlocks"

    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id", ondelete="CASCADE"), primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[UnlockSource] = mapped_column(enum_type(UnlockSource))
    source_id: Mapped[int] = mapped_column(BigInteger)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvitationReport(Base):
    """Жалоба кандидата на приглашение (§8.5): одна на приглашение, разбирает администратор."""

    __tablename__ = "invitation_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invitation_id: Mapped[int] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"), unique=True, index=True
    )
    reason: Mapped[ReportReason] = mapped_column(enum_type(ReportReason))
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(enum_type(ReportStatus), default=ReportStatus.open)
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
