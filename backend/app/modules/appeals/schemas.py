from datetime import datetime

from pydantic import Field

from app.core.enums import AppealStatus
from app.core.schemas import ApiModel, CategoryRef


class AppealCreate(ApiModel):
    comment: str = Field(
        min_length=10, max_length=2000, description="Почему кандидат не согласен с результатом теста"
    )


class AppealResolve(ApiModel):
    reply: str = Field(min_length=1, max_length=2000, description="Ответ проверяющего кандидату")


class AppealOut(ApiModel):
    id: int
    category: CategoryRef = Field(description="Оспариваемая категория — снимок на момент обращения")
    theta: float
    comment: str
    status: AppealStatus
    reply: str | None
    created_at: datetime
    resolved_at: datetime | None


class AdminAppealOut(AppealOut):
    candidate_id: int
    candidate_name: str
    category_is_current: bool = Field(description="Оспариваемая категория всё ещё действующая")
