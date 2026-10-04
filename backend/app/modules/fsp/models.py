from datetime import date

from sqlalchemy import BigInteger, Date, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import CompetencyStatus
from app.core.types import enum_type


class FspAchievement(Base):
    __tablename__ = "fsp_achievements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    competition_id: Mapped[str] = mapped_column(String(64))
    competition_name: Mapped[str] = mapped_column(String(300))
    discipline: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(32))
    format: Mapped[str] = mapped_column(String(16))
    held_on: Mapped[date] = mapped_column(Date)
    place: Mapped[int] = mapped_column(Integer)
    participants: Mapped[int] = mapped_column(Integer)
    team_role: Mapped[str | None] = mapped_column(String(32))
    prize: Mapped[str | None] = mapped_column(String(16))
    percentile: Mapped[float] = mapped_column(Float)
    strength: Mapped[float] = mapped_column(Float)


class FspRank(Base):
    __tablename__ = "fsp_ranks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    discipline: Mapped[str] = mapped_column(String(32))
    rank: Mapped[str] = mapped_column(String(8))
    awarded_at: Mapped[date] = mapped_column(Date)


class CandidateCompetency(Base):
    __tablename__ = "candidate_competencies"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    competency_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[CompetencyStatus] = mapped_column(enum_type(CompetencyStatus))
    evidence: Mapped[list | None] = mapped_column(JSONB)
