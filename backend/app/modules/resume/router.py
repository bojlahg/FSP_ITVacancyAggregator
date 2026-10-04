from typing import Literal

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import Response

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.resume.schemas import ResumeParseResult

router = APIRouter(prefix="/candidates/me", tags=["candidate: profile"])

PDF_RESPONSE = {200: {"content": {"application/pdf": {}}, "description": "PDF-файл"}}


@router.post(
    "/resume",
    response_model=ResumeParseResult,
    summary="Загрузить PDF-резюме и получить предзаполнение профиля",
    responses=error_responses(401, 403, 422),
)
async def upload_resume(
    user: CurrentCandidate,
    db: DbSession,
    file: UploadFile = File(description="PDF до 5 МБ"),
) -> ResumeParseResult:
    raise NotImplementedApiError()


@router.get(
    "/profile.pdf",
    response_class=Response,
    summary="Стандартизированный PDF-профиль",
    responses={**PDF_RESPONSE, **error_responses(401, 403)},
)
async def my_profile_pdf(
    user: CurrentCandidate,
    db: DbSession,
    variant: Literal["full", "public"] = Query(default="full"),
) -> Response:
    raise NotImplementedApiError()
