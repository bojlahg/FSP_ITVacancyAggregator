from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import CurrentEmployer, DbSession
from app.core.enums import Grade, WorkFormat
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.matching.schemas import CandidateCard, CategoryCatalogItem, TalentSearchOut

router = APIRouter(prefix="/talent", tags=["employer: talent pool"])


@router.get(
    "/categories",
    response_model=list[CategoryCatalogItem],
    summary="Каталог категорий «специализация × грейд» со счётчиками",
    responses=error_responses(401, 403),
)
async def list_categories(user: CurrentEmployer, db: DbSession) -> list[CategoryCatalogItem]:
    raise NotImplementedApiError()


@router.get(
    "/search",
    response_model=TalentSearchOut,
    summary="Поиск по всей базе с фильтрами; сортировка внутри категории по силе профиля",
    responses=error_responses(401, 403, 422),
)
async def search_talent(
    user: CurrentEmployer,
    db: DbSession,
    specialization: str | None = Query(default=None),
    grade: Grade | None = Query(default=None),
    skills: list[str] = Query(default=[], description="id навыков"),
    verified_only: bool = Query(default=False),
    has_fsp: bool | None = Query(default=None),
    fsp_discipline: str | None = Query(default=None),
    fsp_min_rank: str | None = Query(default=None),
    salary_max: int | None = Query(default=None),
    work_format: WorkFormat | None = Query(default=None),
    city: str | None = Query(default=None),
    fresh_days: int | None = Query(default=None),
    sort: Literal["vps", "percentile", "fresh"] = Query(default="vps"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
) -> TalentSearchOut:
    raise NotImplementedApiError()


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateCard,
    summary="Карточка кандидата: обезличенная до раскрытия контактов",
    responses=error_responses(401, 403, 404),
)
async def get_candidate_card(
    candidate_id: int,
    user: CurrentEmployer,
    db: DbSession,
    need_id: int | None = Query(default=None, description="Добавить объяснение совпадения с потребностью"),
) -> CandidateCard:
    raise NotImplementedApiError()


@router.get(
    "/candidates/{candidate_id}/profile.pdf",
    response_class=Response,
    summary="PDF-профиль кандидата (полный — только после раскрытия контактов)",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF-файл"},
        **error_responses(401, 403, 404),
    },
)
async def get_candidate_pdf(candidate_id: int, user: CurrentEmployer, db: DbSession) -> Response:
    raise NotImplementedApiError()
