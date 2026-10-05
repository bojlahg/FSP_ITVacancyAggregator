from datetime import datetime

from pydantic import Field, model_validator

from app.core.enums import AssignmentStatus, Grade, GradedBy, ItemKind, TaskKind
from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateBrief
from app.modules.testing.schemas import AnswerPayload, CurrentItem


class EmployerTaskCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    kind: TaskKind
    specialization: str = Field(description="При need_id берётся из потребности")
    grade: Grade | None = Field(default=None, description="null — для всех грейдов специализации")
    need_id: int | None = None
    template_id: str | None = Field(default=None, description="Для kind=auto — шаблон из банка")
    prompt: str | None = Field(default=None, max_length=4000, description="Для kind=approach — текст задачи")
    rubric: list[str] = Field(
        default_factory=list, description="Бинарные критерии оценки подхода (лимит — content/tasks.yaml)"
    )

    @model_validator(mode="after")
    def check_kind(self) -> "EmployerTaskCreate":
        if self.kind == TaskKind.auto and not self.template_id:
            raise ValueError("Для автопроверяемого задания нужен template_id")
        if self.kind == TaskKind.approach and not (self.prompt or "").strip():
            raise ValueError("Для задания на подход нужен prompt")
        if any(not item.strip() or len(item) > 200 for item in self.rubric):
            raise ValueError("Критерий чек-листа — непустая строка до 200 символов")
        return self


class EmployerTaskOut(EmployerTaskCreate):
    id: int
    assignments_total: int = Field(description="Скольким кандидатам задание предложено")
    submissions: int = Field(description="Сколько решений прислано")
    awaiting_rating: int = Field(description="Решения на подход без оценки — ждут работодателя")
    created_at: datetime


class TaskTemplateOption(ApiModel):
    """Шаблон банка для автопроверяемого задания: пример экземпляра без ключа ответа."""

    id: str
    topic: str
    topic_name: str
    skills: list[str] = Field(description="Названия навыков, которые подтвердит верное решение")
    kind: ItemKind
    difficulty_b: float
    difficulty: str
    example_stem: str
    matches_need: bool = Field(description="Шаблон проверяет навык потребности")


class TaskAssignmentForCandidate(ApiModel):
    id: int
    company_name: str
    title: str
    kind: TaskKind
    item: CurrentItem | None = Field(description="Для kind=auto — экземпляр задания (без ключа)")
    prompt: str | None
    rubric: list[str] = Field(description="Критерии, по которым оценят подход")
    status: AssignmentStatus
    offered_at: datetime
    due_at: datetime
    submitted_at: datetime | None
    response: AnswerPayload | None
    score: float | None = Field(description="0..1; null — ещё не проверено")
    graded_by: GradedBy | None
    confirmed_skills: list[str] = Field(description="Навыки, подтверждённые этим заданием")


class TaskSubmit(ApiModel):
    response: AnswerPayload


class TaskSubmissionForEmployer(ApiModel):
    assignment_id: int
    candidate: CandidateBrief
    status: AssignmentStatus
    response: AnswerPayload | None
    score: float | None
    graded_by: GradedBy | None
    rubric_hits: list[bool] = Field(default_factory=list)
    employer_rating: int | None
    submitted_at: datetime | None


class TaskRating(ApiModel):
    rating: int = Field(ge=1, le=5)
