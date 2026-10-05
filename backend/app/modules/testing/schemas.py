from datetime import datetime

from pydantic import Field, model_validator

from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade, ItemKind, TemplateStatus
from app.core.schemas import ApiModel, CategoryRef
from app.modules.needs.schemas import NeedDraft


class AttemptCreate(ApiModel):
    specialization: str
    grade_target: Grade
    purpose: AttemptPurpose = AttemptPurpose.calibration


class AttemptOut(ApiModel):
    id: int
    specialization: str
    grade_target: Grade
    purpose: AttemptPurpose
    status: AttemptStatus
    answered: int
    total_estimate: int = Field(description="Ожидаемое число заданий (может вырасти у порога грейда)")
    started_at: datetime
    finished_at: datetime | None


class ItemOption(ApiModel):
    id: str
    text: str


class CurrentItem(ApiModel):
    """Текущее задание. Ключ ответа никогда не передаётся (§13)."""

    finished: bool = Field(description="true — заданий больше нет, смотрите /result")
    item_id: int | None = None
    position: int | None = None
    total_estimate: int | None = None
    kind: ItemKind | None = None
    stem: str | None = None
    code: str | None = Field(default=None, description="Фрагмент кода к заданию, если есть")
    code_language: str | None = None
    options: list[ItemOption] = Field(default_factory=list)
    max_length: int | None = Field(default=None, description="Для open_approach")
    time_limit_sec: int | None = None
    deadline_at: datetime | None = Field(default=None, description="Серверный дедлайн ответа")


class AnswerPayload(ApiModel):
    choice_ids: list[str] | None = Field(
        default=None, description="single_choice / multi_choice / code_output"
    )
    number: float | None = Field(default=None, description="numeric")
    order: list[str] | None = Field(default=None, description="ordering — id вариантов в порядке")
    text: str | None = Field(default=None, max_length=1500, description="open_approach")


class AnswerRequest(ApiModel):
    item_id: int
    response: AnswerPayload
    focus_lost_count: int = Field(
        default=0, ge=0, description="Сколько раз уходили со вкладки (флаг, не штраф)"
    )


class AnswerAck(ApiModel):
    accepted: bool
    late: bool = Field(description="Ответ пришёл после дедлайна — засчитан как неверный")
    finished: bool


class TopicScore(ApiModel):
    topic: str
    name: str
    score: float = Field(ge=0, le=1)
    items: int


class ApproachCriterion(ApiModel):
    text: str
    met: bool | None = Field(description="Отметка LLM по чек-листу; null — ответ ещё не оценён")


class ApproachAnswer(ApiModel):
    question: str
    answer: str = Field(description="До раскрытия контактов email, телефоны и ссылки вычищены")
    criteria: list[ApproachCriterion]
    score: float | None = Field(description="Доля отмеченных критериев; в θ̂ и категорию не входит (§10.5)")


class NextAction(ApiModel):
    action: str = Field(description="retake_lower | try_higher | none")
    grade: Grade | None = None
    available_at: datetime | None = None
    message: str


class AttemptResultOut(ApiModel):
    attempt_id: int
    specialization: str
    grade_target: Grade
    result: AttemptResult
    theta: float = Field(description="Оценка способности на IRT-шкале специализации")
    se: float = Field(description="Стандартная ошибка оценки")
    percentile: float | None = Field(description="Перцентиль в категории, 0..1")
    category: CategoryRef | None = Field(description="Присвоенная или сохранённая категория")
    topic_scores: list[TopicScore]
    verified_skills: list[str] = Field(description="id навыков из /catalog/skills, проверенных тестом")
    approach_score: float | None = None
    next_actions: list[NextAction]


class VacancyExample(ApiModel):
    slug: str
    title: str
    raw_text: str


class VacancyTestPreviewRequest(ApiModel):
    raw_text: str | None = Field(default=None, max_length=20000)
    need_id: int | None = None
    regenerate_seed: int | None = Field(
        default=None, ge=0, le=2_000_000_000, description="Другой seed — другие экземпляры той же сложности"
    )

    @model_validator(mode="after")
    def one_source(self) -> "VacancyTestPreviewRequest":
        if not (self.raw_text or self.need_id):
            raise ValueError("Нужен raw_text или need_id")
        if self.need_id is None and len((self.raw_text or "").strip()) < 20:
            raise ValueError("Текст вакансии слишком короткий: нужно хотя бы 20 символов")
        return self


class TopicWeight(ApiModel):
    topic: str
    name: str
    base_items: int = Field(description="Заданий по теме в базовом blueprint специализации")
    items: int = Field(description="Заданий по теме после смещения по требованиям вакансии")


class BlueprintPreview(ApiModel):
    specialization: str
    grade: Grade = Field(description="Грейд вакансии: примеры заданий берутся у его порога")
    total_items: int = Field(description="Оцениваемых заданий в основном блоке теста")
    topics: list[TopicWeight] = Field(description="Темы в порядке убывания числа заданий")
    stack_modules: list[str] = Field(description="Стек-модули по навыкам вакансии: python, java, react…")
    weight_changes: list[str] = Field(description="Почему изменились веса: «Kafka → +2 к теме Архитектура»")


class PreviewItem(ApiModel):
    """Пример задания. Ключ ответа не передаётся даже работодателю (инвариант §13)."""

    template_id: str
    topic: str
    topic_name: str
    skills: list[str] = Field(description="Названия навыков, которые проверяет шаблон")
    difficulty_b: float = Field(description="Сложность шаблона на IRT-шкале специализации")
    difficulty: str = Field(description="Сложность словами относительно порогов грейдов")
    kind: ItemKind
    stem: str
    code: str | None = None
    code_language: str | None = None
    options: list[ItemOption]


class SkillRef(ApiModel):
    id: str
    name: str


class LlmTemplateDraft(ApiModel):
    title: str
    topic: str
    skills: list[str]
    stem: str
    status: TemplateStatus = Field(description="Всегда pilot: не влияет на оценку до калибровки")


class VacancyTestPreview(ApiModel):
    requirements: NeedDraft
    blueprint: BlueprintPreview
    sample_items: list[PreviewItem]
    seed: int = Field(description="Seed экземпляров; seed+1 — другие экземпляры тех же шаблонов")
    uncovered_skills: list[SkillRef] = Field(
        description="Навыки вакансии, для которых в банке нет шаблонов этой специализации"
    )
    llm_available: bool = Field(description="Генерация черновиков LLM включена на стенде")
    llm_note: str = Field(description="Что с черновиками: созданы, не нужны или генерация выключена")
    llm_drafts: list[LlmTemplateDraft]
