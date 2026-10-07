from fastapi import APIRouter, BackgroundTasks, Query

from app.core.deps import CurrentAdmin, CurrentCandidate, CurrentEmployer, DbSession
from app.core.enums import InvitationStatus, ReportStatus
from app.core.errors import error_responses
from app.core.mail import Mail, send_all
from app.modules.integrations import service as integrations_service
from app.modules.invitations import service
from app.modules.invitations.schemas import (
    DeclineRequest,
    DeclineStats,
    InvitationCreate,
    InvitationForCandidate,
    InvitationForEmployer,
    ReportForAdmin,
    ReportRequest,
    ReportResolve,
)

candidate_router = APIRouter(tags=["candidate: invitations"])
employer_router = APIRouter(tags=["employer: invitations"])
admin_router = APIRouter(prefix="/admin/invitation-reports", tags=["admin: reports"])

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
    return await service.list_mine(db, user.id, status)


@candidate_router.post(
    "/invitations/{invitation_id}/view",
    response_model=InvitationForCandidate,
    summary="Отметить просмотренным (sent → viewed)",
    responses=TRANSITION,
)
async def view_invitation(
    invitation_id: int, user: CurrentCandidate, db: DbSession
) -> InvitationForCandidate:
    return await service.view(db, user.id, invitation_id)


@candidate_router.post(
    "/invitations/{invitation_id}/accept",
    response_model=InvitationForCandidate,
    summary="Принять — работодателю раскрываются контакты",
    responses=TRANSITION,
)
async def accept_invitation(
    invitation_id: int, user: CurrentCandidate, db: DbSession, background: BackgroundTasks
) -> InvitationForCandidate:
    outbox: list[Mail] = []
    result = await service.accept(db, user.id, invitation_id, outbox)
    background.add_task(integrations_service.deliver_pending)
    background.add_task(send_all, outbox)
    return result


@candidate_router.post(
    "/invitations/{invitation_id}/decline",
    response_model=InvitationForCandidate,
    summary="Отклонить с причиной",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def decline_invitation(
    invitation_id: int,
    body: DeclineRequest,
    user: CurrentCandidate,
    db: DbSession,
    background: BackgroundTasks,
) -> InvitationForCandidate:
    outbox: list[Mail] = []
    result = await service.decline(db, user.id, invitation_id, body, outbox)
    background.add_task(integrations_service.deliver_pending)
    background.add_task(send_all, outbox)
    return result


@employer_router.post(
    "/invitations",
    response_model=InvitationForEmployer,
    status_code=201,
    summary=(
        "Пригласить кандидата: предложение, вилка, способ связи "
        "(409 invitation_limit — лимит активных приглашений, "
        "company_profile_required — не заполнено название компании)"
    ),
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_invitation(
    body: InvitationCreate, user: CurrentEmployer, db: DbSession, background: BackgroundTasks
) -> InvitationForEmployer:
    outbox: list[Mail] = []
    result = await service.create(db, user.id, body, outbox)
    background.add_task(send_all, outbox)
    return result


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
    return await service.list_sent(db, user.id, status, need_id)


@employer_router.post(
    "/invitations/{invitation_id}/withdraw",
    response_model=InvitationForEmployer,
    summary="Отозвать приглашение",
    responses=TRANSITION,
)
async def withdraw_invitation(
    invitation_id: int, user: CurrentEmployer, db: DbSession, background: BackgroundTasks
) -> InvitationForEmployer:
    outbox: list[Mail] = []
    result = await service.withdraw(db, user.id, invitation_id, outbox)
    background.add_task(send_all, outbox)
    return result


@employer_router.get(
    "/employers/me/decline-stats",
    response_model=DeclineStats,
    summary="Сводка причин отказов по моим приглашениям",
    responses=error_responses(401, 403),
)
async def get_decline_stats(
    user: CurrentEmployer, db: DbSession, need_id: int | None = Query(default=None)
) -> DeclineStats:
    return await service.decline_stats(db, user.id, need_id)


@candidate_router.post(
    "/invitations/{invitation_id}/report",
    response_model=InvitationForCandidate,
    summary="Пожаловаться на приглашение (409 report_exists — жалоба уже подана)",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def report_invitation(
    invitation_id: int, body: ReportRequest, user: CurrentCandidate, db: DbSession
) -> InvitationForCandidate:
    return await service.report(db, user.id, invitation_id, body)


@admin_router.get(
    "",
    response_model=list[ReportForAdmin],
    summary="Жалобы кандидатов на приглашения",
    responses=error_responses(401, 403),
)
async def list_reports(
    user: CurrentAdmin, db: DbSession, status: ReportStatus | None = Query(default=None)
) -> list[ReportForAdmin]:
    return await service.list_reports(db, status)


@admin_router.post(
    "/{report_id}/resolve",
    response_model=ReportForAdmin,
    summary="Закрыть жалобу с описанием принятых мер",
    responses=error_responses(401, 403, 404, 422),
)
async def resolve_report(
    report_id: int, body: ReportResolve, user: CurrentAdmin, db: DbSession
) -> ReportForAdmin:
    return await service.resolve_report(db, user.id, report_id, body)
