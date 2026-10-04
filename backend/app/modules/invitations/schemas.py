from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.core.enums import DeclineReason, InvitationStatus
from app.core.schemas import ApiModel, Explanation, SalaryRange
from app.modules.candidates.schemas import Contacts
from app.modules.employers.schemas import CompanyPublic
from app.modules.matching.schemas import CandidateBrief


class ContactMethod(ApiModel):
    """Как кандидат может связаться с работодателем — обязательная часть приглашения (ТЗ §2.2)."""

    name: str = Field(min_length=1, max_length=200, description="Контактное лицо")
    email: EmailStr | None = None
    telegram: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def at_least_one_channel(self) -> "ContactMethod":
        if not (self.email or self.telegram or self.phone):
            raise ValueError("Нужен хотя бы один способ связи: email, telegram или телефон")
        return self


class InvitationCreate(SalaryRange):
    candidate_id: int
    need_id: int | None = Field(default=None, description="Привязка к потребности или вакансии необязательна")
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000, description="Описание предложения")
    contact_method: ContactMethod
    expires_in_days: int | None = Field(default=None, ge=1, le=60)


class InvitationForCandidate(ApiModel):
    id: int
    company: CompanyPublic
    title: str
    message: str
    salary_from: int
    salary_to: int
    contact_method: ContactMethod
    why_you: Explanation = Field(
        description="Почему выбрали именно вас — тот же расчёт, что видит работодатель"
    )
    status: InvitationStatus
    created_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None
    expires_at: datetime


class InvitationForEmployer(ApiModel):
    id: int
    candidate: CandidateBrief
    need_id: int | None
    title: str
    message: str
    salary_from: int
    salary_to: int
    contact_method: ContactMethod
    match_snapshot: Explanation | None
    status: InvitationStatus
    decline_reason: DeclineReason | None
    decline_comment: str | None
    contacts: Contacts | None = Field(description="Контакты кандидата — после accepted")
    created_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None
    expires_at: datetime


class DeclineRequest(ApiModel):
    reason: DeclineReason
    comment: str | None = Field(default=None, max_length=1000)


class DeclineStats(ApiModel):
    total_sent: int
    accepted: int
    declined: int
    expired: int
    acceptance_rate: float | None
    by_reason: dict[DeclineReason, int]
    top_reason: DeclineReason | None
    hint: str | None = Field(description="Например: «3 из 5 отказов — зарплата»")
