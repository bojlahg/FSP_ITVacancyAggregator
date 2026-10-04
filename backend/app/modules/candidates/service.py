from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates.models import Candidate


def create_empty_profile(db: AsyncSession, user_id: int) -> Candidate:
    candidate = Candidate(user_id=user_id, work_formats=[], roles=[], privacy={})
    db.add(candidate)
    return candidate
