from typing import Any, Literal

from pydantic import Field

from app.core.enums import Grade
from app.core.schemas import ApiModel


class SurveyOption(ApiModel):
    id: str
    label: str


class SurveyQuestion(ApiModel):
    id: str
    text: str
    kind: Literal["single", "multi", "skills", "number", "salary_range", "text"]
    required: bool = True
    options: list[SurveyOption] = Field(default_factory=list)


class SurveySubmit(ApiModel):
    answers: dict[str, Any] = Field(description="id вопроса → ответ (id варианта, список id, число, текст)")


class SpecializationScore(ApiModel):
    specialization: str
    name: str
    score: float = Field(ge=0, le=1)


class SurveyResult(ApiModel):
    response_id: int
    recommended: list[SpecializationScore] = Field(
        description="Топ специализаций по ответам — кандидат подтверждает"
    )
    suggested_grade: Grade = Field(description="Подсказка по стажу; грейд выбирает сам кандидат")
    stack_modules: list[str] = Field(description="Стек-модули теста по выбранному стеку")


class SpecializationConfirm(ApiModel):
    specialization: str
