from fastapi import APIRouter, Query

from app.core.deps import CurrentCandidate, CurrentEmployer, DbSession
from app.core.enums import InvitationStatus
from app.core.errors import NotImplementedApiError, error_responses
from app.modules.invitations.schemas import (
    DeclineRequest,
    DeclineStats,
    InvitationCreate,
    InvitationForCandidate,
    InvitationForEmployer,
)

candidate_router = APIRouter(tags=["candidate: invitations"])
employer_router = APIRouter(tags=["employer: invitations"])

OWNED = error_responses(401, 403, 404)
TRANSITION = error_responses(401, 403, 404, 409)


@candidate_router.get(
    "/candidates/me/invitations",
    response_model=list[InvitationForCandidate],
    summary="Входящие приглашения (только свои)",
    responses=error_responses(401, 403),
)
async def list_my_invitations(
    user: CurrentCandidate, db: DbSession, status: InvitationStatus | None = Query(default=None)
) -> list[InvitationForCandidate]:
    raise NotImplementedApiError()


@candidate_router.post(
    "/invitations/{invitation_id}/view",
    response_model=InvitationForCandidate,
    summary="Отметить просмотренным (sent → viewed)",
    responses=TRANSITION,
)
async def view_invitation(
    invitation_id: int, user: CurrentCandidate, db: DbSession
) -> InvitationForCandidate:
    raise NotImplementedApiError()


@candidate_router.post(
    "/invitations/{invitation_id}/accept",
    response_model=InvitationForCandidate,
    summary="Принять — работодателю раскрываются контакты",
    responses=TRANSITION,
)
async def accept_invitation(
    invitation_id: int, user: CurrentCandidate, db: DbSession
) -> InvitationForCandidate:
    raise NotImplementedApiError()


@candidate_router.post(
    "/invitations/{invitation_id}/decline",
    response_model=InvitationForCandidate,
    summary="Отклонить с причиной",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def decline_invitation(
    invitation_id: int, body: DeclineRequest, user: CurrentCandidate, db: DbSession
) -> InvitationForCandidate:
    raise NotImplementedApiError()


@employer_router.post(
    "/invitations",
    response_model=InvitationForEmployer,
    status_code=201,
    summary="Пригласить кандидата: предложение, вилка, способ связи (409 — лимит активных приглашений)",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_invitation(
    body: InvitationCreate, user: CurrentEmployer, db: DbSession
) -> InvitationForEmployer:
    raise NotImplementedApiError()


@employer_router.get(
    "/employers/me/invitations",
    response_model=list[InvitationForEmployer],
    summary="Отправленные приглашения со статусами",
    responses=error_responses(401, 403),
)
async def list_sent_invitations(
    user: CurrentEmployer,
    db: DbSession,
    status: InvitationStatus | None = Query(default=None),
    need_id: int | None = Query(default=None),
) -> list[InvitationForEmployer]:
    raise NotImplementedApiError()


@employer_router.post(
    "/invitations/{invitation_id}/withdraw",
    response_model=InvitationForEmployer,
    summary="Отозвать приглашение",
    responses=TRANSITION,
)
async def withdraw_invitation(
    invitation_id: int, user: CurrentEmployer, db: DbSession
) -> InvitationForEmployer:
    raise NotImplementedApiError()


@employer_router.get(
    "/employers/me/decline-stats",
    response_model=DeclineStats,
    summary="Сводка причин отказов по моим приглашениям",
    responses=error_responses(401, 403),
)
async def get_decline_stats(
    user: CurrentEmployer, db: DbSession, need_id: int | None = Query(default=None)
) -> DeclineStats:
    raise NotImplementedApiError()
