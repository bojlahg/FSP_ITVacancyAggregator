from fastapi import APIRouter

from app.core.errors import error_responses
from app.modules.legal import service
from app.modules.legal.schemas import LegalDocument, LegalDocumentRef

router = APIRouter(prefix="/legal", tags=["public: legal"])


@router.get(
    "/documents",
    response_model=list[LegalDocumentRef],
    summary="Список юридических документов: политика, согласия, правила рекомендаций",
)
async def list_documents() -> list[LegalDocumentRef]:
    return service.list_documents()


@router.get(
    "/documents/{slug}",
    response_model=LegalDocument,
    summary="Текст документа; числа в правилах рекомендаций — из действующих весов подбора",
    responses=error_responses(404),
)
async def get_document(slug: str) -> LegalDocument:
    return service.get_document(slug)
