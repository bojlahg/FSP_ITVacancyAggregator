from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employers.models import Employer


def create_empty_profile(db: AsyncSession, user_id: int, company_name: str | None = None) -> Employer:
    employer = Employer(user_id=user_id, company_name=company_name)
    db.add(employer)
    return employer
