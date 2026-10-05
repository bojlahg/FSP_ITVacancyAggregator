from typing import Literal

from pydantic import Field, model_validator

from app.core.enums import Grade, ItemKind
from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateCard
from app.modules.testing.schemas import ExplainerInstance


class ExpertNeed(ApiModel):
    title: str
    category: str = Field(description="«Backend · Middle»")
    required_skills: list[str]
    optional_skills: list[str]
    salary_from: int
    salary_to: int
    work_format: str | None
    city: str | None
    industry: str | None
    team_description: str | None


class ExpertProgress(ApiModel):
    done: int = Field(description="Сколько пар разметил этот эксперт")
    total: int


class ExpertTask(ApiModel):
    progress: ExpertProgress
    pair_id: int | None = Field(description="null — все пары размечены")
    need: ExpertNeed | None
    candidate: CandidateCard | None = Field(description="Обезличенная карточка без score и объяснения")


class ExpertLabelRequest(ApiModel):
    label: int = Field(
        ge=0,
        le=3,
        description="0 — не подходит; 1 — слабо; 2 — подходит с оговорками; 3 — полностью подходит",
    )


class RankerQuality(ApiModel):
    name: str
    precision_at_5: float | None = Field(description="Доля релевантных (средняя оценка ≥ порога) в топ-5")
    needs: int = Field(description="Потребностей, у которых топ-5 размечен полностью")


class ExpertSummary(ApiModel):
    raters: int
    labels: int
    pairs_total: int
    pairs_labeled: int
    relevant_from: float
    rankers: list[RankerQuality]
    spearman: float | None = Field(description="Корреляция Спирмена score ITScout со средней оценкой")
    spearman_pairs: int
    agreement_pairs: int = Field(description="Пар, размеченных двумя и более экспертами")
    exact_agreement: float | None
    weighted_kappa: float | None = Field(description="Квадратично взвешенная κ согласия экспертов")


class AngoffProgress(ApiModel):
    done: int = Field(description="Сколько шаблонов набора оценил этот эксперт в раунде")
    total: int


class AngoffItemFeedback(ApiModel):
    raters: int = Field(description="Экспертов, полностью прошедших раунд 1")
    median: float = Field(description="Медиана оценок группы в раунде 1")
    low: float = Field(description="Минимальная оценка группы")
    high: float = Field(description="Максимальная оценка группы")


class AngoffTask(ApiModel):
    template_id: str
    topic_name: str
    kind: ItemKind
    instance: ExplainerInstance = Field(description="Пример экземпляра без ключа ответа")
    rating: float | None = Field(description="Оценка эксперта в этом раунде, null — ещё не оценён")
    round1_rating: float | None = Field(
        default=None, description="Раунд 2: собственная оценка эксперта в раунде 1"
    )
    group: AngoffItemFeedback | None = Field(
        default=None,
        description="Раунд 2: оценки группы в раунде 1; null, если раунд 1 прошли меньше feedback_min_raters",
    )


class AngoffHofsteeValues(ApiModel):
    min_cut: float = Field(ge=0, le=1, description="Минимальный допустимый порог: доля верных по набору")
    max_cut: float = Field(ge=0, le=1, description="Максимальный допустимый порог: доля верных по набору")
    min_fail: float = Field(ge=0, le=1, description="Минимальная допустимая доля не дотягивающих до грейда")
    max_fail: float = Field(ge=0, le=1, description="Максимальная допустимая доля не дотягивающих до грейда")

    @model_validator(mode="after")
    def _ordered(self) -> "AngoffHofsteeValues":
        if self.min_cut > self.max_cut or self.min_fail > self.max_fail:
            raise ValueError("Минимум не может быть больше максимума")
        return self


class AngoffHofsteeRequest(AngoffHofsteeValues):
    specialization: str = Field(max_length=32)
    grade: Grade


class AngoffTasks(ApiModel):
    specialization: str
    grade: Grade
    grade_name: str
    round: int = Field(description="1 — первичная оценка, 2 — пересмотр после данных о последствиях")
    rating_step: float = Field(description="Шаг шкалы оценки, доля")
    progress: AngoffProgress = Field(description="Прогресс в запрошенном раунде")
    round1_complete: bool = Field(description="Эксперт оценил весь набор в раунде 1 — открыт раунд 2")
    round2_started: bool = Field(description="У эксперта есть оценки раунда 2")
    hofstee: AngoffHofsteeValues | None = Field(description="Ответы эксперта для проверки Hofstee")
    hofstee_defaults: AngoffHofsteeValues = Field(description="Значения формы Hofstee по умолчанию")
    tasks: list[AngoffTask]


class AngoffRatingRequest(ApiModel):
    specialization: str = Field(max_length=32)
    grade: Grade
    template_id: str = Field(max_length=120)
    round: int = Field(default=1, ge=1, le=2, description="Раунд оценки; раунд 2 — после полного раунда 1")
    rating: float = Field(
        ge=0, le=1, description="Вероятность, что минимально компетентный кандидат грейда решит задание"
    )


