from datetime import datetime

from pydantic import Field, model_validator

from app.core.enums import AssignmentStatus, Grade, GradedBy, TaskKind
from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateBrief
from app.modules.testing.schemas import AnswerPayload, CurrentItem


class EmployerTaskCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    kind: TaskKind
    specialization: str = Field(description="При need_id берётся из потребности")
    grade: Grade | None = Field(default=None, description="null — для всех грейдов специализации")
    need_id: int | None = None
    pool: str | None = Field(
        default=None, description="Для kind=auto — группа заданий из GET /employer-tasks/templates (key)"
    )
    prompt: str | None = Field(default=None, max_length=4000, description="Для kind=approach — текст задачи")
    rubric: list[str] = Field(
        default_factory=list, description="Бинарные критерии оценки подхода (лимит — content/tasks.yaml)"
    )

    @model_validator(mode="after")
    def check_kind(self) -> "EmployerTaskCreate":
        if self.kind == TaskKind.auto and not self.pool:
            raise ValueError("Для автопроверяемого задания выберите тему и уровень")
        if self.kind == TaskKind.approach and not (self.prompt or "").strip():
            raise ValueError("Для задания на подход нужен prompt")
        if any(not item.strip() or len(item) > 200 for item in self.rubric):
            raise ValueError("Критерий чек-листа — непустая строка до 200 символов")
        return self


class EmployerTaskOut(EmployerTaskCreate):
    id: int
    pool_name: str | None = Field(description="Тема и уровень автопроверяемого задания")
    assignments_total: int = Field(description="Скольким кандидатам задание предложено")
    submissions: int = Field(description="Сколько решений прислано")
    awaiting_rating: int = Field(description="Решения на подход без оценки — ждут работодателя")
    created_at: datetime


class TaskTemplateOption(ApiModel):
    """Группа заданий банка «тема × стек × уровень»: тексты, id и сложность шаблонов скрыты (§10.6)."""

    key: str = Field(description="Передаётся в pool при создании задания")
    name: str = Field(description="Тема, стек и уровень словами")
    topic_name: str
    level: str = Field(description="Уровень словами: «уровень Middle»")
    skills: list[str] = Field(description="Навыки, которые может подтвердить верное решение")
    matches_need: bool = Field(description="В группе есть задания на навыки потребности")


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
