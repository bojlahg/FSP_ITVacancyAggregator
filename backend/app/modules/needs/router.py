from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.core.schemas import MessageResponse
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


@router.get(
    "",
    response_model=list[NeedOut],
    summary="Мои потребности и вакансии",
    responses=error_responses(401, 403),
)
async def list_needs(user: CurrentEmployer, db: DbSession) -> list[NeedOut]:
    raise NotImplementedApiError()


@router.post(
    "/parse",
    response_model=NeedParseResult,
    summary="Разобрать текст потребности: словарь, затем LLM; результат — редактируемая форма",
    responses=error_responses(401, 403, 422),
)
async def parse_need(body: NeedParseRequest, user: CurrentEmployer) -> NeedParseResult:
    raise NotImplementedApiError()


@router.post(
    "",
    response_model=NeedOut,
    status_code=201,
    summary="Создать потребность (вилка обязательна)",
    responses=error_responses(401, 403, 422),
)
async def create_need(body: NeedCreate, user: CurrentEmployer, db: DbSession) -> NeedOut:
    raise NotImplementedApiError()


@router.get("/{need_id}", response_model=NeedOut, summary="Потребность", responses=OWNED)
async def get_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    raise NotImplementedApiError()


@router.put(
    "/{need_id}",
    response_model=NeedOut,
    summary="Уточнить потребность — создаётся новая версия, шорт-лист сохраняется",
    responses=error_responses(401, 403, 404, 422),
)
async def update_need(need_id: int, body: NeedUpdate, user: CurrentEmployer, db: DbSession) -> NeedOut:
    raise NotImplementedApiError()


@router.post(
    "/{need_id}/shortlist/{candidate_id}",
    response_model=MessageResponse,
    summary="Закрепить кандидата в шорт-листе",
    responses=OWNED,
)
async def add_to_shortlist(
    need_id: int, candidate_id: int, body: ShortlistNote, user: CurrentEmployer, db: DbSession
) -> MessageResponse:
    raise NotImplementedApiError()


@router.delete(
    "/{need_id}/shortlist/{candidate_id}",
    response_model=MessageResponse,
    summary="Убрать из шорт-листа",
    responses=OWNED,
)
async def remove_from_shortlist(
    need_id: int, candidate_id: int, user: CurrentEmployer, db: DbSession
) -> MessageResponse:
    raise NotImplementedApiError()


@router.post(
    "/{need_id}/publish", response_model=NeedOut, summary="Опубликовать как вакансию", responses=OWNED
)
async def publish_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    raise NotImplementedApiError()


@router.post(
    "/{need_id}/unpublish", response_model=NeedOut, summary="Снять вакансию с публикации", responses=OWNED
)
async def unpublish_need(need_id: int, user: CurrentEmployer, db: DbSession) -> NeedOut:
    raise NotImplementedApiError()
