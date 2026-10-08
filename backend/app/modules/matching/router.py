from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.enums import Grade, WorkFormat
from app.core.errors import error_responses
from app.core.schemas import MAX_RUBLES
from app.modules.matching import service
from app.modules.matching.schemas import (
    CandidateCard,
    CandidateMarketOut,
    CategoryCatalogItem,
    JsonResume,
    RecommendationsOut,
    SalaryCoverage,
    TalentSearchOut,
)
from app.modules.matching.service import Filters, SearchFilters

router = APIRouter(prefix="/talent", tags=["employer: talent pool"])


@router.get(
    "/categories",
    response_model=list[CategoryCatalogItem],
    summary="Каталог категорий «специализация × грейд» со счётчиками",
    responses=error_responses(401, 403),
)
async def list_categories(user: CurrentEmployer, db: DbSession) -> list[CategoryCatalogItem]:
    return await service.categories_catalog(db, user.id)


@router.get(
    "/cities",
    response_model=list[str],
    summary="Города кандидатов в выдаче — справочник для фильтра; самые частые первыми",
    responses=error_responses(401, 403),
)
async def list_cities(user: CurrentEmployer, db: DbSession) -> list[str]:
    return await service.cities(db, user.id)


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
    salary_max: int | None = Query(default=None, gt=0, le=MAX_RUBLES),
    work_format: WorkFormat | None = Query(default=None),
    city: str | None = Query(default=None),
    fresh_days: int | None = Query(default=None),
    sort: Literal["vps", "percentile", "fresh"] = Query(default="vps"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
) -> TalentSearchOut:
    filters = SearchFilters(
        specialization=specialization,
        grade=grade.value if grade else None,
        skills=skills,
        verified_only=verified_only,
        has_fsp=has_fsp,
        fsp_discipline=fsp_discipline,
        fsp_min_rank=fsp_min_rank,
        salary_max=salary_max,
        work_format=work_format.value if work_format else None,
        city=city,
        fresh_days=fresh_days,
        sort=sort,
        offset=offset,
        limit=limit,
    )
    return await service.search(db, user.id, filters)


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
    return await service.candidate_card(db, user.id, candidate_id, need_id)


@router.get(
    "/candidates/{candidate_id}/resume.json",
    response_model=JsonResume,
    response_model_by_alias=True,
    summary="Кандидат в формате JSON Resume для ATS (контакты — только после раскрытия)",
    description=(
        "Стандартная схема JSON Resume и расширение `x-itscout`: категория по тесту, перцентиль, "
        "результаты по темам, разряды ФСП и совпадение с потребностью. Правила видимости — как у карточки."
    ),
    responses=error_responses(401, 403, 404),
)
async def get_candidate_json_resume(
    candidate_id: int,
    user: CurrentEmployer,
    db: DbSession,
    need_id: int | None = Query(default=None, description="Добавить совпадение с потребностью"),
) -> JsonResume:
    return await service.json_resume(db, user.id, candidate_id, need_id)


@router.get(
    "/candidates/{candidate_id}/profile.pdf",
    response_class=Response,
    summary="PDF-профиль кандидата (полный — только после раскрытия контактов)",
    description="Обезличенная версия до раскрытия контактов; полная — при записи в contact_unlocks.",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF-файл"},
        **error_responses(401, 403, 404),
    },
)
async def get_candidate_pdf(candidate_id: int, user: CurrentEmployer, db: DbSession) -> Response:
    from app.modules.resume import service as resume_service
    from app.modules.resume.router import pdf_response

    return pdf_response(*await resume_service.employer_candidate_pdf(db, user.id, candidate_id))


# Подборка по потребности живёт в matching: здесь весь расчёт score и объяснений (§8.3–8.4)
need_router = APIRouter(prefix="/needs", tags=["employer: needs & matching"])

OWNED = error_responses(401, 403, 404)


@need_router.get(
    "/{need_id}/recommendations",
    response_model=RecommendationsOut,
    summary="Подборка: рекомендованные категории и кандидаты с объяснением",
    responses=OWNED,
)
async def get_recommendations(
    need_id: int,
    user: CurrentEmployer,
    db: DbSession,
    grade: Grade | None = Query(default=None, description="Ограничить грейдом"),
    has_fsp: bool | None = Query(default=None),
    verified_only: bool = Query(
        default=False, description="Хотя бы один обязательный навык потребности проверен тестом"
    ),
    salary_max: int | None = Query(default=None, gt=0, le=MAX_RUBLES),
    work_format: WorkFormat | None = Query(default=None),
    city: str | None = Query(default=None),
    fresh_days: int | None = Query(default=None),
    apply_hard_filters: bool = Query(default=True),
    group_by: Literal["category", "none"] = Query(default="category"),
    limit: int | None = Query(default=None, ge=1, le=200, description="По умолчанию — из matching.yaml"),
) -> RecommendationsOut:
    filters = Filters(
        grade=grade.value if grade else None,
        has_fsp=has_fsp,
        verified_only=verified_only,
        salary_max=salary_max,
        work_format=work_format.value if work_format else None,
        city=city,
        fresh_days=fresh_days,
        apply_hard_filters=apply_hard_filters,
        group_by=group_by,
        limit=limit,
    )
    return await service.recommendations(db, user.id, need_id, filters)


@need_router.get(
    "/{need_id}/salary-coverage",
    response_model=SalaryCoverage,
    summary="Какую долю кандидатов категории покрывает вилка",
    responses=OWNED,
)
async def get_salary_coverage(need_id: int, user: CurrentEmployer, db: DbSession) -> SalaryCoverage:
    return await service.salary_coverage(db, user.id, need_id)


# Кандидату — только агрегаты рынка его категории; навыки считаются тем же skills-компонентом, что и подбор
candidate_router = APIRouter(prefix="/candidates/me", tags=["candidate: market"])


@candidate_router.get(
    "/market",
    response_model=CandidateMarketOut,
    summary="Рынок моей категории: потребности, вилки, востребованные навыки и что поможет",
    description=(
        "Только агрегаты по действующим потребностям своей и соседних категорий, без названий компаний и "
        "потребностей. Вилки, навыки и подсказки скрываются (`suppressed=true`), если потребностей или "
        "компаний в выборке меньше порога из `content/matching.yaml` (`insights`)."
    ),
    responses=error_responses(401, 403),
)
async def get_my_market(user: CurrentCandidate, db: DbSession) -> CandidateMarketOut:
    return await service.market_for_candidate(db, user.id)
