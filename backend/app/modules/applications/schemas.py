from datetime import datetime

from pydantic import Field

from app.core.enums import ApplicationStatus, Grade, WorkFormat
from app.core.schemas import ApiModel, CategoryRef, Explanation
from app.modules.candidates.schemas import Contacts
from app.modules.employers.schemas import CompanyPublic
from app.modules.matching.schemas import CandidateBrief


class VacancyOut(ApiModel):
    id: int
    title: str
    company: CompanyPublic
    category: CategoryRef
    specialization: str
    grade: Grade
    required_skills: list[str]
    optional_skills: list[str]
    salary_from: int
    salary_to: int
    work_format: WorkFormat | None
    city: str | None
    team_description: str | None
    description: str | None
    published_at: datetime
    match_score: int | None = Field(
        default=None, description="Совпадение с профилем кандидата, если есть категория"
    )
    match_explanation: Explanation | None = None
    applied: bool = False


class ApplyRequest(ApiModel):
    cover_note: str | None = Field(default=None, max_length=2000)


class ApplicationForCandidate(ApiModel):
    id: int
    vacancy: VacancyOut
    cover_note: str | None
    status: ApplicationStatus
    created_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None


class ApplicationForEmployer(ApiModel):
    id: int
    need_id: int
    candidate: CandidateBrief
    cover_note: str | None
    match_score: int | None = Field(
        description="null — категория кандидата вне категорий вакансии или снимок не сохранился"
    )
    match_explanation: Explanation
    contacts: Contacts = Field(description="Отклик кандидата сразу раскрывает контакты (ТЗ §2.2)")
    status: ApplicationStatus
    created_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None
