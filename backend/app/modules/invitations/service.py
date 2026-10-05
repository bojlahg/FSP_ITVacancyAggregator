"""Приглашения (§8.1 п.6–7, §8.5, §8.6): лимит, статусы, раскрытие контактов, статистика отказов."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mail_templates
from app.core.audit import audit
from app.core.config import get_settings
from app.core.enums import DeclineReason, InvitationStatus, ReportStatus, UnlockSource
from app.core.errors import ConflictError, NotFoundError
from app.core.mail import Mail
from app.core.schemas import Explanation
from app.core.text_rules import check_texts
from app.modules.auth import service as auth_service
from app.modules.candidates import service as candidates_service
from app.modules.candidates.models import Candidate
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.integrations import service as integrations_service
from app.modules.invitations.models import ContactUnlock, Invitation, InvitationReport
from app.modules.invitations.schemas import (
    ContactMethod,
    DeclineRequest,
    DeclineStats,
    InvitationCreate,
    InvitationForCandidate,
    InvitationForEmployer,
    InvitationWarning,
    ReportBrief,
    ReportForAdmin,
    ReportRequest,
    ReportResolve,
)
from app.modules.matching import service as matching_service
from app.modules.needs import service as needs_service

ACTIVE = (InvitationStatus.sent, InvitationStatus.viewed)
DECLINE_NAMES = {
    DeclineReason.salary: "зарплата",
    DeclineReason.stack: "стек",
    DeclineReason.work_format: "формат работы",
    DeclineReason.company: "компания",
    DeclineReason.not_looking: "не ищут работу",
    DeclineReason.other: "другое",
}


class InvitationLimitError(ConflictError):
    code = "invitation_limit"
    message = "По этой потребности уже максимум активных приглашений — дождитесь ответов"


class AlreadyInvitedError(ConflictError):
    code = "already_invited"
    message = "У кандидата уже есть активное приглашение от вашей компании"


class InvitationClosedError(ConflictError):
    code = "invitation_closed"
    message = "Приглашение уже не активно"


def _now() -> datetime:
    return datetime.now(UTC)


async def expire_overdue(db: AsyncSession) -> None:
    """Истечение срока считается лениво при каждом обращении — фоновые задачи не нужны."""
    await db.execute(
        update(Invitation)
        .where(Invitation.status.in_(ACTIVE), Invitation.expires_at < _now())
        .values(status=InvitationStatus.expired)
    )


async def _mail_candidate(
    db: AsyncSession, invitation: Invitation, outbox: list[Mail] | None, withdrawn: bool
) -> None:
    """Письмо кандидату о новом или отозванном приглашении (§8.9)."""
    if outbox is None:
        return
    candidate = await db.get(Candidate, invitation.candidate_id)
    to = await auth_service.notification_email(db, candidate.user_id) if candidate else None
    if to is None:
        return
    employer = await db.get(Employer, invitation.employer_id)
    company = (employer.company_name if employer else None) or "Компания"
    if withdrawn:
        outbox.append(mail_templates.invitation_withdrawn(to, company, invitation.title))
    else:
        outbox.append(
            mail_templates.invitation_received(
                to, company, invitation.title, invitation.salary_from, invitation.salary_to
            )
        )


async def _mail_employer(db: AsyncSession, invitation: Invitation, outbox: list[Mail] | None) -> None:
    """Письмо работодателю об ответе кандидата (§8.9): имя как в выдаче, без контактов."""
    if outbox is None:
        return
    employer = await db.get(Employer, invitation.employer_id)
    to = await auth_service.notification_email(db, employer.user_id) if employer else None
    if to is None:
        return
    brief = (await matching_service.briefs(db, [invitation.candidate_id])).get(invitation.candidate_id)
    name = brief.display_name if brief else "Кандидат"
    if invitation.status == InvitationStatus.accepted:
        mail = mail_templates.invitation_accepted(to, name, invitation.title, invitation.candidate_id)
    else:
        reason = DECLINE_NAMES[invitation.decline_reason] if invitation.decline_reason else "не указана"
        mail = mail_templates.invitation_declined(to, name, invitation.title, reason)
    outbox.append(mail)


def _explanation(snapshot: dict | None) -> Explanation | None:
    return Explanation.model_validate(snapshot) if snapshot else None


async def _for_employer(db: AsyncSession, items: list[Invitation]) -> list[InvitationForEmployer]:
    briefs = await matching_service.briefs(db, [item.candidate_id for item in items])
    result = []
    for item in items:
        brief = briefs.get(item.candidate_id)
        if brief is None:
            continue
        contacts = None
        if await matching_service.contacts_unlocked(db, item.employer_id, item.candidate_id):
            candidate = await db.get(Candidate, item.candidate_id)
            contacts = await matching_service.contacts_of(db, candidate) if candidate else None
        result.append(
            InvitationForEmployer(
                id=item.id,
                candidate=brief,
                need_id=item.need_id,
                title=item.title,
                message=item.message,
                salary_from=item.salary_from,
                salary_to=item.salary_to,
                contact_method=ContactMethod.model_validate(item.contact_method),
                match_snapshot=_explanation(item.match_snapshot),
                status=item.status,
                decline_reason=item.decline_reason,
                decline_comment=item.decline_comment,
                contacts=contacts,
                created_at=item.created_at,
                viewed_at=item.viewed_at,
                responded_at=item.responded_at,
                expires_at=item.expires_at,
            )
        )
    return result


SCAM_RULES_FILE = "invitation_scam_rules.yaml"


def scam_warnings(title: str, message: str) -> list[InvitationWarning]:
    """Признаки мошенничества (§8.5): только предупреждение кандидату, приглашение не блокируется."""
    if not get_settings().invitation_scam_check:
        return []
    return [
        InvitationWarning(rule=i.rule, label=i.label, message=i.message, fragment=i.fragment)
        for i in check_texts(SCAM_RULES_FILE, title, message)
    ]


async def _for_candidate(db: AsyncSession, item: Invitation) -> InvitationForCandidate:
    employer = await db.get(Employer, item.employer_id)
    report = await db.scalar(select(InvitationReport).where(InvitationReport.invitation_id == item.id))
    return InvitationForCandidate(
        id=item.id,
        company=await employers_service.company_public(db, employer),
        title=item.title,
        message=item.message,
        salary_from=item.salary_from,
        salary_to=item.salary_to,
        # Контакт рекрутера кандидат получает после принятия — симметрично раскрытию его контактов (§8.5)
        contact_method=ContactMethod.model_validate(item.contact_method)
        if item.status == InvitationStatus.accepted
        else None,
        why_you=_explanation(item.match_snapshot) or Explanation(lines=[]),
        salary_market=await matching_service.salary_market_for_candidate(
            db, item.candidate_id, item.salary_from, item.salary_to
        ),
        status=item.status,
        created_at=item.created_at,
        viewed_at=item.viewed_at,
        responded_at=item.responded_at,
        expires_at=item.expires_at,
        warnings=scam_warnings(item.title, item.message),
        report=ReportBrief(reason=report.reason, status=report.status, created_at=report.created_at)
        if report
        else None,
    )


# ---------- работодатель ----------


async def create(
    db: AsyncSession, user_id: int, body: InvitationCreate, outbox: list[Mail] | None = None
) -> InvitationForEmployer:
    employer = await employers_service.get_by_user(db, user_id)
    if await db.get(Candidate, body.candidate_id) is None or not await matching_service.reachable(
        db, employer.id, body.candidate_id
    ):
        raise NotFoundError("Кандидат не найден")
    await expire_overdue(db)

    active = await db.scalar(
        select(Invitation.id).where(
            Invitation.employer_id == employer.id,
            Invitation.candidate_id == body.candidate_id,
            Invitation.status.in_(ACTIVE),
        )
    )
    if active is not None:
        raise AlreadyInvitedError()

    need = None
    if body.need_id is not None:
        need = await needs_service.get_own_need(db, user_id, body.need_id)
        # Лимит считается по всей цепочке версий: уточнение потребности не обнуляет счётчик (§8.6 п.3)
        chain = await needs_service.version_chain_ids(db, need)
        used = await db.scalar(
            select(func.count())
            .select_from(Invitation)
            .where(Invitation.need_id.in_(chain), Invitation.status.in_(ACTIVE))
        )
        if used >= get_settings().max_active_invites_per_need:
            raise InvitationLimitError()

    snapshot = await matching_service.snapshot_for(db, employer.id, body.candidate_id, need)
    days = body.expires_in_days or get_settings().invitation_ttl_days
    invitation = Invitation(
        employer_id=employer.id,
        candidate_id=body.candidate_id,
        need_id=need.id if need else None,
        title=body.title,
        message=body.message,
        salary_from=body.salary_from,
        salary_to=body.salary_to,
        contact_method=body.contact_method.model_dump(mode="json"),
        match_snapshot=snapshot.explanation.model_dump(mode="json") if snapshot else None,
        status=InvitationStatus.sent,
        expires_at=_now() + timedelta(days=days),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    await _mail_candidate(db, invitation, outbox, withdrawn=False)
    return (await _for_employer(db, [invitation]))[0]


async def list_sent(
    db: AsyncSession, user_id: int, status: InvitationStatus | None, need_id: int | None
) -> list[InvitationForEmployer]:
    employer = await employers_service.get_by_user(db, user_id)
    await expire_overdue(db)
    await db.commit()
    query = select(Invitation).where(Invitation.employer_id == employer.id)
    if status is not None:
        query = query.where(Invitation.status == status)
    if need_id is not None:
        need = await needs_service.get_own_need(db, user_id, need_id)
        query = query.where(Invitation.need_id.in_(await needs_service.version_chain_ids(db, need)))
    items = list(await db.scalars(query.order_by(Invitation.created_at.desc(), Invitation.id.desc())))
    return await _for_employer(db, items)


async def withdraw(
    db: AsyncSession, user_id: int, invitation_id: int, outbox: list[Mail] | None = None
) -> InvitationForEmployer:
    employer = await employers_service.get_by_user(db, user_id)
    await expire_overdue(db)
    invitation = await db.get(Invitation, invitation_id)
    if invitation is None or invitation.employer_id != employer.id:
        raise NotFoundError("Приглашение не найдено")
    if invitation.status not in ACTIVE:
        raise InvitationClosedError()
    invitation.status = InvitationStatus.withdrawn
    invitation.responded_at = _now()
    await db.commit()
    await db.refresh(invitation)
    await _mail_candidate(db, invitation, outbox, withdrawn=True)
    return (await _for_employer(db, [invitation]))[0]


async def decline_stats(db: AsyncSession, user_id: int, need_id: int | None) -> DeclineStats:
    """Обратная связь по отказам (§8.6 п.2): «3 из 5 отказов — зарплата»."""
    employer = await employers_service.get_by_user(db, user_id)
    await expire_overdue(db)
    await db.commit()
    query = select(Invitation.status, Invitation.decline_reason).where(Invitation.employer_id == employer.id)
    if need_id is not None:
        need = await needs_service.get_own_need(db, user_id, need_id)
        query = query.where(Invitation.need_id.in_(await needs_service.version_chain_ids(db, need)))
    rows = (await db.execute(query)).all()
    statuses = Counter(status for status, _ in rows)
    reasons = Counter(reason for status, reason in rows if status == InvitationStatus.declined and reason)
    accepted = statuses[InvitationStatus.accepted]
    declined = statuses[InvitationStatus.declined]
    top = reasons.most_common(1)[0][0] if reasons else None
    hint = None
    if top is not None:
        hint = f"{reasons[top]} из {declined} отказов — {DECLINE_NAMES[top]}"
    return DeclineStats(
        total_sent=len(rows),
        accepted=accepted,
        declined=declined,
        expired=statuses[InvitationStatus.expired],
        acceptance_rate=round(accepted / (accepted + declined), 3) if accepted + declined else None,
        by_reason={reason: reasons[reason] for reason in DeclineReason},
        top_reason=top,
        hint=hint,
    )


# ---------- кандидат ----------


async def list_mine(
    db: AsyncSession, user_id: int, status: InvitationStatus | None
) -> list[InvitationForCandidate]:
    candidate = await candidates_service.get_by_user(db, user_id)
    await expire_overdue(db)
    await db.commit()
    query = select(Invitation).where(Invitation.candidate_id == candidate.id)
    if status is not None:
        query = query.where(Invitation.status == status)
    items = await db.scalars(query.order_by(Invitation.created_at.desc(), Invitation.id.desc()))
    return [await _for_candidate(db, item) for item in items]


async def _own(db: AsyncSession, user_id: int, invitation_id: int) -> tuple[Candidate, Invitation]:
    candidate = await candidates_service.get_by_user(db, user_id)
    await expire_overdue(db)
    invitation = await db.get(Invitation, invitation_id)
    # Чужое приглашение неотличимо от несуществующего
    if invitation is None or invitation.candidate_id != candidate.id:
        raise NotFoundError("Приглашение не найдено")
    return candidate, invitation


async def view(db: AsyncSession, user_id: int, invitation_id: int) -> InvitationForCandidate:
    _, invitation = await _own(db, user_id, invitation_id)
    if invitation.status == InvitationStatus.sent:
        invitation.status = InvitationStatus.viewed
        invitation.viewed_at = _now()
    await db.commit()
    await db.refresh(invitation)
    return await _for_candidate(db, invitation)


async def _notify(db: AsyncSession, invitation: Invitation, event: str) -> None:
    """Webhook ATS: те же данные, что работодатель видит в API (контакты — только после раскрытия)."""
    items = await _for_employer(db, [invitation])
    if items:
        data = items[0].model_dump(mode="json")
        await integrations_service.enqueue(db, invitation.employer_id, event, data)


async def accept(
    db: AsyncSession, user_id: int, invitation_id: int, outbox: list[Mail] | None = None
) -> InvitationForCandidate:
    candidate, invitation = await _own(db, user_id, invitation_id)
    if invitation.status not in ACTIVE:
        raise InvitationClosedError()
    now = _now()
    invitation.status = InvitationStatus.accepted
    invitation.viewed_at = invitation.viewed_at or now
    invitation.responded_at = now
    await unlock_contacts(
        db, user_id, invitation.employer_id, candidate.id, UnlockSource.invitation, invitation.id
    )
    await _notify(db, invitation, "invitation.accepted")
    await db.commit()
    await db.refresh(invitation)
    await _mail_employer(db, invitation, outbox)
    return await _for_candidate(db, invitation)


async def decline(
    db: AsyncSession,
    user_id: int,
    invitation_id: int,
    body: DeclineRequest,
    outbox: list[Mail] | None = None,
) -> InvitationForCandidate:
    _, invitation = await _own(db, user_id, invitation_id)
    if invitation.status not in ACTIVE:
        raise InvitationClosedError()
    now = _now()
    invitation.status = InvitationStatus.declined
    invitation.decline_reason = body.reason
    invitation.decline_comment = body.comment
    invitation.viewed_at = invitation.viewed_at or now
    invitation.responded_at = now
    await _notify(db, invitation, "invitation.declined")
    await db.commit()
    await db.refresh(invitation)
    await _mail_employer(db, invitation, outbox)
    return await _for_candidate(db, invitation)


async def unlock_contacts(
    db: AsyncSession,
    actor_user_id: int,
    employer_id: int,
    candidate_id: int,
    source: UnlockSource,
    source_id: int,
) -> None:
    """Единственная точка записи в contact_unlocks (+ аудит, §13). Коммитит вызывающий."""
    if await db.get(ContactUnlock, (employer_id, candidate_id)) is not None:
        return
    db.add(
        ContactUnlock(employer_id=employer_id, candidate_id=candidate_id, source=source, source_id=source_id)
    )
    audit(
        db,
        actor_user_id=actor_user_id,
        action="contacts.unlock",
        object_type=source.value,
        object_id=source_id,
        meta={"employer_id": employer_id, "candidate_id": candidate_id},
    )


# ---------- жалобы ----------


async def report(
    db: AsyncSession, user_id: int, invitation_id: int, body: ReportRequest
) -> InvitationForCandidate:
    """Одна жалоба на приглашение; статус приглашения не меняется — отклонить кандидат может отдельно."""
    _, invitation = await _own(db, user_id, invitation_id)
    exists = await db.scalar(
        select(InvitationReport.id).where(InvitationReport.invitation_id == invitation.id)
    )
    if exists is not None:
        raise ConflictError("Жалоба на это приглашение уже отправлена", code="report_exists")
    db.add(InvitationReport(invitation_id=invitation.id, reason=body.reason, comment=body.comment))
    audit(
        db,
        actor_user_id=user_id,
        action="invitation.report",
        object_type="invitation",
        object_id=invitation.id,
        meta={"reason": body.reason.value},
    )
    await db.commit()
    await db.refresh(invitation)
    return await _for_candidate(db, invitation)


async def _report_for_admin(db: AsyncSession, row: InvitationReport) -> ReportForAdmin:
    invitation = await db.get(Invitation, row.invitation_id)
    employer = await db.get(Employer, invitation.employer_id)
    return ReportForAdmin(
        id=row.id,
        invitation_id=invitation.id,
        employer_id=invitation.employer_id,
        company_name=employer.company_name if employer else None,
        invitation_title=invitation.title,
        invitation_message=invitation.message,
        warnings=scam_warnings(invitation.title, invitation.message),
        reason=row.reason,
        comment=row.comment,
        status=row.status,
        resolution=row.resolution,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


async def list_reports(db: AsyncSession, status: ReportStatus | None) -> list[ReportForAdmin]:
    query = select(InvitationReport)
    if status is not None:
        query = query.where(InvitationReport.status == status)
    rows = await db.scalars(query.order_by(InvitationReport.created_at.desc(), InvitationReport.id.desc()))
    return [await _report_for_admin(db, row) for row in rows]


async def resolve_report(
    db: AsyncSession, user_id: int, report_id: int, body: ReportResolve
) -> ReportForAdmin:
    row = await db.get(InvitationReport, report_id)
    if row is None:
        raise NotFoundError("Жалоба не найдена")
    row.status = ReportStatus.resolved
    row.resolution = body.resolution
    row.resolved_at = _now()
    audit(
        db,
        actor_user_id=user_id,
        action="invitation_report.resolve",
        object_type="invitation_report",
        object_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return await _report_for_admin(db, row)


async def forget_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Удаление аккаунта: комментарии к отказам и жалобам — ПДн; причина и статус жалобы остаются.

    Коммитит вызывающий.
    """
    invitations = select(Invitation.id).where(Invitation.candidate_id == candidate_id)
    await db.execute(
        update(Invitation).where(Invitation.candidate_id == candidate_id).values(decline_comment=None)
    )
    await db.execute(
        update(InvitationReport).where(InvitationReport.invitation_id.in_(invitations)).values(comment=None)
    )
