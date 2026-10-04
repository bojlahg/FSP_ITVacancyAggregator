from pydantic import Field

from app.core.enums import ParserKind
from app.core.schemas import ApiModel
from app.modules.candidates.schemas import CandidateProfileUpdate


class ResumeParseResult(ApiModel):
    resume_id: int
    parser: ParserKind = Field(description="dict — словарь и регулярки; llm — с разбором Yandex AI Studio")
    prefill: CandidateProfileUpdate = Field(
        description="Предзаполнение формы — сохраняется только после подтверждения"
    )
    suggested_grade: str | None = None
    unmapped_terms: list[str] = Field(description="Термины, которых нет в онтологии навыков")
    warnings: list[str] = Field(default_factory=list)
