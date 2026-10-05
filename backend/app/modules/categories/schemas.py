from datetime import datetime

from pydantic import Field

from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade
from app.core.schemas import ApiModel, CategoryRef
from app.modules.testing.schemas import GradeEvidence


class CategoryRecord(ApiModel):
    category: CategoryRef
    theta: float
    percentile: float | None
    assigned_at: datetime
    valid_until: datetime
    is_current: bool
    needs_reconfirmation: bool = Field(description="Срок действия результата истёк")
    evidence: GradeEvidence | None = Field(
        default=None,
        description="Только у текущей категории: тест, уверенность в грейде (§10.4.1); null — теста нет",
    )


class AttemptSummary(ApiModel):
    id: int
    specialization: str
    grade_target: Grade
    purpose: AttemptPurpose
    status: AttemptStatus
    result: AttemptResult | None
    started_at: datetime
    finished_at: datetime | None


class GradeAction(ApiModel):
    action: str = Field(description="calibrate | upgrade | downgrade | retry")
    grade: Grade
    allowed: bool
    available_at: datetime | None = Field(description="Когда станет доступно, если сейчас нельзя")
    reason: str | None = None


class GradeStatus(ApiModel):
    current: CategoryRecord | None
    history: list[CategoryRecord]
    attempts: list[AttemptSummary]
    actions: list[GradeAction]
    cooldown_days: int


class GradeDecision(ApiModel):
    """Как тест определил категорию (§10.4): θ̂ против порога грейда; решение — только по тесту."""

    category: CategoryRef
    theta: float = Field(description="Оценка способности θ̂ на шкале специализации")
    se: float | None = Field(description="Стандартная ошибка θ̂")
    cut: float = Field(description="Порог грейда на той же шкале")
    next_grade: Grade | None
    next_cut: float | None = Field(description="Порог следующего грейда")
    result: AttemptResult | None = Field(description="pass — θ̂ ≥ порога; confident_pass — с запасом в SE")
    percentile: float | None
    attempt_id: int | None
    tested_at: datetime = Field(description="Когда завершён тест, давший категорию")
    valid_until: datetime


class GradeExplanation(ApiModel):
    current: GradeDecision | None
