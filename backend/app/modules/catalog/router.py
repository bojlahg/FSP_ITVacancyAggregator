from fastapi import APIRouter, Query

from app.core.errors import NotImplementedApiError
from app.modules.catalog.schemas import GradeOut, IndustryOut, SkillOut, SoftSkillOut, SpecializationOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/specializations", response_model=list[SpecializationOut], summary="Справочник специализаций")
async def list_specializations() -> list[SpecializationOut]:
    raise NotImplementedApiError()


@router.get("/grades", response_model=list[GradeOut], summary="Справочник грейдов")
async def list_grades() -> list[GradeOut]:
    raise NotImplementedApiError()


@router.get("/skills", response_model=list[SkillOut], summary="Онтология навыков с поиском по алиасам")
async def list_skills(
    q: str | None = Query(default=None, description="Поиск по названию и алиасам"),
    family: str | None = Query(default=None),
) -> list[SkillOut]:
    raise NotImplementedApiError()


@router.get("/industries", response_model=list[IndustryOut], summary="Справочник отраслей")
async def list_industries() -> list[IndustryOut]:
    raise NotImplementedApiError()


@router.get("/soft-skills", response_model=list[SoftSkillOut], summary="Справочник софт-скиллов")
async def list_soft_skills() -> list[SoftSkillOut]:
    raise NotImplementedApiError()
