from pydantic import Field

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
    done: int = Field(description="Сколько шаблонов набора оценил этот эксперт")
    total: int


class AngoffTask(ApiModel):
    template_id: str
    topic_name: str
    kind: ItemKind
    instance: ExplainerInstance = Field(description="Пример экземпляра без ключа ответа")
    rating: float | None = Field(description="Текущая оценка эксперта, null — ещё не оценён")


class AngoffTasks(ApiModel):
    specialization: str
    grade: Grade
    grade_name: str
    rating_step: float = Field(description="Шаг шкалы оценки, доля")
    progress: AngoffProgress
    tasks: list[AngoffTask]


class AngoffRatingRequest(ApiModel):
    specialization: str = Field(max_length=32)
    grade: Grade
    template_id: str = Field(max_length=120)
    rating: float = Field(
        ge=0, le=1, description="Вероятность, что минимально компетентный кандидат грейда решит задание"
    )


class AngoffRaterCut(ApiModel):
    rater: str = Field(description="Обезличенно: «Эксперт 1», «Эксперт 2», …")
    you: bool = Field(description="Это оценки текущего пользователя")
    cut: float = Field(description="θ, при котором ожидаемый балл по набору равен сумме оценок")
    expected_share: float = Field(description="Средняя оценка по набору: Σp / n")
    clamped: bool = Field(description="Порог упёрся в край шкалы θ")


class AngoffGradeSummary(ApiModel):
    grade: Grade
    grade_name: str
    items: int = Field(description="Шаблонов в наборе")
    raters: int = Field(description="Экспертов, оценивших весь набор")
    incomplete_raters: int = Field(description="Экспертов, оценивших набор частично (в расчёт не входят)")
    rater_cuts: list[AngoffRaterCut]
    mean_cut: float = Field(description="Рекомендуемый порог: среднее порогов экспертов")
    sd: float | None = Field(description="Стандартное отклонение порогов экспертов; null при одном эксперте")
    se: float | None = Field(description="Стандартная ошибка среднего: SD / √k")
    current_cut: float = Field(description="Действующий порог из content/blueprints.yaml")
    difference: float = Field(description="mean_cut − current_cut")


class AngoffSummary(ApiModel):
    specialization: str
    grades: list[AngoffGradeSummary] = Field(
        description="Только грейды, где хотя бы один эксперт оценил весь набор. Пороги не применяются сами"
    )
