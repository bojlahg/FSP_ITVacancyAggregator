"""Модель движка тестирования (§10). Чистый Python без БД и FastAPI: его используют backend и validation/."""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ItemKind = Literal["single_choice", "multi_choice", "numeric", "ordering", "code_output", "open_approach"]
CHOICE_KINDS = {"single_choice", "multi_choice", "code_output"}


class IrtParams(BaseModel):
    a: float = Field(ge=0.3, le=3.0, description="Дискриминация")
    b: float = Field(ge=-3.5, le=3.5, description="Сложность на шкале специализации, логиты")


class ParamSpec(BaseModel):
    """Случайный параметр шаблона: выбор из списка или целое из диапазона."""

    model_config = ConfigDict(populate_by_name=True)

    choice: list[Any] | None = None
    int_range: tuple[int, int] | None = Field(default=None, alias="int")
    step: int = 1

    @model_validator(mode="after")
    def one_kind(self) -> "ParamSpec":
        if (self.choice is None) == (self.int_range is None):
            raise ValueError("параметр задаётся ровно одним из: choice | int")
        if self.choice is not None and not self.choice:
            raise ValueError("пустой choice")
        return self


class OptionPools(BaseModel):
    correct: list[str] = Field(min_length=1)
    wrong: list[str] = Field(default_factory=list)


class NumericAnswer(BaseModel):
    expr: str = Field(description="Арифметика над параметрами: {{n}} * 2 + 1")
    tolerance: float = 0.0


class Template(BaseModel):
    id: str
    version: int = 1
    specializations: list[str] = Field(min_length=1)
    topic: str
    stack_module: str | None = Field(default=None, description="Для topic=stack: python, react, …")
    skills: list[str] = Field(default_factory=list)
    kind: ItemKind
    irt: IrtParams
    # showcase — витрина для публичной страницы «Как работает тест»: в тесты, задания и предпросмотр не входит
    status: Literal["pilot", "active", "retired", "showcase"] = "active"
    time_limit_sec: int = Field(default=90, ge=20, le=900)
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    stem: str | None = None
    stem_variants: list[str] = Field(default_factory=list)
    code: str | None = None
    code_language: str | None = None
    options: OptionPools | None = None
    n_options: int = Field(default=4, ge=2, le=6)
    order_items: list[str] = Field(default_factory=list, description="ordering: элементы в верном порядке")
    answer: NumericAnswer | None = None
    rubric: list[str] = Field(default_factory=list, description="open_approach: бинарные критерии")
    max_length: int = 1500
    generator: str | None = Field(
        default=None, description="Имя Python-генератора вместо декларативной формы"
    )

    @model_validator(mode="after")
    def check_shape(self) -> "Template":
        if self.generator:
            return self
        if not (self.stem or self.stem_variants):
            raise ValueError(f"{self.id}: нужен stem или stem_variants")
        if self.kind in CHOICE_KINDS and self.options is None:
            raise ValueError(f"{self.id}: для {self.kind} нужны options")
        if self.kind == "numeric" and self.answer is None:
            raise ValueError(f"{self.id}: для numeric нужен answer.expr")
        if self.kind == "ordering" and len(self.order_items) < 3:
            raise ValueError(f"{self.id}: для ordering нужно ≥3 order_items")
        if self.kind == "open_approach" and len(self.rubric) < 3:
            raise ValueError(f"{self.id}: для open_approach нужно ≥3 критерия rubric")
        if self.topic == "stack" and not self.stack_module:
            raise ValueError(f"{self.id}: topic=stack требует stack_module")
        return self

    @property
    def guessing(self) -> float:
        """c в 3PL: вероятность угадать (§10.1)."""
        if self.kind in {"single_choice", "code_output"}:
            return 1.0 / self.n_options
        return 0.0


@dataclass(frozen=True)
class Option:
    id: str
    text: str


@dataclass(frozen=True)
class Instance:
    """Экземпляр задания для конкретной попытки. key уходит только в БД, никогда во фронт."""

    template_id: str
    version: int
    kind: str
    topic: str
    skills: tuple[str, ...]
    stem: str
    code: str | None
    code_language: str | None
    options: tuple[Option, ...]
    time_limit_sec: int
    max_length: int | None
    key: dict[str, Any] = field(default_factory=dict)

    def public_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "topic": self.topic,
            "stem": self.stem,
            "code": self.code,
            "code_language": self.code_language,
            "options": [{"id": option.id, "text": option.text} for option in self.options],
            "time_limit_sec": self.time_limit_sec,
            "max_length": self.max_length,
        }


@dataclass(frozen=True)
class Generated:
    """Что возвращает Python-генератор: текст и верные/неверные варианты либо иной ключ."""

    stem: str
    code: str | None = None
    code_language: str | None = None
    correct: tuple[str, ...] = ()
    wrong: tuple[str, ...] = ()
    order_items: tuple[str, ...] = ()
    number: float | None = None
    tolerance: float = 0.0
