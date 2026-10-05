from datetime import date, datetime

from pydantic import EmailStr, Field

from app.core.enums import ConsentKind, FspLinkMethod, SearchStatus, SkillSource, SkillStatus, WorkFormat
from app.core.schemas import ApiModel, CategoryRef


class ExperienceItem(ApiModel):
    company: str = Field(max_length=200)
    position: str = Field(max_length=200)
    started_on: date | None = None
    ended_on: date | None = Field(default=None, description="null — по настоящее время")
    description: str | None = None


class DeclaredSkill(ApiModel):
    skill_id: str = Field(description="id из онтологии /catalog/skills")


class SkillState(ApiModel):
    skill_id: str
    name: str
    status: SkillStatus = Field(description="Итоговый статус: проверено тестом / подтверждено ФСП / заявлено")
    sources: list[SkillSource]


class PrivacySettings(ApiModel):
    show_last_name: bool = Field(default=False, description="Показывать фамилию до раскрытия контактов")
    show_fsp: bool = True
    show_salary: bool = True
    hidden_employer_ids: list[int] = Field(
        default_factory=list, description="Компании, от которых профиль скрыт"
    )


class Contacts(ApiModel):
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    telegram: str | None = None


class CandidateProfileBase(ApiModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    telegram: str | None = Field(default=None, max_length=64)
    contact_email: EmailStr | None = None
    city: str | None = Field(default=None, max_length=100)
    relocation: bool = False
    work_formats: list[WorkFormat] = Field(default_factory=list)
    salary_min: int | None = Field(default=None, gt=0, description="Минимальные ожидания, ₽")
    salary_max: int | None = Field(default=None, gt=0)
    experience_years: float | None = Field(default=None, ge=0, le=60)
    roles: list[str] = Field(default_factory=list)
    industries_exp: list[str] = Field(default_factory=list)
    industries_pref: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    about: str | None = Field(default=None, max_length=4000)
    search_status: SearchStatus = SearchStatus.open


class CandidateProfileUpdate(CandidateProfileBase):
    declared_skills: list[DeclaredSkill] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)


class CandidateProfileOut(CandidateProfileBase):
    id: int
    specialization: str | None
    category: CategoryRef | None = Field(description="Действующая категория по итогам теста")
    skills: list[SkillState]
    experience: list[ExperienceItem]
    privacy: PrivacySettings
    fsp_id: str | None
    fsp_link_method: FspLinkMethod | None
    profile_completeness: float = Field(ge=0, le=1)
    onboarding_step: str = Field(description="survey | specialization | grade | test | done")
    updated_at: datetime


class SearchStatusUpdate(ApiModel):
    search_status: SearchStatus = Field(description="hidden — профиль скрыт из поиска")


class CompanyRef(ApiModel):
    id: int
    company_name: str


class ConsentOut(ApiModel):
    kind: ConsentKind
    granted: bool
    policy_version: str | None
    granted_at: datetime | None
    revoked_at: datetime | None


class ConsentUpdate(ApiModel):
    kind: ConsentKind
    granted: bool
