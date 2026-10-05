from fastapi import APIRouter

from app.core.deps import CurrentEmployer, DbSession
from app.core.errors import error_responses
from app.modules.employers import service
from app.modules.employers.schemas import EmployerProfileOut, EmployerProfileUpdate

router = APIRouter(prefix="/employers/me", tags=["employer: company"])


@router.get(
    "",
    response_model=EmployerProfileOut,
    summary="Профиль компании и репутация по приглашениям и откликам",
    responses=error_responses(401, 403),
)
async def get_company(user: CurrentEmployer, db: DbSession) -> EmployerProfileOut:
    return await service.get_profile(db, user.id)


@router.put(
    "",
    response_model=EmployerProfileOut,
    summary="Обновить профиль компании",
    responses=error_responses(401, 403, 422),
)
async def update_company(
    body: EmployerProfileUpdate, user: CurrentEmployer, db: DbSession
) -> EmployerProfileOut:
    return await service.update_profile(db, user.id, body)
