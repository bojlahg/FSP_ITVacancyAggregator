"""Вакансии и отклики (§8.7): вакансия — последняя версия потребности с published=true."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApplicationStatus, Grade, NeedStatus, UnlockSource
from app.core.errors import ConflictError, NotFoundError
from app.core.schemas import Explanation
from app.modules.applications.models import Application
from app.modules.applications.schemas import (
    ApplicationForCandidate,
    ApplicationForEmployer,
    ApplyRequest,
    VacancyOut,
)
from app.modules.candidates import service as candidates_service
from app.modules.candidates.models import Candidate
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.employers.schemas import CompanyPublic
from app.modules.integrations import service as integrations_service
from app.modules.invitations import service as invitations_service
from app.modules.matching import service as matching_service
from app.modules.matching.schemas import CandidateMatch
from app.modules.needs import service as needs_service
from app.modules.needs.models import HiringNeed

OPEN = (ApplicationStatus.sent, ApplicationStatus.viewed)


class AlreadyAppliedError(ConflictError):
    code = "already_applied"
    message = "Вы уже откликнулись на эту вакансию"


class CategoryRequiredError(ConflictError):
    code = "category_required"
    message = "Откликаться можно после теста: работодатель сравнивает отклики по категории"


class ApplicationClosedError(ConflictError):
    code = "application_closed"
    message = "По этому отклику уже есть решение"


def _now() -> datetime:
    return datetime.now(UTC)


def _snapshot(match: CandidateMatch | None) -> dict | None:
    if match is None:
        return None
    return {"score": match.score, **match.explanation.model_dump(mode="json")}


def _published(query):
    return query.where(HiringNeed.published.is_(True), HiringNeed.status != NeedStatus.closed)


async def _vacancy(
    db: AsyncSession,
    need: HiringNeed,
    match: CandidateMatch | None,
    applied: bool,
    companies: dict[int, CompanyPublic] | None = None,
) -> VacancyOut:
    companies = {} if companies is None else companies
    if need.employer_id not in companies:
        employer = await db.get(Employer, need.employer_id)
        companies[need.employer_id] = await employers_service.company_public(db, employer)
    return VacancyOut(
        id=need.id,
        title=need.title,
        company=companies[need.employer_id],
        category=categories_service.category_ref(need.specialization, need.grade.value),
        specialization=need.specialization,
        grade=need.grade,
        required_skills=list(need.required_skills or []),
        optional_skills=list(need.optional_skills or []),
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        work_format=need.work_format,
        city=need.city,
        team_description=need.team_description,
        description=need.raw_text,
        published_at=need.published_at or need.created_at,
        match_score=match.score if match else None,
        match_explanation=match.explanation if match else None,
        applied=applied,
    )


async def _applied_chains(db: AsyncSession, candidate_id: int) -> set[int]:
    return set(await db.scalars(select(Application.need_id).where(Application.candidate_id == candidate_id)))


# ---------- кандидат ----------


async def list_vacancies(
    db: AsyncSession,
    user_id: int,
    match: bool,
    specialization: str | None,
    grade: Grade | None,
    q: str | None,
) -> list[VacancyOut]:
    candidate = await candidates_service.get_by_user(db, user_id)
    query = _published(select(HiringNeed))
    if specialization:
        query = query.where(HiringNeed.specialization == specialization)
    if grade:
        query = query.where(HiringNeed.grade == grade)
    needs = list(await db.scalars(query))
    if q:
        needle = q.lower()
        names = {skill.id: skill.name.lower() for skill in get_catalog().skills}
        needs = [
            need
            for need in needs
            if needle in need.title.lower()
            or any(needle in names.get(s, s) for s in [*need.required_skills, *need.optional_skills])
        ]
    applied_ids = await _applied_chains(db, candidate.id)
    chains = await needs_service.version_chains(db, needs)
    matches = await matching_service.matches_for_needs(db, candidate.id, needs) if match else {}
    companies: dict[int, CompanyPublic] = {}
    result = []
    for need in needs:
        applied = bool(applied_ids & set(chains[need.id]))
        result.append(await _vacancy(db, need, matches.get(need.id), applied, companies))
    newest = sorted(result, key=lambda v: v.published_at, reverse=True)
    if not match:
        return newest
    # Сначала подходящие категории кандидата — по тому же score, что видит работодатель (§8.7)
    return sorted(newest, key=lambda v: (v.match_score is None, -(v.match_score or 0)))


async def _get_published(db: AsyncSession, vacancy_id: int) -> HiringNeed:
    need = await db.scalar(_published(select(HiringNeed)).where(HiringNeed.id == vacancy_id))
    if need is None:
        raise NotFoundError("Вакансия не найдена")
    return need


async def get_vacancy(db: AsyncSession, user_id: int, vacancy_id: int) -> VacancyOut:
    candidate = await candidates_service.get_by_user(db, user_id)
    need = await _get_published(db, vacancy_id)
    chain = await needs_service.version_chain_ids(db, need)
    match = await matching_service.match_for(db, need.employer_id, candidate.id, need)
    return await _vacancy(db, need, match, bool(await _applied_chains(db, candidate.id) & set(chain)))


async def apply(
    db: AsyncSession, user_id: int, vacancy_id: int, body: ApplyRequest
) -> ApplicationForCandidate:
    candidate = await candidates_service.get_by_user(db, user_id)
    need = await _get_published(db, vacancy_id)
    if await categories_service.get_current(db, candidate.id) is None:
        raise CategoryRequiredError()
    chain = await needs_service.version_chain_ids(db, need)
    if await _applied_chains(db, candidate.id) & set(chain):
        raise AlreadyAppliedError()
    match = await matching_service.snapshot_for(db, need.employer_id, candidate.id, need)
    application = Application(
        need_id=need.id,
        candidate_id=candidate.id,
        cover_note=body.cover_note,
        match_snapshot=_snapshot(match),
        status=ApplicationStatus.sent,
    )
    db.add(application)
    await db.flush()
    # Отклик сразу раскрывает контакты работодателю — кандидат сам начал общение (ТЗ §2.2)
    await invitations_service.unlock_contacts(
        db, user_id, need.employer_id, candidate.id, UnlockSource.application, application.id
    )
    items = await _for_employer(db, [application])
    if items:
        data = items[0].model_dump(mode="json")
        await integrations_service.enqueue(db, need.employer_id, "application.created", data)
    await db.commit()
    await db.refresh(application)
    return await _for_candidate(db, application)


async def _for_candidate(db: AsyncSession, application: Application) -> ApplicationForCandidate:
    need = await db.get(HiringNeed, application.need_id)
    snapshot = application.match_snapshot or {}
    match_score = snapshot.get("score")
    vacancy = await _vacancy(db, need, None, True)
    if snapshot:
        vacancy.match_score = match_score
        vacancy.match_explanation = Explanation(lines=snapshot.get("lines", []))
    return ApplicationForCandidate(
        id=application.id,
        vacancy=vacancy,
        cover_note=application.cover_note,
        status=application.status,
        created_at=application.created_at,
        viewed_at=application.viewed_at,
        responded_at=application.responded_at,
    )


async def list_mine(db: AsyncSession, user_id: int) -> list[ApplicationForCandidate]:
    candidate = await candidates_service.get_by_user(db, user_id)
    items = await db.scalars(
        select(Application)
        .where(Application.candidate_id == candidate.id)
        .order_by(Application.created_at.desc(), Application.id.desc())
    )
    return [await _for_candidate(db, item) for item in items]


# ---------- работодатель ----------


async def _for_employer(db: AsyncSession, items: list[Application]) -> list[ApplicationForEmployer]:
    briefs = await matching_service.briefs(db, [item.candidate_id for item in items])
    result = []
    for item in items:
        brief = briefs.get(item.candidate_id)
        candidate = await db.get(Candidate, item.candidate_id)
        if brief is None or candidate is None:
            continue
        snapshot = item.match_snapshot or {}
        result.append(
            ApplicationForEmployer(
                id=item.id,
                need_id=item.need_id,
                candidate=brief,
                cover_note=item.cover_note,
                match_score=snapshot.get("score"),
                match_explanation=Explanation(lines=snapshot.get("lines", [])),
                contacts=await matching_service.contacts_of(db, candidate),
                status=item.status,
                created_at=item.created_at,
                viewed_at=item.viewed_at,
                responded_at=item.responded_at,
            )
        )
    return result


async def list_for_need(db: AsyncSession, user_id: int, need_id: int) -> list[ApplicationForEmployer]:
    need = await needs_service.get_own_need(db, user_id, need_id)
    chain = await needs_service.version_chain_ids(db, need)
    items = list(await db.scalars(select(Application).where(Application.need_id.in_(chain))))
    result = await _for_employer(db, items)
    return sorted(result, key=lambda a: (a.match_score is None, -(a.match_score or 0), a.created_at))


async def _own(db: AsyncSession, user_id: int, application_id: int) -> Application:
    employer = await employers_service.get_by_user(db, user_id)
    application = await db.get(Application, application_id)
    need = await db.get(HiringNeed, application.need_id) if application else None
    if application is None or need is None or need.employer_id != employer.id:
        raise NotFoundError("Отклик не найден")
    return application


async def _respond(db: AsyncSession, application: Application) -> ApplicationForEmployer:
    await db.commit()
    await db.refresh(application)
    return (await _for_employer(db, [application]))[0]


async def view(db: AsyncSession, user_id: int, application_id: int) -> ApplicationForEmployer:
    application = await _own(db, user_id, application_id)
    if application.status == ApplicationStatus.sent:
        application.status = ApplicationStatus.viewed
        application.viewed_at = _now()
    return await _respond(db, application)


async def decide(
    db: AsyncSession, user_id: int, application_id: int, status: ApplicationStatus
) -> ApplicationForEmployer:
    application = await _own(db, user_id, application_id)
    if application.status not in OPEN:
        raise ApplicationClosedError()
    now = _now()
    application.status = status
    application.viewed_at = application.viewed_at or now
    application.responded_at = now
    return await _respond(db, application)
