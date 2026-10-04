from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import ApplicationStatus
from app.core.types import enum_type


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("need_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    cover_note: Mapped[str | None] = mapped_column(Text)
    match_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[ApplicationStatus] = mapped_column(
        enum_type(ApplicationStatus), default=ApplicationStatus.sent
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
