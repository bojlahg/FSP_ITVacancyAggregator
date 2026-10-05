from datetime import datetime

from pydantic import EmailStr, Field, model_validator

from app.core.enums import DeclineReason, InvitationStatus, ReportReason, ReportStatus
from app.core.schemas import ApiModel, Explanation, SalaryRange
from app.modules.candidates.schemas import Contacts
from app.modules.employers.schemas import CompanyPublic
from app.modules.matching.schemas import CandidateBrief, SalaryMarketCheck


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


class InvitationWarning(ApiModel):
    rule: str = Field(description="id правила из content/invitation_scam_rules.yaml")
    label: str
    message: str
    fragment: str = Field(description="Найденный фрагмент текста приглашения")


class ReportRequest(ApiModel):
    reason: ReportReason
    comment: str | None = Field(default=None, max_length=1000)


class ReportBrief(ApiModel):
    reason: ReportReason
    status: ReportStatus
    created_at: datetime


class InvitationForCandidate(ApiModel):
    id: int
    company: CompanyPublic
    title: str
    message: str
    salary_from: int
    salary_to: int
    contact_method: ContactMethod | None = Field(description="Контакт рекрутера — после принятия приглашения")
    why_you: Explanation = Field(
        description="Почему выбрали именно вас — тот же расчёт, что видит работодатель"
    )
    salary_market: SalaryMarketCheck | None = Field(
        default=None, description="Вилка против ожиданий вашей категории: в рынке, ниже или выше рынка"
    )
    status: InvitationStatus
    created_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None
    expires_at: datetime
    warnings: list[InvitationWarning] = Field(
        default_factory=list,
        description="Признаки мошенничества в тексте: оплата, крипта, мессенджер, документы",
    )
    report: ReportBrief | None = Field(default=None, description="Жалоба кандидата, если подана")


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


class ReportForAdmin(ApiModel):
    id: int
    invitation_id: int
    employer_id: int
    company_name: str | None
    invitation_title: str
    invitation_message: str
    warnings: list[InvitationWarning]
    reason: ReportReason
    comment: str | None
    status: ReportStatus
    resolution: str | None
    created_at: datetime
    resolved_at: datetime | None


class ReportResolve(ApiModel):
    resolution: str = Field(min_length=1, max_length=2000, description="Что сделано по жалобе")
