from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.config import get_settings
from app.core.enums import Grade
from app.core.errors import error_responses
from app.modules.testing import explainer_service
from app.modules.testing.schemas import (
    ExplainerDiversity,
    ExplainerInformation,
    ExplainerInstances,
    ExplainerOverview,
    ExplainerTemplate,
)

router = APIRouter(prefix="/explainer", tags=["public: test explainer"])
# Симуляция и рендер — CPU: синхронные обработчики FastAPI выполняет в пуле потоков, не блокируя цикл событий

_settings = get_settings()
MAX_SEED = 2_000_000_000

TemplateId = Annotated[str, Path(max_length=120, description="id шаблона, например be.db.where_vs_having")]


@router.get(
    "/overview",
    response_model=ExplainerOverview,
    summary="Шкала грейдов, специализации с тестом и параметры MST",
    description="Публичный метод без входа: данные для страницы «Как работает тест».",
)
async def explainer_overview() -> ExplainerOverview:
    return explainer_service.overview()


@router.get(
    "/specializations/{specialization}/templates",
    response_model=list[ExplainerTemplate],
    summary="Показательные шаблоны специализации с параметрами IRT (без ключей; в тесты они не входят)",
    description="404 specialization_not_found — специализации нет или для неё нет теста.",
    responses=error_responses(404),
)
async def explainer_templates(specialization: str) -> list[ExplainerTemplate]:
    return explainer_service.templates(specialization)


@router.get(
    "/templates/{template_id}/instances",
    response_model=ExplainerInstances,
    summary="Экземпляры шаблона для заданных seed: одна идея и сложность, разные числа и код",
    description=(
        f"Не больше {_settings.explainer_max_seeds} seed за запрос, повторы отбрасываются. "
        "Ключи ответов не передаются. 404 template_not_found — шаблона нет или он не активен."
    ),
    responses=error_responses(404, 422),
)
async def explainer_instances(
    template_id: TemplateId,
    seeds: Annotated[
        list[Annotated[int, Query(ge=0, le=MAX_SEED)]],
        Query(min_length=1, max_length=_settings.explainer_max_seeds, description="seed экземпляров"),
    ],
) -> ExplainerInstances:
    return explainer_service.instances(template_id, seeds)


@router.get(
    "/templates/{template_id}/diversity",
    response_model=ExplainerDiversity,
    summary="Разнообразие экземпляров шаблона и польза от утечки",
    description=(
        "Рендерит sample экземпляров и считает, сколько из них различны, вероятность совпадения "
        "у двух кандидатов и долю, совпавшую с «слитыми» экземплярами. 404 template_not_found."
    ),
    responses=error_responses(404, 422),
)
def explainer_diversity(
    template_id: TemplateId,
    sample: Annotated[int, Query(ge=2, le=_settings.explainer_max_sample)] = _settings.explainer_max_sample,
) -> ExplainerDiversity:
    return explainer_service.diversity(template_id, sample)


@router.get(
    "/specializations/{specialization}/information",
    response_model=ExplainerInformation,
    summary="Информационная функция MST-теста на грейд по симуляции движка",
    description=(
        "Три симулированных кандидата (слабее порога, у порога, сильнее) проходят тест настоящим "
        "Planner'ом; кривые — средняя информация Фишера по реальным параметрам банка (a, b, c). "
        "404 specialization_not_found."
    ),
    responses=error_responses(404, 422),
)
def explainer_information(
    specialization: str, grade: Annotated[Grade, Query(description="Грейд, на который идёт тест")]
) -> ExplainerInformation:
    return explainer_service.information_profile(specialization, grade)
