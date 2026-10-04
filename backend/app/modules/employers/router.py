from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.employers.schemas import EmployerProfileOut, EmployerProfileUpdate

router = APIRouter(prefix="/employers/me", tags=["employer: company"])


@router.get(
    "", response_model=EmployerProfileOut, summary="Профиль компании", responses=error_responses(401, 403)
)
async def get_company(user: CurrentEmployer, db: DbSession) -> EmployerProfileOut:
    raise NotImplementedApiError()


@router.put(
    "",
    response_model=EmployerProfileOut,
    summary="Обновить профиль компании",
    responses=error_responses(401, 403, 422),
)
async def update_company(
    body: EmployerProfileUpdate, user: CurrentEmployer, db: DbSession
) -> EmployerProfileOut:
    raise NotImplementedApiError()
