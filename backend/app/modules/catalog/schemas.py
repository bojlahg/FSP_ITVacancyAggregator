from app.core.enums import Grade
from app.core.schemas import ApiModel


class SpecializationOut(ApiModel):
    slug: str
    name: str
    has_test: bool
    adjacent: list[str]
    description: str
    stack_modules: list[str]


class GradeOut(ApiModel):
    slug: Grade
    name: str
    order: int
    experience_hint: str


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


class TeamRoleOut(ApiModel):
    slug: str
    name: str
