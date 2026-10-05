from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.errors import register_error_handlers, use_unified_validation_schema
from app.core.schemas import ApiModel
from app.modules.admin.router import router as admin_router
from app.modules.applications import router as applications
from app.modules.auth.router import me_router
from app.modules.auth.router import router as auth_router
from app.modules.candidates.router import router as candidates_router
from app.modules.catalog.router import router as catalog_router
from app.modules.catalog.service import get_catalog
from app.modules.categories.router import router as categories_router
from app.modules.employers.router import router as employers_router
from app.modules.fsp.router import router as fsp_router
from app.modules.invitations import router as invitations
from app.modules.matching.router import need_router as matching_need_router
from app.modules.matching.router import router as matching_router
from app.modules.needs.router import router as needs_router
from app.modules.resume.router import router as resume_router
from app.modules.survey.router import router as survey_router
from app.modules.tasks import router as tasks
from app.modules.testing.preview_router import router as vacancy_test_router
from app.modules.testing.router import router as testing_router

API_PREFIX = "/api/v1"

TAGS = [
    {"name": "service", "description": "Служебные методы"},
    {"name": "auth", "description": "Регистрация, вход, токены"},
    {"name": "catalog", "description": "Справочники: специализации, грейды, навыки, отрасли"},
    {"name": "candidate: profile", "description": "Профиль, резюме, приватность, согласия"},
    {"name": "candidate: onboarding", "description": "Опрос по отрасли и специализации"},
    {"name": "candidate: testing", "description": "Тест на грейд и категория"},
    {"name": "candidate: fsp", "description": "Привязка ФСП ID и достижения"},
    {"name": "candidate: invitations", "description": "Входящие приглашения"},
    {"name": "candidate: vacancies", "description": "Вакансии и отклики"},
    {"name": "candidate: tasks", "description": "Регулярные задания"},
    {"name": "employer: company", "description": "Профиль компании"},
    {"name": "employer: needs & matching", "description": "Потребности, подборка, шорт-лист, вакансии"},
    {"name": "employer: talent pool", "description": "Каталог категорий, поиск по базе, карточка кандидата"},
    {"name": "employer: invitations", "description": "Приглашения кандидатам и статистика отказов"},
    {"name": "employer: vacancies", "description": "Отклики на вакансии"},
    {"name": "employer: vacancy test preview", "description": "Как собирается тест под вакансию"},
    {"name": "employer: tasks", "description": "Короткие задания для кандидатов"},
]


class HealthOut(ApiModel):
    status: str
    db: bool
    version: str


def create_app() -> FastAPI:
    settings = get_settings()
    get_catalog()  # битые справочники должны ронять старт, а не первый запрос
    app = FastAPI(
        title="ITScout API",
        version="0.1.0",
        description=(
            "Платформа ИТ-подбора с обратной механикой и верифицированным профилем ФСП. "
            "Ошибки возвращаются в едином формате `{error: {code, message, details}}`."
        ),
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_tags=TAGS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health", response_model=HealthOut, tags=["service"], summary="Проверка живости и доступа к БД")
    async def health() -> HealthOut:
        db_ok = True
        try:
            async with SessionFactory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return HealthOut(status="ok" if db_ok else "degraded", db=db_ok, version=app.version)

    for router in (
        auth_router,
        me_router,
        catalog_router,
        candidates_router,
        resume_router,
        survey_router,
        testing_router,
        categories_router,
        fsp_router,
        invitations.candidate_router,
        applications.candidate_router,
        tasks.candidate_router,
        employers_router,
        needs_router,
        matching_need_router,
        matching_router,
        invitations.employer_router,
        applications.employer_router,
        vacancy_test_router,
        tasks.employer_router,
        admin_router,
    ):
        api.include_router(router)

    app.include_router(api)

    def openapi() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = use_unified_validation_schema(FastAPI.openapi(app))
        return app.openapi_schema

    app.openapi = openapi
    return app


app = create_app()
