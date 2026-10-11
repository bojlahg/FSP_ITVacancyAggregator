"""Интеграция с реестром ФСП (§9): импорт результатов и разрядов, компетенции, привязка ФСП ID."""

import logging
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import get_settings
from app.core.enums import CompetencyStatus, ConsentKind, FspLinkMethod, SkillSource
from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.auth.models import Consent
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.catalog.service import get_catalog
from app.modules.fsp import oidc
from app.modules.fsp.evidence import RankRecord, ResultRecord, evaluate, percentile
from app.modules.fsp.models import CandidateCompetency, FspAchievement, FspRank
from app.modules.fsp.schemas import (
    CompetencyOut,
    FspAchievementOut,
    FspLinkRequest,
    FspProfileOut,
    FspRankOut,
)

log = logging.getLogger("itscout.fsp")


class RegistryUnavailableError(AppError):
    status_code = 503
    code = "fsp_registry_unavailable"
    message = "Реестр ФСП временно недоступен, попробуйте позже"


async def fetch_from_registry(fsp_id: str) -> tuple[list[ResultRecord], list[RankRecord]] | None:
    """REST-API реестра с сервисным ключом (в проде — client credentials, §24). None — участник не найден."""
    settings = get_settings()
    headers = {"X-Api-Key": settings.fsp_api_key}
    base = settings.fsp_api_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            participant = await client.get(f"{base}/participants/{fsp_id}")
            if participant.status_code == 404:
                return None
            participant.raise_for_status()
            results = (await client.get(f"{base}/participants/{fsp_id}/results")).raise_for_status().json()
            ranks = (await client.get(f"{base}/participants/{fsp_id}/ranks")).raise_for_status().json()
    except httpx.HTTPError as exc:
        log.warning("fsp registry error: %s", exc)
        raise RegistryUnavailableError() from exc
    return (
        [
            ResultRecord(
                competition_id=row["competition"]["id"],
                competition_name=row["competition"]["name"],
                discipline=row["competition"]["discipline"],
                level=row["competition"]["level"],
                format=row["competition"]["format"],
                held_on=date.fromisoformat(row["competition"]["held_on"]),
                place=row["place"],
                participants=row["competition"]["participants_count"],
                team_role=row.get("team_role"),
                prize=row.get("prize"),
            )
            for row in results
        ],
        [RankRecord(row["discipline"], row["rank"], date.fromisoformat(row["awarded_at"])) for row in ranks],
    )


async def clear_evidence(db: AsyncSession, candidate_id: int) -> None:
    for model in (FspAchievement, FspRank, CandidateCompetency):
        await db.execute(delete(model).where(model.candidate_id == candidate_id))
    await db.execute(
        delete(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id, CandidateSkill.source == SkillSource.fsp
        )
    )


async def store_evidence(
    db: AsyncSession,
    candidate: Candidate,
    results: list[ResultRecord],
    ranks: list[RankRecord],
    today: date | None = None,
) -> None:
    """Сохраняет результаты, разряды, компетенции и навыки «подтверждено ФСП». Коммитит вызывающий."""
    catalog = get_catalog()
    today = today or datetime.now(UTC).date()
    await clear_evidence(db, candidate.id)
    evidence = evaluate(results, ranks, today, catalog)
    for result, value in zip(results, evidence.strengths, strict=True):
        db.add(
            FspAchievement(
                candidate_id=candidate.id,
                competition_id=result.competition_id,
                competition_name=result.competition_name,
                discipline=result.discipline,
                level=result.level,
                format=result.format,
                held_on=result.held_on,
                place=result.place,
                participants=result.participants,
                team_role=result.team_role,
                prize=result.prize,
                percentile=round(percentile(result.place, result.participants), 4),
                strength=round(value, 4),
            )
        )
    for rank in ranks:
        db.add(
            FspRank(
                candidate_id=candidate.id,
                discipline=rank.discipline,
                rank=rank.rank,
                awarded_at=rank.awarded_at,
            )
        )
    for item in evidence.competencies.values():
        db.add(
            CandidateCompetency(
                candidate_id=candidate.id,
                competency_id=item.competency_id,
                score=round(item.score, 4),
                status=CompetencyStatus(item.status),
                evidence=item.evidence,
            )
        )
    # Технологический навык из ФСП — максимум «подтверждено ФСП» и только через роль (§9.2)
    if evidence.supported_families:
        families = {skill.id: skill.family for skill in catalog.skills}
        declared = await db.scalars(
            select(CandidateSkill.skill_id).where(
                CandidateSkill.candidate_id == candidate.id, CandidateSkill.source == SkillSource.declared
            )
        )
        now = datetime.now(UTC)
        for skill_id in set(declared):
            if families.get(skill_id) in evidence.supported_families:
                db.add(
                    CandidateSkill(
                        candidate_id=candidate.id,
                        skill_id=skill_id,
                        source=SkillSource.fsp,
                        evidence={"families": sorted(evidence.supported_families)},
                        updated_at=now,
                    )
                )


