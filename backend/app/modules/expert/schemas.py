from pydantic import Field

from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateCard


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
