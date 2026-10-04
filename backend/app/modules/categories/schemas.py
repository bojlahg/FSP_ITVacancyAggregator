from datetime import datetime

from pydantic import Field

from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade
from app.core.schemas import ApiModel, CategoryRef


class CategoryRecord(ApiModel):
    category: CategoryRef
    theta: float
    percentile: float | None
    assigned_at: datetime
    valid_until: datetime
    is_current: bool
    needs_reconfirmation: bool = Field(description="Срок действия результата истёк")


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
