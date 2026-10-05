from datetime import datetime
from typing import Literal

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


class IntegrityReason(ApiModel):
    code: Literal["person_fit", "rapid_guessing", "fast_correct_hard"]
    text: str


class IntegritySignals(ApiModel):
    """Сигналы честности попытки (§10.9): пометка для человека, в θ̂, грейд, категорию и score не входит."""

    enough_data: bool = Field(description="false — оценённых заданий слишком мало, сигналы не считались")
    flagged: bool = Field(description="Есть хотя бы один сигнал — стоит перепроверить на собеседовании")
    reasons: list[IntegrityReason]
    note: str = Field(description="Пояснение для работодателя; при flagged — «стоит перепроверить»")
    items: int = Field(description="Оценённых заданий в попытке")
    lz_star: float | None = Field(description="Person-fit lz*: ниже порога — ответы плохо согласуются с IRT")
    rapid_share: float | None = Field(description="Доля ответов быстрее нормативного порога NT10")
    fast_correct_hard: int | None = Field(description="Верных ответов на трудных заданиях быстрее порога")


class GradeBandProbability(ApiModel):
    grade: Grade | None = Field(description="null — ниже порога стажёра: категория не присваивается")
    label: str
    probability: float = Field(description="P(истинный уровень в полосе грейда) при θ ~ N(θ̂, SE²)")


class GradeConfidence(ApiModel):
    """Уверенность в грейде (§10.4.1, Rudner 2001/2005): объяснение решения, на грейд не влияет."""

    grade: Grade = Field(description="Грейд, к которому относится уверенность: присвоенный или проверяемый")
    at_least: float = Field(description="P(θ ≥ cut грейда) — вероятность, что уровень не ниже этого грейда")
    level: str = Field(description="Словесный уровень по content/confidence.yaml: high | medium | low")
    level_label: str
    text: str = Field(
        description="Готовая фраза: работодателю «87% — вероятность, что уровень не ниже Middle», "
        "кандидату «Уверенность: 87%, что ваш уровень не ниже Middle»"
    )
    bands: list[GradeBandProbability] = Field(description="Вероятности всех полос шкалы, снизу вверх")
    note: str


class GradeEvidence(ApiModel):
    """Блок «Почему этому грейду можно верить» (§10.4.1): из чего сложилась категория."""

    tested_at: datetime | None = Field(description="Когда завершён тест, по которому присвоена категория")
    valid_until: datetime = Field(description="Срок действия результата (§6.3)")
    adaptive: bool = Field(description="Двухэтапный адаптивный тест (MST): задания подбирались по ответам")
    short_mode: bool = Field(description="Сокращённый демо-режим теста (TEST_MODE=short)")
    items_scored: int = Field(description="Оценённых заданий в попытке")
    theta: float
    se: float = Field(description="Стандартная ошибка θ̂")
    confidence: GradeConfidence
    how_it_works_path: str = Field(description="Публичная страница о том, как устроен тест")
    validation_url: str = Field(description="Отчёт симуляционной валидации (§12)")


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
    confidence: GradeConfidence = Field(
        description="Уверенность относительно проверяемого грейда (§10.4.1); на результат не влияет"
    )
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


# Публичная страница «Как работает тест». Ключи ответов сюда не попадают (инвариант §13).


class ExplainerGrade(ApiModel):
    grade: Grade
    name: str
    cut: float = Field(description="Порог грейда на IRT-шкале специализации, логиты")


class ExplainerSpecialization(ApiModel):
    slug: str
    name: str
    active_templates: int = Field(description="Активных шаблонов с автопроверкой в банке специализации")
    topics: int = Field(description="Тем в blueprint специализации")


class ExplainerOverview(ApiModel):
    grades: list[ExplainerGrade]
    active_templates: int = Field(description="Активных шаблонов с автопроверкой во всём банке")
    specializations: list[ExplainerSpecialization] = Field(description="Только специализации с тестом")
    stage1_items: int
    stage2_items: int
    extra_items_max: int
    stage_split: float = Field(description="Насколько θ̂ этапа 1 должна отойти от порога, чтобы сменить блок")
    max_seeds: int = Field(description="Сколько экземпляров можно запросить за раз")
    max_sample: int = Field(description="Максимальный размер выборки для подсчёта разнообразия")
    leak_size: int = Field(description="Сколько экземпляров шаблона считаются «слитыми» в подсчёте")


class ExplainerTemplate(ApiModel):
    id: str
    topic: str
    topic_name: str
    kind: ItemKind
    skills: list[str] = Field(description="Названия навыков, которые проверяет шаблон")
    a: float = Field(description="Дискриминация")
    b: float = Field(description="Сложность на IRT-шкале специализации, логиты")
    c: float = Field(description="Вероятность угадать: 1/k для выбора одного варианта, иначе 0")
    difficulty: str = Field(description="Сложность словами относительно порогов грейдов")


class CurvePoint(ApiModel):
    theta: float
    value: float


class ExplainerInstance(ApiModel):
    seed: int
    stem: str
    code: str | None = None
    code_language: str | None = None
    options: list[ItemOption]


class ExplainerInstances(ApiModel):
    template: ExplainerTemplate
    icc: list[CurvePoint] = Field(description="Вероятность верного ответа P(θ) по модели 3PL")
    instances: list[ExplainerInstance]


class ExplainerDiversity(ApiModel):
    template_id: str
    sample: int = Field(description="Сколько экземпляров отрендерено")
    distinct: int = Field(description="Сколько из них различны по тексту, коду и набору вариантов")
    collision_probability: float = Field(
        description="Вероятность, что два кандидата получат одинаковый экземпляр"
    )
    leak_size: int = Field(description="Сколько экземпляров считаются слитыми")
    leak_match_share: float = Field(
        description="Доля новых экземпляров, совпавших с одним из слитых: столько ответов помогла бы утечка"
    )


class InformationPoint(ApiModel):
    theta: float
    information: float = Field(description="Информация Фишера теста в точке θ")
    se: float = Field(description="Ожидаемая стандартная ошибка θ̂: 1/√(I + 1) с априорным N(0,1)")


class ExplainerItemPoint(ApiModel):
    b: float
    a: float
    stage: int = Field(description="1 — этап 1, 2 — этап 2, 3 — дополнительное задание у порога")


class ExplainerScenario(ApiModel):
    scenario: Literal["below", "at", "above"]
    label: str
    theta_true: float = Field(description="Истинная способность симулированного кандидата")
    stage2_target: float = Field(description="Куда чаще всего уходит блок этапа 2 (средняя цель)")
    items_mean: float = Field(description="Среднее число оценённых заданий")
    se_mean: float = Field(description="Средняя итоговая SE оценки θ̂")
    pass_share: float = Field(description="Доля симуляций с решением «пройден»")
    information: list[InformationPoint] = Field(description="Средняя информационная функция теста")
    items: list[ExplainerItemPoint] = Field(description="Задания одной симулированной попытки")


class ExplainerInformation(ApiModel):
    specialization: str
    grade: Grade
    cut: float
    grades: list[ExplainerGrade]
    stack_module: str | None = Field(description="Стек-модуль симулированных кандидатов")
    simulations: int = Field(description="Симулированных попыток на сценарий")
    template_overlap: float = Field(
        description="Средняя доля общих шаблонов у двух попыток сценария «у порога»"
    )
    instance_overlap: float = Field(
        description="Средняя доля общих экземпляров (тот же текст, код и варианты) у тех же пар попыток"
    )
    scenarios: list[ExplainerScenario]
