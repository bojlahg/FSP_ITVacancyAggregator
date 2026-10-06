from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.modules.testing import preview_service
from app.modules.testing.schemas import VacancyExample, VacancyTestPreview, VacancyTestPreviewRequest

router = APIRouter(prefix="/vacancy-tests", tags=["employer: vacancy test preview"])


@router.get(
    "/examples",
    response_model=list[VacancyExample],
    summary="Демо-набор описаний вакансий для проверки под вакансию",
    responses=error_responses(401, 403),
)
async def vacancy_examples(user: CurrentEmployer) -> list[VacancyExample]:
    return preview_service.examples()


@router.post(
    "/preview",
    response_model=VacancyTestPreview,
    summary="Как система соберёт тест под вакансию: blueprint, примеры заданий, черновики LLM",
    description=(
        "Источник — текст вакансии (raw_text) или своя потребность (need_id). Повтор с другим "
        "regenerate_seed даёт другие экземпляры тех же шаблонов той же сложности. Ключи ответов "
        "не передаются. 422 specialization_not_detected / no_test_for_specialization — "
        "по тексту нельзя собрать тест. 429 — превышен суточный лимит предпросмотров "
        "(VACANCY_PREVIEW_PER_DAY)."
    ),
    responses=error_responses(401, 403, 404, 422, 429),
)
async def preview_vacancy_test(
    body: VacancyTestPreviewRequest, user: CurrentEmployer, db: DbSession
) -> VacancyTestPreview:
    return await preview_service.preview(db, user.id, body)