async def candidate_fsp_score(
    db: AsyncSession, candidate_id: int, specialization: str
) -> tuple[float, bool, str | None]:
    """(fsp_score для специализации, есть ли история ФСП, высший разряд) — для индекса выдачи."""
    catalog = get_catalog()
    competencies = list(
        await db.scalars(select(CandidateCompetency).where(CandidateCompetency.candidate_id == candidate_id))
    )
    ranks = list(await db.scalars(select(FspRank.rank).where(FspRank.candidate_id == candidate_id)))
    has_results = await db.scalar(
        select(FspAchievement.id).where(FspAchievement.candidate_id == candidate_id).limit(1)
    )
    relevance = catalog.competency_relevance.get(specialization, {})
    score = max((c.score * relevance.get(c.competency_id, 0.0) for c in competencies), default=0.0)
    order = catalog.rules.fsp.rank_order
    best = max(ranks, key=order.index) if ranks else None
    return round(score, 4), bool(has_results or ranks), best


def counts_in_score(candidate: Candidate) -> bool:
    """ФСП учитывается в подборе, только если владение подтверждено входом через ФСП ID (§9.3)."""
    if candidate.fsp_link_method == FspLinkMethod.oidc:
        return True
    return candidate.fsp_link_method == FspLinkMethod.manual and get_settings().fsp_manual_link_counts


async def link_manual(db: AsyncSession, candidate: Candidate, body: FspLinkRequest) -> FspProfileOut:
    if not body.consent:
        raise AppError("Нужно согласие на импорт данных из реестра ФСП", code="consent_required")
    await _link(db, candidate, body.fsp_id, FspLinkMethod.manual)
    return await profile(db, candidate)


async def oidc_start(candidate: Candidate, consent: bool) -> tuple[str, str]:
    """(authorization_url для фронта, значение cookie флоу). Согласие даётся до ухода на ФСП ID."""
    if not consent:
        raise AppError("Нужно согласие на импорт данных из реестра ФСП", code="consent_required")
    flow = oidc.new_flow(candidate.id)
    return oidc.authorization_url(await oidc.discovery(), flow), oidc.encode_flow(flow)


async def oidc_complete(db: AsyncSession, cookie: str | None, code: str | None, state: str | None) -> None:
    """Callback: state из cookie → обмен кода → claim fsp_id из проверенного id_token → привязка."""
    flow = oidc.decode_flow(cookie, state)
    if not code:
        raise oidc.OidcError("Вход через ФСП ID отменён", code="fsp_oidc_denied")
    fsp_id = await oidc.exchange_code(code, flow)
    from app.modules.auth import service as auth_service

    candidate = await db.get(Candidate, flow.candidate_id)
    # Флоу мог начаться до удаления аккаунта: удалённому профилю ФСП не привязываем
    if candidate is None or await auth_service.is_deleted(db, candidate.user_id):
        raise NotFoundError("Профиль кандидата не найден")
    await _link(db, candidate, fsp_id, FspLinkMethod.oidc)


