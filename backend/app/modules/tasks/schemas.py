from datetime import datetime

from pydantic import Field, model_validator

from app.core.enums import AssignmentStatus, Grade, GradedBy, TaskKind
from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateBrief
from app.modules.testing.schemas import AnswerPayload, CurrentItem


class EmployerTaskCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    kind: TaskKind
    specialization: str
    grade: Grade | None = None
    need_id: int | None = None
    template_id: str | None = Field(default=None, description="Для kind=auto — шаблон из банка")
    prompt: str | None = Field(default=None, max_length=4000, description="Для kind=approach — текст задачи")
    rubric: list[str] = Field(default_factory=list, description="Бинарные критерии оценки подхода")

    @model_validator(mode="after")
    def check_kind(self) -> "EmployerTaskCreate":
        if self.kind == TaskKind.auto and not self.template_id:
            raise ValueError("Для автопроверяемого задания нужен template_id")
        if self.kind == TaskKind.approach and not self.prompt:
            raise ValueError("Для задания на подход нужен prompt")
        return self


class EmployerTaskOut(EmployerTaskCreate):
    id: int
    assignments_total: int
    submissions: int
    created_at: datetime


class TaskAssignmentForCandidate(ApiModel):
    id: int
    company_name: str
    title: str
    kind: TaskKind
    item: CurrentItem | None = Field(description="Для kind=auto — экземпляр задания")
    prompt: str | None
    status: AssignmentStatus
    offered_at: datetime
    due_at: datetime
    score: float | None


class TaskSubmit(ApiModel):
    response: AnswerPayload


class TaskSubmissionForEmployer(ApiModel):
    assignment_id: int
    candidate: CandidateBrief
    response: AnswerPayload | None
    score: float | None
    graded_by: GradedBy | None
    rubric_hits: list[bool] = Field(default_factory=list)
    employer_rating: int | None
    submitted_at: datetime | None


class TaskRating(ApiModel):
    rating: int = Field(ge=1, le=5)
