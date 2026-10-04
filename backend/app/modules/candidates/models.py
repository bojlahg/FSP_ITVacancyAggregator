from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.core.enums import FspLinkMethod, SearchStatus, SkillSource
from app.core.types import enum_type


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    city: Mapped[str | None] = mapped_column(String(100))
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    work_formats: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1))
    specialization: Mapped[str | None] = mapped_column(String(32), index=True)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    industries_exp: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    industries_pref: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    soft_skills: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    about: Mapped[str | None] = mapped_column(Text)
    search_status: Mapped[SearchStatus] = mapped_column(enum_type(SearchStatus), default=SearchStatus.open)
    privacy: Mapped[dict] = mapped_column(JSONB, default=dict)
    hidden_employer_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)
    fsp_id: Mapped[str | None] = mapped_column(String(64), index=True)
    fsp_link_method: Mapped[FspLinkMethod | None] = mapped_column(enum_type(FspLinkMethod))
    fsp_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # DEMO_MODE: попытки до этой отметки не учитываются в ограничениях смены грейда
    grade_rules_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateExperience(Base):
    __tablename__ = "candidate_experience"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(200))
    started_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[SkillSource] = mapped_column(enum_type(SkillSource), primary_key=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
