from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint

from app.core.db import Base
from app.core.enums import Grade
from app.core.types import enum_type


class ExpertPair(Base):
    """Пара «потребность — кандидат» для экспертной разметки (§12.2).

    Снимки потребности и обезличенной карточки хранятся целиком, без внешних ключей: разметка
    переживает пересоздание демо-данных (reseed не трогает эти таблицы).
    """

    __tablename__ = "expert_pairs"
    __table_args__ = (UniqueConstraint("need_id", "candidate_id", name="uq_expert_pairs_need_candidate"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    need_id: Mapped[int] = mapped_column(BigInteger)
    candidate_id: Mapped[int] = mapped_column(BigInteger)
    need_snapshot: Mapped[dict] = mapped_column(JSONB)
    candidate_snapshot: Mapped[dict] = mapped_column(JSONB)
    ours_rank: Mapped[int | None] = mapped_column(Integer)
    ours_score: Mapped[int | None] = mapped_column(Integer)
    keyword_rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExpertLabel(Base):
    __tablename__ = "expert_labels"
    __table_args__ = (
        UniqueConstraint("pair_id", "rater_email", name="uq_expert_labels_pair_rater"),
        CheckConstraint("label BETWEEN 0 AND 3", name="label_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pair_id: Mapped[int] = mapped_column(ForeignKey("expert_pairs.id", ondelete="CASCADE"))
    # Email, а не id пользователя: после reseed эксперт регистрируется заново и продолжает с тем же email
    rater_email: Mapped[str] = mapped_column(String(320))
    label: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AngoffRating(Base):
    """Оценка modified Angoff (§10.4): вероятность, что минимально компетентный кандидат грейда решит шаблон.

    Без внешних ключей и по email эксперта: оценки переживают reseed (PRESERVED_TABLES в seed/generate.py).
    """

    __tablename__ = "angoff_ratings"
    __table_args__ = (
        UniqueConstraint(
            "rater_email", "specialization", "grade", "template_id", name="uq_angoff_ratings_rater_item"
        ),
        CheckConstraint("rating BETWEEN 0 AND 1", name="rating_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rater_email: Mapped[str] = mapped_column(String(320))
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[Grade] = mapped_column(enum_type(Grade))
    template_id: Mapped[str] = mapped_column(String(120))
    rating: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
