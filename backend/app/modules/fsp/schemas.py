from datetime import date, datetime

from pydantic import Field

from app.core.enums import CompetencyStatus, FspLinkMethod
from app.core.schemas import ApiModel


class FspLinkRequest(ApiModel):
    fsp_id: str = Field(min_length=1, max_length=64)
    consent: bool = Field(description="Согласие на импорт данных из реестра ФСП")


class FspAchievementOut(ApiModel):
    competition_name: str
    discipline: str
    level: str = Field(description="international | national | interregional | regional | municipal")
    format: str = Field(description="individual | team")
    held_on: date
    place: int
    participants: int
    percentile: float
    team_role: str | None
    prize: str | None
    strength: float = Field(description="Сила результата: перцентиль × уровень × давность (§9.2)")


class FspRankOut(ApiModel):
    discipline: str
    rank: str
    awarded_at: date


class CompetencyOut(ApiModel):
    id: str
    name: str
    score: float = Field(ge=0, le=1)
    status: CompetencyStatus
    evidence_count: int


class FspProfileOut(ApiModel):
    linked: bool
    fsp_id: str | None
    method: FspLinkMethod | None
    ownership_verified: bool = Field(description="true только для привязки через ФСП ID (OIDC)")
    linked_at: datetime | None
    ranks: list[FspRankOut]
    achievements: list[FspAchievementOut]
    competencies: list[CompetencyOut]


class OidcStartOut(ApiModel):
    authorization_url: str
