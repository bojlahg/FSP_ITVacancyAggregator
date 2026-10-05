from typing import Literal

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import Response

from app.core.deps import CurrentCandidate, DbSession
from app.core.errors import error_responses
from app.modules.resume import service
from app.modules.resume.schemas import ResumeParseResult

router = APIRouter(prefix="/candidates/me", tags=["candidate: profile"])

PDF_RESPONSE = {200: {"content": {"application/pdf": {}}, "description": "PDF-файл"}}


def pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/resume",
    response_model=ResumeParseResult,
    summary="Загрузить PDF-резюме и получить предзаполнение профиля",
    description=(
        "PDF до 5 МБ → текст (pdfplumber) → словарный разбор, при подключённом LLM — дополнение. "
        "Профиль не меняется: кандидат правит prefill и сохраняет его через PUT /candidates/me. "
        "Навыки из резюме сохраняются только как «заявлено», грейд и категорию определяет тест. "
        "422 с кодом file_too_large, not_pdf или invalid_pdf — файл не подходит."
    ),
    responses=error_responses(401, 403, 422),
)
async def upload_resume(
    user: CurrentCandidate,
    db: DbSession,
    file: UploadFile = File(description="PDF до 5 МБ"),
) -> ResumeParseResult:
    return await service.upload_resume(db, user.id, file)


@router.get(
    "/profile.pdf",
    response_class=Response,
    summary="Стандартизированный PDF-профиль",
    description="full — полная версия с контактами; public — так профиль видит работодатель до контакта.",
    responses={**PDF_RESPONSE, **error_responses(401, 403, 422)},
)
async def my_profile_pdf(
    user: CurrentCandidate,
    db: DbSession,
    variant: Literal["full", "public"] = Query(default="full"),
) -> Response:
    return pdf_response(*await service.own_profile_pdf(db, user.id, variant))
