"""Приватность, согласия и удаление аккаунта кандидата (§6.4, §13, 152-ФЗ)."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.enums import ConsentKind, InvitationStatus, SearchStatus
from app.core.errors import ConflictError
from app.modules.auth import service as auth_service
from app.modules.auth.models import Consent, User
from app.modules.candidates.models import Candidate, CandidateExperience
from app.modules.candidates.schemas import (
    CompanyRef,
    ConsentOut,
    ConsentUpdate,
    PrivacySettings,
    SearchStatusUpdate,
)
from app.modules.candidates.service import privacy_of


def _now() -> datetime:
    return datetime.now(UTC)


async def update_privacy(db: AsyncSession, candidate: Candidate, body: PrivacySettings) -> PrivacySettings:
    from app.modules.matching import service as matching_service

    candidate.privacy = body.model_dump(exclude={"hidden_employer_ids"})
    candidate.hidden_employer_ids = sorted(set(body.hidden_employer_ids))
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    return privacy_of(candidate)


async def update_search_status(db: AsyncSession, candidate: Candidate, body: SearchStatusUpdate) -> None:
    from app.modules.matching import service as matching_service

    candidate.search_status = body.search_status
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    await db.refresh(candidate)


async def find_companies(db: AsyncSession, q: str | None, ids: list[int]) -> list[CompanyRef]:
    """Поиск компании по названию — чтобы скрыть от неё профиль (например, от текущего работодателя)."""
    from app.modules.employers.models import Employer

    query = select(Employer.id, Employer.company_name).where(Employer.company_name.is_not(None))
    if ids:
        query = query.where(Employer.id.in_(ids))
    elif q:
        query = query.where(Employer.company_name.ilike(f"%{q.strip()}%"))
    else:
        return []
    rows = await db.execute(query.order_by(Employer.company_name).limit(20))
    return [CompanyRef(id=row.id, company_name=row.company_name) for row in rows]


async def list_consents(db: AsyncSession, candidate: Candidate) -> list[ConsentOut]:
    rows = await db.scalars(
        select(Consent).where(Consent.user_id == candidate.user_id).order_by(Consent.granted_at, Consent.id)
    )
    latest = {row.kind: row for row in rows}
    result = []
    for kind in ConsentKind:
        row = latest.get(kind)
        result.append(
            ConsentOut(
                kind=kind,
                granted=row is not None and row.revoked_at is None,
                policy_version=row.policy_version if row else None,
                granted_at=row.granted_at if row else None,
                revoked_at=row.revoked_at if row else None,
            )
        )
    return result


async def update_consent(db: AsyncSession, candidate: Candidate, body: ConsentUpdate) -> list[ConsentOut]:
    """Каждое изменение — новая запись или отметка об отзыве, плюс аудит: история согласий сохраняется."""
    from app.modules.fsp import service as fsp_service
    from app.modules.matching import service as matching_service

    active = await db.scalar(
        select(Consent).where(
            Consent.user_id == candidate.user_id, Consent.kind == body.kind, Consent.revoked_at.is_(None)
        )
    )
    if body.granted and active is None:
        db.add(
            Consent(user_id=candidate.user_id, kind=body.kind, policy_version=get_settings().policy_version)
        )
        audit(
            db,
            actor_user_id=candidate.user_id,
            action="consent.granted",
            object_type="consent",
            meta={"kind": body.kind.value},
        )
    elif not body.granted and active is not None:
        if body.kind == ConsentKind.pd_processing:
            raise ConflictError(
                "Без согласия на обработку персональных данных профиль работать не может — удалите аккаунт",
                code="consent_required",
            )
        if body.kind == ConsentKind.fsp_import and candidate.fsp_id:
            # Отзыв согласия на импорт удаляет и импортированные данные ФСП
            await fsp_service.unlink(db, candidate)
        else:
            active.revoked_at = _now()
        audit(
            db,
            actor_user_id=candidate.user_id,
            action="consent.revoked",
            object_type="consent",
            meta={"kind": body.kind.value},
        )
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    return await list_consents(db, candidate)


async def delete_account(db: AsyncSession, candidate: Candidate) -> None:
    """Мягкое удаление: учётная запись закрыта, ПДн обезличены, профиль исчезает из выдачи (§13)."""
    from app.modules.appeals import service as appeals_service
    from app.modules.applications import service as applications_service
    from app.modules.categories import service as categories_service
    from app.modules.challenges import service as challenges_service
    from app.modules.expert import service as expert_service
    from app.modules.fsp import service as fsp_service
    from app.modules.integrations import service as integrations_service
    from app.modules.invitations import service as invitations_service
    from app.modules.invitations.models import Invitation
    from app.modules.matching import service as matching_service
    from app.modules.resume.models import Resume
    from app.modules.tasks import service as tasks_service
    from app.modules.testing import service as testing_service

    now = _now()
    user = await db.get(User, candidate.user_id)
    await fsp_service.clear_evidence(db, candidate.id)
    paths = [
        Path(path)
        for path in await db.scalars(select(Resume.file_path).where(Resume.candidate_id == candidate.id))
    ]
    await asyncio.to_thread(lambda: [path.unlink(missing_ok=True) for path in paths])
    await db.execute(delete(Resume).where(Resume.candidate_id == candidate.id))
    await db.execute(delete(CandidateExperience).where(CandidateExperience.candidate_id == candidate.id))
    # Копии данных кандидата вне профиля: события для ATS и снимки экспертной разметки
    await integrations_service.forget_candidate(db, candidate.id)
    await expert_service.forget_candidate(db, candidate.id)
    await appeals_service.forget_candidate(db, candidate.id)
    # Свободный текст кандидата в решениях, ответах теста и челленджей, откликах, отказах и жалобах (§13)
    await tasks_service.forget_candidate(db, candidate.id)
    await testing_service.forget_candidate(db, candidate.id)
    await applications_service.forget_candidate(db, candidate.id)
    await invitations_service.forget_candidate(db, candidate.id)
    await challenges_service.forget_candidate(db, candidate.id)
    await db.execute(
        update(Invitation)
        .where(
            Invitation.candidate_id == candidate.id,
            Invitation.status.in_((InvitationStatus.sent, InvitationStatus.viewed)),
        )
        .values(status=InvitationStatus.expired)
    )

    for field in (
        "last_name",
        "middle_name",
        "phone",
        "telegram",
        "contact_email",
        "about",
        "city",
        "fsp_id",
    ):
        setattr(candidate, field, None)
    candidate.first_name = "Удалённый пользователь"
    candidate.fsp_link_method = None
    candidate.fsp_linked_at = None
    candidate.search_status = SearchStatus.hidden
    candidate.privacy = {}
    candidate.hidden_employer_ids = []

    await db.execute(
        update(Consent)
        .where(Consent.user_id == candidate.user_id, Consent.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await auth_service.revoke_sessions(db, candidate.user_id)
    if user is not None:
        user.email = f"deleted-{user.id}@deleted.invalid"
        user.password_hash = "!"
        user.deleted_at = now
    audit(
        db,
        actor_user_id=candidate.user_id,
        action="account.deleted",
        object_type="candidate",
        object_id=candidate.id,
    )
    await db.flush()
    await matching_service.drop_candidate(db, candidate.id)
    # Удалённый не участвует в перцентилях соседей по категории (они входят в VPS и сортировку)
    retired = await categories_service.retire_current(db, candidate.id)
    if retired is not None:
        await matching_service.refresh_category(db, *retired)
    await db.commit()
