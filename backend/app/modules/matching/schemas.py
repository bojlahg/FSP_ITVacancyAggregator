from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.enums import InvitationStatus, WorkFormat
from app.core.schemas import ApiModel, CategoryRef, Explanation, FspBadge
from app.modules.candidates.schemas import Contacts, ExperienceItem, SkillState
from app.modules.fsp.schemas import FspProfileOut
from app.modules.testing.schemas import ApproachAnswer, TopicScore


class CandidateBrief(ApiModel):
    """Обезличенная карточка в списках: без контактов, фамилия скрыта по умолчанию."""

    id: int
    display_name: str = Field(
        description="Имя и первая буква фамилии (или полностью, если кандидат разрешил)"
    )
    category: CategoryRef
    percentile: float | None
    vps: float = Field(description="Сила подтверждённого профиля внутри категории, 0..1 (§8.3)")
    city: str | None
    relocation: bool
    work_formats: list[WorkFormat]
    salary_min: int | None = Field(description="null, если кандидат скрыл ожидания")
    fsp: FspBadge
    verified_skills: list[str]
    declared_skills: list[str]
    last_activity_at: datetime | None


class MatchComponents(ApiModel):
    """Компоненты score, каждый 0..1 — формула в docs/implementation.md §8.3."""

    skills: float
    strength: float
    category: float
    fsp: float
    fresh: float
    conditions: float


class CandidateMatch(ApiModel):
    candidate: CandidateBrief
    score: int = Field(ge=0, le=100)
    components: MatchComponents
    explanation: Explanation
    shortlisted: bool = False
    out_of_filter_reasons: list[str] = Field(default_factory=list)
    invitation_status: InvitationStatus | None = Field(
        default=None, description="Статус последнего приглашения от вашей компании, если оно было"
    )


class CategoryRecommendation(ApiModel):
    category: CategoryRef
    fit: Literal["exact", "adjacent_grade", "adjacent_specialization", "adjacent_both"]
    candidates_count: int
    with_fsp_count: int
    salary_coverage: float | None = Field(
        description="Доля кандидатов категории, чьи ожидания укладываются в вилку"
    )
    reason: str


class RecommendationsOut(ApiModel):
    need_id: int
    need_version: int
    categories: list[CategoryRecommendation]
    candidates: list[CandidateMatch]
    out_of_filter: list[CandidateMatch] = Field(description="Не прошли жёсткие фильтры — с причиной")
    shortlist: list[CandidateMatch] = Field(description="Закреплённые кандидаты — не теряются при уточнении")
    total: int


class SalaryBucket(ApiModel):
    salary_from: int
    salary_to: int
    count: int


class SalaryMarketCheck(ApiModel):
    verdict: Literal["ok", "below_market", "suspicious_high", "unknown"] = Field(
        description="ok — в рынке; below_market — покрывает мало ожиданий категории; "
        "suspicious_high — нижняя граница намного выше медианы ожиданий (признак вакансии-приманки); "
        "unknown — мало данных"
    )
    coverage: float | None = Field(description="Доля ожиданий категории, которые покрывает верхняя граница")
    median_expectation: int | None
    message: str


class SalaryCoverage(ApiModel):
    category: CategoryRef
    coverage: float = Field(description="Доля кандидатов категории с ожиданиями ≤ верхней границы вилки")
    median_expectation: int | None
    histogram: list[SalaryBucket]
    market: SalaryMarketCheck


class CategoryCatalogItem(ApiModel):
    category: CategoryRef
    candidates_count: int
    with_fsp_count: int
    median_percentile: float | None
    median_salary: int | None


class TalentSearchOut(ApiModel):
    items: list[CandidateBrief]
    total: int


class CandidateCard(ApiModel):
    brief: CandidateBrief
    about: str | None
    experience_years: float | None
    roles: list[str]
    industries_exp: list[str]
    soft_skills: list[str]
    experience: list[ExperienceItem] = Field(description="Без названий компаний до раскрытия контактов")
    skills: list[SkillState]
    topic_scores: list[TopicScore]
    approach_answers: list[ApproachAnswer] = Field(
        default_factory=list, description="Ответы на открытый вопрос о подходе из теста текущей категории"
    )
    fsp: FspProfileOut | None = Field(description="null, если кандидат скрыл ФСП")
    contacts_unlocked: bool
    contacts: Contacts | None = Field(description="Только после принятого приглашения или отклика")
    match: CandidateMatch | None = Field(description="Если передан need_id")
    invitation_status: InvitationStatus | None = Field(
        default=None, description="Статус последнего приглашения от вашей компании, если оно было"
    )
    grade_history: list[CategoryRef]


# ---------- экспорт в ATS: JSON Resume (https://jsonresume.org/schema) + расширение x-itscout ----------

JSON_RESUME_SCHEMA = "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json"


class JsonResumeLocation(ApiModel):
    city: str | None = None


class JsonResumeProfile(ApiModel):
    network: str
    username: str


class JsonResumeBasics(ApiModel):
    name: str = Field(description="До раскрытия контактов — имя и первая буква фамилии")
    label: str = Field(description="Категория по тесту, например «Backend · Middle»")
    email: str | None = Field(default=None, description="Только после раскрытия контактов")
    phone: str | None = Field(default=None, description="Только после раскрытия контактов")
    summary: str | None = None
    location: JsonResumeLocation
    profiles: list[JsonResumeProfile] = Field(description="Telegram — только после раскрытия контактов")


class JsonResumeWork(ApiModel):
    name: str | None = Field(default=None, description="Компания — только после раскрытия контактов")
    position: str
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    summary: str | None = None


class JsonResumeSkill(ApiModel):
    name: str
    level: str = Field(description="Источник подтверждения: проверено тестом, ФСП, заданием или заявлено")
    keywords: list[str]


class JsonResumeAward(ApiModel):
    title: str
    date: str
    awarder: str
    summary: str


class ItscoutExtension(ApiModel):
    candidate_id: int
    category: CategoryRef
    percentile: float | None = Field(description="Перцентиль в категории по тесту")
    topic_scores: list[TopicScore]
    fsp_ranks: list[str]
    match: CandidateMatch | None = Field(description="Совпадение с потребностью, если передан need_id")
    contacts_unlocked: bool
    generated_at: datetime


class JsonResume(ApiModel):
    schema_url: str = Field(default=JSON_RESUME_SCHEMA, alias="$schema")
    basics: JsonResumeBasics
    work: list[JsonResumeWork]
    skills: list[JsonResumeSkill]
    awards: list[JsonResumeAward]
    itscout: ItscoutExtension = Field(alias="x-itscout")