async def _link(db: AsyncSession, candidate: Candidate, fsp_id: str, method: FspLinkMethod) -> None:
    """Общий путь ручной и OIDC-привязки: импорт из реестра, согласие, аудит, пересчёт индекса."""
    from app.modules.matching import service as matching_service

    # Один ФСП ID — один профиль: параллельные привязки того же ID идут по очереди до конца транзакции
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"fsp_id:{fsp_id}"))))
    owner = await db.scalar(
        select(Candidate.id).where(Candidate.fsp_id == fsp_id, Candidate.id != candidate.id)
    )
    if owner is not None:
        raise ConflictError("Этот ФСП ID уже привязан к другому профилю", code="fsp_id_taken")
    fetched = await fetch_from_registry(fsp_id)
    if fetched is None:
        raise NotFoundError("Участник с таким ФСП ID не найден в реестре", code="fsp_participant_not_found")

    await store_evidence(db, candidate, *fetched)
    candidate.fsp_id = fsp_id
    candidate.fsp_link_method = method
    candidate.fsp_linked_at = datetime.now(UTC)
    settings = get_settings()
    db.add(
        Consent(
            user_id=candidate.user_id, kind=ConsentKind.fsp_import, policy_version=settings.policy_version
        )
    )
    audit(
        db,
        actor_user_id=candidate.user_id,
        action="fsp.linked",
        object_type="candidate",
        object_id=candidate.id,
        meta={"fsp_id": fsp_id, "method": method.value},
    )
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()


async def unlink_own(db: AsyncSession, candidate: Candidate) -> None:
    """Отвязка по запросу самого кандидата; общему демо-кандидату недоступна."""
    from app.modules.candidates import privacy

    await privacy.ensure_not_shared_demo(db, candidate, "отвязка ФСП")
    await unlink(db, candidate)


async def unlink(db: AsyncSession, candidate: Candidate) -> None:
    from app.modules.matching import service as matching_service

    await clear_evidence(db, candidate.id)
    await db.execute(
        update(Consent)
        .where(
            Consent.user_id == candidate.user_id,
            Consent.kind == ConsentKind.fsp_import,
            Consent.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    candidate.fsp_id = None
    candidate.fsp_link_method = None
    candidate.fsp_linked_at = None
    audit(
        db,
        actor_user_id=candidate.user_id,
        action="fsp.unlinked",
        object_type="candidate",
        object_id=candidate.id,
    )
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()


async def profile(db: AsyncSession, candidate: Candidate) -> FspProfileOut:
    names = {item.id: item.name for item in get_catalog().competencies}
    achievements = list(
        await db.scalars(
            select(FspAchievement)
            .where(FspAchievement.candidate_id == candidate.id)
            .order_by(FspAchievement.strength.desc())
        )
    )
    ranks = list(await db.scalars(select(FspRank).where(FspRank.candidate_id == candidate.id)))
    competencies = list(
        await db.scalars(
            select(CandidateCompetency)
            .where(CandidateCompetency.candidate_id == candidate.id)
            .order_by(CandidateCompetency.score.desc())
        )
    )
    return FspProfileOut(
        linked=candidate.fsp_id is not None,
        fsp_id=candidate.fsp_id,
        method=candidate.fsp_link_method,
        ownership_verified=candidate.fsp_link_method == FspLinkMethod.oidc,
        linked_at=candidate.fsp_linked_at,
        ranks=[FspRankOut.model_validate(rank) for rank in ranks],
        achievements=[FspAchievementOut.model_validate(item) for item in achievements],
        competencies=[
            CompetencyOut(
                id=item.competency_id,
                name=names.get(item.competency_id, item.competency_id),
                score=item.score,
                status=item.status,
                evidence_count=len(item.evidence or []),
            )
            for item in competencies
        ],
    )
