from fastapi import APIRouter, Query

from app.modules.catalog import service
from app.modules.catalog.schemas import (
    GradeOut,
    IndustryOut,
    SkillOut,
    SoftSkillOut,
    SpecializationOut,
    TeamRoleOut,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/specializations", response_model=list[SpecializationOut], summary="Справочник специализаций")
async def list_specializations() -> list[SpecializationOut]:
    return [
        SpecializationOut.model_validate(item.model_dump()) for item in service.get_catalog().specializations
    ]


@router.get("/grades", response_model=list[GradeOut], summary="Справочник грейдов")
async def list_grades() -> list[GradeOut]:
    grades = sorted(service.get_catalog().grades, key=lambda grade: grade.order)
    return [GradeOut.model_validate(grade.model_dump()) for grade in grades]


@router.get("/skills", response_model=list[SkillOut], summary="Онтология навыков с поиском по алиасам")
async def list_skills(
    q: str | None = Query(default=None, description="Поиск по названию и алиасам"),
    family: str | None = Query(default=None),
) -> list[SkillOut]:
    return [SkillOut.model_validate(skill.model_dump()) for skill in service.search_skills(q, family)]


@router.get("/industries", response_model=list[IndustryOut], summary="Справочник отраслей")
async def list_industries() -> list[IndustryOut]:
    return [IndustryOut.model_validate(item.model_dump()) for item in service.get_catalog().industries]


@router.get("/soft-skills", response_model=list[SoftSkillOut], summary="Справочник софт-скиллов")
async def list_soft_skills() -> list[SoftSkillOut]:
    return [SoftSkillOut.model_validate(item.model_dump()) for item in service.get_catalog().soft_skills]


@router.get("/team-roles", response_model=list[TeamRoleOut], summary="Роли в команде")
async def list_team_roles() -> list[TeamRoleOut]:
    return [TeamRoleOut.model_validate(item.model_dump()) for item in service.get_catalog().team_roles]
