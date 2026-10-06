from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import Grade


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageResponse(ApiModel):
    message: str


# Суммы хранятся в колонках Integer: большее значение БД не примет (500 вместо понятной ошибки)
MAX_RUBLES = 2_147_483_647


class SalaryRange(ApiModel):
    """Вилка в рублях «от–до» — обязательна в потребности, вакансии и приглашении (ТЗ §2.2)."""

    salary_from: int = Field(gt=0, le=MAX_RUBLES, description="Нижняя граница, ₽")
    salary_to: int = Field(gt=0, le=MAX_RUBLES, description="Верхняя граница, ₽")

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.salary_from > self.salary_to:
            raise ValueError("salary_from не может быть больше salary_to")
        return self


class ExplanationLine(ApiModel):
    kind: Literal["positive", "warning", "neutral"]
    source: Literal["category", "test", "skills", "fsp", "freshness", "conditions", "profile"]
    text: str


class Explanation(ApiModel):
    """Объяснение собирается кодом из тех же компонентов, что и score (§8.4)."""

    lines: list[ExplanationLine]


class CategoryRef(ApiModel):
    specialization: str = Field(description="slug специализации, например backend")
    grade: Grade
    label: str = Field(description="Например «Backend · Middle»")


class FspBadge(ApiModel):
    has_fsp: bool
    max_rank: str | None = Field(default=None, description="III | II | I | КМС | МС")
    achievements_count: int = 0
