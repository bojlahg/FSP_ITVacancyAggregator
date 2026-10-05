from pydantic import Field

from app.core.enums import Grade, ParserKind
from app.core.schemas import ApiModel
from app.modules.candidates.schemas import CandidateProfileUpdate


class ResumeParseResult(ApiModel):
    resume_id: int
    parser: ParserKind = Field(description="dict — словарь и регулярки; llm — с разбором Yandex AI Studio")
    prefill: CandidateProfileUpdate = Field(
        description=(
            "Предзаполнение формы: текущий профиль, дополненный данными резюме. Сохраняется только после "
            "подтверждения через PUT /candidates/me; навыки из резюме — только «заявлено»"
        )
    )
    from_resume: list[str] = Field(
        default_factory=list, description="Поля prefill, которые заполнены или дополнены из резюме"
    )
    suggested_grade: Grade | None = Field(
        default=None, description="Подсказка по стажу из резюме; грейд выбирает кандидат, а определяет тест"
    )
    unmapped_terms: list[str] = Field(description="Термины, которых нет в онтологии навыков")
    warnings: list[str] = Field(default_factory=list)
