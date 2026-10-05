from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.core.schemas import MessageResponse
from app.modules.needs import service
from app.modules.needs.parser import parse_need_text
from app.modules.needs.schemas import (
    NeedCreate,
    NeedOut,
    NeedParseRequest,
    NeedParseResult,
    NeedUpdate,
    ShortlistNote,
)

router = APIRouter(prefix="/needs", tags=["employer: needs & matching"])

OWNED = error_responses(401, 403, 404)
# 409 — правка не последней версии потребности
LATEST_OWNED = error_responses(401, 403, 404, 409)


@router.get(
    "",
    response_model=list[NeedOut],
    summary="Мои потребности и вакансии (последние версии, новые сверху)",
    responses=error_responses(401, 403),
)
async def list_needs(user: CurrentEmployer, db: DbSession) -> list[NeedOut]:
    return await service.list_needs(db, user.id)


@router.post(
    "/parse",
    response_model=NeedParseResult,
    summary="Разобрать текст потребности: словарь, затем LLM; результат — редактируемая форма",
    responses=error_responses(401, 403, 422),
)
async def parse_need(body: NeedParseRequest, user: CurrentEmployer) -> NeedParseResult:
    return await parse_need_text(body.raw_text, user_id=user.id)


@router.post(
    "",
    response_model=NeedOut,
    status_code=201,
    summary="Создать потребность (вилка обязательна)",
    responses=error_responses(401, 403, 422),
)
async def create_need(body: NeedCreate, user: CurrentEmployer, db: DbSession) -> NeedOut:
    return await service.create_need(db, user.id, body)


@router.get("/{need_id}", response_model=NeedOut, summary="Потребность", responses=OWNED)
async def get_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    return await service.get_need(db, user.id, need_id)


@router.put(
    "/{need_id}",
    response_model=NeedOut,
    summary="Уточнить потребность — создаётся новая версия, шорт-лист сохраняется",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_need(need_id: int, body: NeedUpdate, user: CurrentEmployer, db: DbSession) -> NeedOut:
    return await service.update_need(db, user.id, need_id, body)


@router.post(
    "/{need_id}/shortlist/{candidate_id}",
    response_model=MessageResponse,
    summary="Закрепить кандидата в шорт-листе",
    responses=LATEST_OWNED,
)
async def add_to_shortlist(
    need_id: int, candidate_id: int, body: ShortlistNote, user: CurrentEmployer, db: DbSession
) -> MessageResponse:
    return await service.add_to_shortlist(db, user.id, need_id, candidate_id, body.note)


@router.delete(
    "/{need_id}/shortlist/{candidate_id}",
    response_model=MessageResponse,
    summary="Убрать из шорт-листа",
    responses=LATEST_OWNED,
)
async def remove_from_shortlist(
    need_id: int, candidate_id: int, user: CurrentEmployer, db: DbSession
) -> MessageResponse:
    return await service.remove_from_shortlist(db, user.id, need_id, candidate_id)


@router.post(
    "/{need_id}/publish",
    response_model=NeedOut,
    summary="Опубликовать как вакансию (нужно название компании в профиле)",
    responses=LATEST_OWNED,
)
async def publish_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    return await service.set_published(db, user.id, need_id, published=True)


@router.post(
    "/{need_id}/unpublish",
    response_model=NeedOut,
    summary="Снять вакансию с публикации",
    responses=LATEST_OWNED,
)
async def unpublish_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    return await service.set_published(db, user.id, need_id, published=False)
