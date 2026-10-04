from app.core.enums import Grade
from app.core.schemas import ApiModel


class SpecializationOut(ApiModel):
    slug: str
    name: str
    has_test: bool
    adjacent: list[str]


class GradeOut(ApiModel):
    slug: Grade
    name: str
    order: int


class SkillOut(ApiModel):
    id: str
    name: str
    family: str
    parent: str | None = None


class IndustryOut(ApiModel):
    slug: str
    name: str


class SoftSkillOut(ApiModel):
    slug: str
    name: str