class AngoffRoundStart(ApiModel):
    specialization: str = Field(max_length=32)
    grade: Grade


class AngoffBandShare(ApiModel):
    band: str = Field(description="below — ниже стажёра, иначе грейд")
    name: str
    current: float = Field(description="Доля кандидатов в полосе при действующих порогах")
    proposed: float = Field(description="Доля кандидатов в полосе при предложенных порогах")


class AngoffGroupFeedback(ApiModel):
    raters: int = Field(description="Экспертов, полностью прошедших раунд 1")
    median_cut: float
    min_cut: float
    max_cut: float
    sd: float | None = Field(description="Стандартное отклонение порогов; null при одном эксперте")


class AngoffImpact(ApiModel):
    specialization: str
    grade: Grade
    grade_name: str
    source: Literal["results", "synthetic"] = Field(
        description="results — последние результаты тестов; synthetic — синтетическая популяция, "
        "если результатов меньше impact.min_candidates"
    )
    candidates: int = Field(description="Размер популяции, по которой считаются доли")
    your_cut: float = Field(description="Порог эксперта по раунду 1 (θ)")
    your_fail_rate: float = Field(description="Доля кандидатов ниже порога эксперта")
    group: AngoffGroupFeedback | None = Field(
        description="Пороги группы в раунде 1; null, если раунд 1 прошли меньше feedback_min_raters"
    )
    current_cut: float
    current_fail_rate: float = Field(description="Доля кандидатов ниже действующего порога")
    proposed_cut: float = Field(description="Медиана группы, а при недостатке экспертов — порог эксперта")
    proposed_fail_rate: float
    bands: list[AngoffBandShare] = Field(
        description="Распределение по грейдам: действующие пороги против действующих с заменой этого порога"
    )


class AngoffRaterCut(ApiModel):
    rater: str = Field(description="Обезличенно: «Эксперт 1», «Эксперт 2», …")
    you: bool = Field(description="Это оценки текущего пользователя")
    cut: float = Field(description="θ, при котором ожидаемый балл по набору равен сумме оценок")
    expected_share: float = Field(description="Средняя оценка по набору: Σp / n")
    clamped: bool = Field(description="Порог упёрся в край шкалы θ")


class AngoffRoundSummary(ApiModel):
    round: int
    raters: int = Field(description="Экспертов, оценивших весь набор в этом раунде")
    incomplete_raters: int = Field(description="Экспертов, оценивших набор частично (в расчёт не входят)")
    rater_cuts: list[AngoffRaterCut]
    mean_cut: float = Field(description="Среднее порогов экспертов")
    median_cut: float
    sd: float | None = Field(description="Стандартное отклонение порогов экспертов; null при одном эксперте")
    se: float | None = Field(description="Стандартная ошибка среднего: SD / √k")


class AngoffHofsteeCheck(ApiModel):
    raters: int = Field(description="Экспертов, заполнивших окно Hofstee")
    box: AngoffHofsteeValues = Field(description="Окно Hofstee: средние границы экспертов")
    cut_share: float = Field(description="Порог Hofstee: доля верных по набору")
    cut_theta: float = Field(description="Порог Hofstee на шкале θ (через TCC набора)")
    fail_rate: float = Field(description="Доля не дотягивающих при пороге Hofstee")
    intersects: bool = Field(description="Кривая доли не дотягивающих пересекает диагональ окна внутри окна")
    angoff_share: float = Field(description="Рекомендуемый порог Angoff как доля верных по набору")
    angoff_fail_rate: float = Field(description="Доля не дотягивающих при пороге Angoff")
    in_box: bool = Field(description="Порог Angoff внутри окна Hofstee по обеим осям")


class AngoffGradeSummary(ApiModel):
    grade: Grade
    grade_name: str
    items: int = Field(description="Шаблонов в наборе")
    rounds: list[AngoffRoundSummary] = Field(description="Раунды, где хотя бы один эксперт оценил весь набор")
    recommended_round: int = Field(description="Раунд, по которому дана рекомендация: последний пройденный")
    recommended_cut: float = Field(description="Рекомендуемый порог: среднее порогов экспертов в этом раунде")
    se: float | None = Field(description="SE рекомендуемого порога")
    current_cut: float = Field(description="Действующий порог из content/blueprints.yaml")
    difference: float = Field(description="recommended_cut − current_cut")
    recommended_raters: int = Field(description="Рекомендуемое число экспертов (content/angoff.yaml)")
    hofstee: AngoffHofsteeCheck | None = Field(description="null — никто не заполнил окно Hofstee")
    impact_source: Literal["results", "synthetic"]
    impact_candidates: int


class AngoffSummary(ApiModel):
    specialization: str
    grades: list[AngoffGradeSummary] = Field(
        description="Только грейды, где хотя бы один эксперт оценил весь набор. Пороги не применяются сами"
    )
