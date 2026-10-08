from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.enums import Grade, NeedStatus, ParserKind, WorkFormat
from app.core.schemas import MAX_RUBLES, ApiModel, CategoryRef, SalaryRange


class NeedFields(SalaryRange):
    title: str = Field(min_length=1, max_length=200)
    raw_text: str | None = Field(
        default=None, max_length=20000, description="Исходный текст потребности или вакансии"
    )
    specialization: str
    grade: Grade
    required_skills: list[str] = Field(default_factory=list, description="id навыков из онтологии")
    optional_skills: list[str] = Field(default_factory=list)
    industry: str | None = None
    team_description: str | None = Field(default=None, max_length=4000)
    work_format: WorkFormat | None = None
    city: str | None = Field(default=None, max_length=100)


class NeedCreate(NeedFields):
    pass


class NeedUpdate(NeedFields):
    """Правка создаёт новую версию потребности; шорт-лист переносится (§8.1)."""


class NeedParseRequest(ApiModel):
    raw_text: str = Field(min_length=20, max_length=20000)


class NeedDraft(ApiModel):
    title: str | None = None
    specialization: str | None = None
    grade: Grade | None = None
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    industry: str | None = None
    team_description: str | None = None
    work_format: WorkFormat | None = None
    city: str | None = None
    salary_from: int | None = Field(default=None, gt=0, le=MAX_RUBLES)
    salary_to: int | None = Field(default=None, gt=0, le=MAX_RUBLES)


class NeedTextIssue(ApiModel):
    rule: str = Field(description="id правила из content/need_text_rules.yaml")
    severity: Literal["block", "warn"] = Field(description="block — мешает публикации, warn — подсказка")
    label: str
    message: str
    fragment: str = Field(description="Найденный фрагмент текста")


class NeedParseResult(ApiModel):
    parser: ParserKind
    draft: NeedDraft = Field(description="Редактируемая форма — работодатель правит до сохранения")
    unmapped_terms: list[str] = Field(description="«Не распознали: …»")
    text_issues: list[NeedTextIssue] = Field(
        default_factory=list, description="Запрещённые требования в тексте (возраст, пол, регистрация…)"
    )


class NeedStats(ApiModel):
    shortlisted: int
    invitations_active: int
    invitations_total: int
    invitations_limit: int
    applications: int


class NeedOut(NeedFields):
    id: int
    version: int
    parent_id: int | None
    status: NeedStatus
    published: bool
    published_at: datetime | None
    category: CategoryRef
    stats: NeedStats
    text_issues: list[NeedTextIssue] = Field(
        default_factory=list, description="Запрещённые требования в тексте (возраст, пол, регистрация…)"
    )
    created_at: datetime


class ShortlistNote(ApiModel):
    note: str | None = Field(default=None, max_length=1000)
