from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.core.enums import ChallengeAttemptStatus, ChallengeStatus, Grade
from app.core.schemas import ApiModel
from app.modules.matching.schemas import CandidateBrief

QuestionKind = Literal["single_choice", "multi_choice", "numeric", "open_approach"]


class ChallengeOption(ApiModel):
    text: str = Field(min_length=1, max_length=300)
    correct: bool = False


class ChallengeQuestion(ApiModel):
    """Вопрос работодателя. Ключ (correct, number) виден только автору челленджа."""

    kind: QuestionKind
    text: str = Field(min_length=1, max_length=2000)
    code: str | None = Field(default=None, max_length=4000, description="Фрагмент кода к вопросу")
    options: list[ChallengeOption] = Field(default_factory=list, description="Для вопросов с выбором")
    number: float | None = Field(default=None, description="Для numeric — верный ответ")
    tolerance: float = Field(default=0.0, ge=0, description="Для numeric — допустимое отклонение")
    rubric: list[str] = Field(
        default_factory=list, description="Для open_approach — критерии, по которым вы прочитаете ответ"
    )

    @model_validator(mode="after")
    def check_kind(self) -> "ChallengeQuestion":
        correct = sum(option.correct for option in self.options)
        if self.kind in {"single_choice", "multi_choice"}:
            if len(self.options) < 2:
                raise ValueError("Нужно хотя бы два варианта ответа")
            if self.kind == "single_choice" and correct != 1:
                raise ValueError("В вопросе с одним ответом отметьте ровно один верный вариант")
            if self.kind == "multi_choice" and correct < 1:
                raise ValueError("Отметьте хотя бы один верный вариант")
            if len({option.text.strip().lower() for option in self.options}) != len(self.options):
                raise ValueError("Варианты ответа не должны повторяться")
        if self.kind == "numeric" and self.number is None:
            raise ValueError("Укажите верный числовой ответ")
        if any(not item.strip() or len(item) > 200 for item in self.rubric):
            raise ValueError("Критерий — непустая строка до 200 символов")
        return self


class ChallengeCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000, description="Кого ищете и что проверяет челлендж")
    specialization: str
    grade: Grade | None = Field(default=None, description="null — для всех грейдов специализации")
    skills: list[str] = Field(default_factory=list, description="Навыки из справочника")
    time_per_question_sec: int | None = Field(
        default=None, description="Лимит на вопрос в секундах, считает сервер; null — по умолчанию"
    )
    questions_per_attempt: int | None = Field(
        default=None, description="Сколько вопросов показать кандидату из общего списка; null — все"
    )
    questions: list[ChallengeQuestion]


class ChallengeStats(ApiModel):
    started: int
    completed: int
    average_score: float | None = Field(description="Средняя доля верных автопроверяемых ответов")


class ChallengeOut(ChallengeCreate):
    """Челлендж глазами автора — с ключами."""

    id: int
    status: ChallengeStatus
    stats: ChallengeStats
    created_at: datetime
    published_at: datetime | None
    closed_at: datetime | None


class ChallengeCard(ApiModel):
    """Челлендж глазами кандидата — без вопросов и ключей."""

    id: int
    company_name: str
    title: str
    description: str
    specialization: str
    grade: Grade | None
    skills: list[str] = Field(description="Названия навыков")
    questions: int = Field(description="Сколько вопросов будет в попытке")
    time_per_question_sec: int
    published_at: datetime | None
    attempt_id: int | None = Field(description="Ваша попытка, если начата")
    attempt_status: ChallengeAttemptStatus | None
    score: float | None = Field(description="Ваша доля верных автопроверяемых ответов после завершения")


class ChallengeAttemptResult(ApiModel):
    attempt_id: int
    challenge_id: int
    title: str
    company_name: str
    status: ChallengeAttemptStatus
    answered: int
    total: int
    correct: int
    scored_total: int = Field(description="Вопросов с автопроверкой")
    score: float | None
    started_at: datetime
    finished_at: datetime | None


class OpenAnswer(ApiModel):
    question: str
    answer: str | None = Field(description="Контакты в тексте скрыты до раскрытия контактов")
    rubric: list[str]


class ChallengeSolver(ApiModel):
    attempt_id: int
    candidate: CandidateBrief
    correct: int
    scored_total: int
    score: float | None
    finished_at: datetime | None
    open_answers: list[OpenAnswer]
