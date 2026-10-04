from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schemas import ApiModel


class EmployerProfileFields(ApiModel):
    inn: str | None = Field(default=None, pattern=r"^\d{10}(\d{2})?$")
    industry: str | None = None
    description: str | None = Field(default=None, max_length=4000)
    website: str | None = Field(default=None, max_length=300)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_telegram: str | None = Field(default=None, max_length=64)


class EmployerProfileUpdate(EmployerProfileFields):
    company_name: str = Field(min_length=1, max_length=200)


class EmployerReputation(ApiModel):
    """Сигналы добросовестности работодателя, видимые кандидату (§8.6)."""

    invitations_sent: int
    acceptance_rate: float | None
    withdrawn_rate: float | None
    median_response_hours: float | None = Field(description="Медиана времени ответа на отклики")


class EmployerProfileOut(EmployerProfileFields):
    id: int
    company_name: str | None = Field(description="null, пока профиль компании не заполнен")
    reputation: EmployerReputation
    updated_at: datetime


class CompanyPublic(ApiModel):
    id: int
    company_name: str
    industry: str | None
    website: str | None
    description: str | None
    reputation: EmployerReputation
