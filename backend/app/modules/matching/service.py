"""Индекс выдачи (§14) и подбор (§8): подборка по потребности, поиск по базе, каталог категорий, карточка."""

import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import any_, case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import (
    ConsentKind,
    Grade,
    InvitationStatus,
    SearchStatus,
    SkillSource,
    SkillStatus,
    WorkFormat,
)
from app.core.errors import AppError, NotFoundError
from app.core.schemas import CategoryRef, Explanation, ExplanationLine, FspBadge
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.candidates import service as candidates_service
from app.modules.candidates.models import Candidate, CandidateExperience, CandidateSkill
from app.modules.candidates.schemas import Contacts, ExperienceItem
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.categories.models import CandidateCategory
from app.modules.fsp import service as fsp_service
from app.modules.fsp.models import FspAchievement
from app.modules.fsp.schemas import FspProfileOut
from app.modules.invitations.models import ContactUnlock, Invitation
from app.modules.matching import market, scoring
from app.modules.matching.models import CandidateSearchIndex
from app.modules.matching.schemas import (
    AcceptanceOut,
    CandidateBrief,
    CandidateCard,
    CandidateMarketOut,
    CandidateMatch,
    CategoryCatalogItem,
    CategoryRecommendation,
    ItscoutExtension,
    JsonResume,
    JsonResumeAward,
    JsonResumeBasics,
    JsonResumeLocation,
    JsonResumeProfile,
    JsonResumeSkill,
    JsonResumeWork,
    MatchComponents,
    RecommendationsOut,
    SalaryBucket,
    SalaryCoverage,
    SalaryMarketCheck,
    TalentSearchOut,
)
from app.modules.needs.models import HiringNeed
from app.modules.resume.pdf import redact_contacts
from app.modules.tasks import service as tasks_service
from app.modules.testing.engine.bank import GRADE_ORDER, get_blueprints
from app.modules.testing.models import TestAttempt
from app.modules.testing.schemas import TopicScore

STATUS_RANK = {status: rank for rank, status in enumerate(candidates_service.STATUS_ORDER)}
FIT_ORDER = {
    "exact": 0,
    "adjacent_grade": 1,
    "adjacent_specialization": 2,
    "adjacent_both": 3,
    "unconfirmed": 4,
}
LEVEL_NAMES = {
    "international": "международные",
    "national": "всероссийские",
    "interregional": "межрегиональные",
    "regional": "региональные",
    "municipal": "муниципальные",
}


def freshness(last_activity: datetime | None, now: datetime) -> float:
    if last_activity is None:
        return 0.0
    return scoring.freshness_from_days((now - last_activity).total_seconds() / 86400)


# ---------- индекс ----------


async def _indexable_without_category(db: AsyncSession, candidate: Candidate) -> bool:
    """Без действующей категории в индекс попадает кандидат с выбранной специализацией (§8.2):
    строка «грейд не подтверждён». Показ в выдаче — за настройкой SHOW_UNCONFIRMED_CANDIDATES."""
    if not candidate.specialization:
        return False
    user = await db.get(User, candidate.user_id)
    return user is not None and user.deleted_at is None


async def refresh_candidate(db: AsyncSession, candidate_id: int) -> None:
    candidate = await db.get(Candidate, candidate_id)
    current = await categories_service.get_current(db, candidate_id) if candidate else None
    if candidate is None or (current is None and not await _indexable_without_category(db, candidate)):
        await db.execute(
            delete(CandidateSearchIndex).where(CandidateSearchIndex.candidate_id == candidate_id)
        )
        return

    now = datetime.now(UTC)
    specialization = current.specialization if current else candidate.specialization
    attempt = await db.get(TestAttempt, current.attempt_id) if current and current.attempt_id else None
    skills: dict[str, str] = {}
    fsp_counts = fsp_service.counts_in_score(candidate)
    fsp_skills = candidates_service.fsp_skills_count(candidate, for_employer=True)
    for skill in await db.scalars(select(CandidateSkill).where(CandidateSkill.candidate_id == candidate_id)):
        if skill.source == SkillSource.fsp and not fsp_skills:
            continue
        # Без действующей категории «проверено тестом» не показываем: грейд и тест не подтверждены
        if skill.source == SkillSource.test and current is None:
            continue
        # Сильнейший источник навыка — по тому же порядку, что в профиле (skill_states, §8.3)
        status = candidates_service.STATUS_BY_SOURCE.get(skill.source, SkillStatus.declared)
        known = skills.get(skill.skill_id)
        if known is None or STATUS_RANK[status] < STATUS_RANK[SkillStatus(known)]:
            skills[skill.skill_id] = status.value
    published = await auth_service.has_active_consent(db, candidate.user_id, ConsentKind.profile_publication)
    # Проверенные решения регулярных заданий тоже освежают профиль и дают approach (§11)
    tasks = await tasks_service.signals(db, candidate_id)
    last_activity = max(
        filter(None, [current.assigned_at if current else None, tasks.last_graded_at]), default=None
    )
    fresh = freshness(last_activity, now)
    approach_scores = [
        s for s in [attempt.approach_score if attempt else None, *tasks.approach_scores] if s is not None
    ]
    approach = round(sum(approach_scores) / len(approach_scores), 4) if approach_scores else None

    row = await db.get(CandidateSearchIndex, candidate_id) or CandidateSearchIndex(candidate_id=candidate_id)
    row.visible = published and candidate.search_status != SearchStatus.hidden
    row.specialization = specialization
    row.grade = current.grade if current else None
    row.theta = current.theta if current else None
    row.percentile = current.percentile if current else None
    row.fsp_score, row.has_fsp, row.max_rank = await fsp_service.candidate_fsp_score(
        db, candidate_id, specialization
    )
    if not fsp_counts:
        row.fsp_score = 0.0
    # Скрытое в настройках приватности в индекс не попадает: иначе его выдадут объяснение и фильтры поиска
    privacy = candidates_service.privacy_of(candidate)
    if not privacy.show_fsp:
        row.fsp_score, row.has_fsp, row.max_rank = 0.0, False, None
    row.fresh = fresh
    row.approach = approach
    row.vps = scoring.vps(row.percentile, row.fsp_score, fresh, approach)
    row.skills_status = skills
    row.topic_scores = (attempt.topic_scores or {}) if attempt else {}
    row.skill_scores = (attempt.skill_scores or {}) if attempt else {}
    row.salary_min = candidate.salary_min if privacy.show_salary else None
    row.work_formats = list(candidate.work_formats or [])
    row.city = candidate.city
    row.relocation = candidate.relocation
    row.hidden_employer_ids = list(candidate.hidden_employer_ids or [])
    row.last_activity_at = last_activity
    row.updated_at = now
    db.add(row)


async def drop_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Убрать кандидата из выдачи совсем — после удаления аккаунта."""
    await db.execute(delete(CandidateSearchIndex).where(CandidateSearchIndex.candidate_id == candidate_id))


async def refresh_category(db: AsyncSession, specialization: str, grade) -> None:
    """Перцентили соседей по категории изменились — обновляем их строки индекса."""
    rows = await db.scalars(
        select(CandidateSearchIndex.candidate_id).where(
            CandidateSearchIndex.specialization == specialization, CandidateSearchIndex.grade == grade
        )
    )
    for candidate_id in list(rows):
        await refresh_candidate(db, candidate_id)


# ---------- общие строительные блоки ----------


@dataclass
class Filters:
    grade: str | None = None
    has_fsp: bool | None = None
    verified_only: bool = False
    salary_max: int | None = None
    work_format: str | None = None
    city: str | None = None
    fresh_days: int | None = None
    apply_hard_filters: bool = True
    group_by: str = "category"
    limit: int | None = None  # None — recommendations.default_limit из matching.yaml


@dataclass
class SearchFilters:
    specialization: str | None = None
    grade: str | None = None
    skills: list[str] = field(default_factory=list)
    verified_only: bool = False
    has_fsp: bool | None = None
    fsp_discipline: str | None = None
    fsp_min_rank: str | None = None
    salary_max: int | None = None
    work_format: str | None = None
    city: str | None = None
    fresh_days: int | None = None
    sort: str = "vps"
    offset: int = 0
    limit: int = 30


def need_spec(need: HiringNeed) -> scoring.NeedSpec:
    return scoring.NeedSpec(
        specialization=need.specialization,
        grade=need.grade.value,
        required=tuple(need.required_skills or ()),
        optional=tuple(need.optional_skills or ()),
        work_format=need.work_format.value if need.work_format else None,
        city=need.city,
        salary_from=need.salary_from,
        salary_to=need.salary_to,
    )


# Справочники загружаются один раз за процесс; словари подписей строим раз на справочник, а не на строку
_names_cache: dict[int, dict[str, str]] = {}
_labels_cache: dict[tuple[int, int, str, str], dict[str, str]] = {}


def _skill_names() -> dict[str, str]:
    catalog = get_catalog()
    names = _names_cache.get(id(catalog))
    if names is None:
        _names_cache.clear()
        names = _names_cache[id(catalog)] = {skill.id: skill.name for skill in catalog.skills}
    return names


def _grade(row: CandidateSearchIndex) -> str | None:
    """None — грейд не подтверждён тестом (§8.2)."""
    return row.grade.value if row.grade is not None else None


def unconfirmed_label(specialization: str) -> str:
    names = {spec.slug: spec.short_name for spec in get_catalog().specializations}
    return f"{names.get(specialization, specialization)} · грейд не подтверждён"


def brief_label(brief: CandidateBrief) -> str:
    """Подпись категории в экспорте: «Backend · Middle» или «Backend · грейд не подтверждён»."""
    return brief.category.label if brief.category is not None else unconfirmed_label(brief.specialization)


def _labels(row: CandidateSearchIndex) -> dict[str, str]:
    blueprints = get_blueprints()
    grade = _grade(row)
    key = (id(get_catalog()), id(blueprints), row.specialization, grade or "")
    labels = _labels_cache.get(key)
    if labels is None:
        labels = {
            **_skill_names(),
            "category": categories_service.category_label(row.specialization, grade)
            if grade
            else unconfirmed_label(row.specialization),
        }
        labels.update({f"topic:{topic}": name for topic, name in blueprints.topic_names.items()})
        _labels_cache[key] = labels
    return labels


async def _best_fsp(db: AsyncSession, candidate_ids: list[int]) -> dict[int, str]:
    if not candidate_ids:
        return {}
    rows = await db.scalars(
        select(FspAchievement)
        .where(FspAchievement.candidate_id.in_(candidate_ids))
        .order_by(FspAchievement.candidate_id, FspAchievement.strength.desc())
    )
    candidates = list(await db.scalars(select(Candidate).where(Candidate.id.in_(candidate_ids))))
    unverified = {c.id for c in candidates if not fsp_service.counts_in_score(c)}
    hidden = {c.id for c in candidates if not candidates_service.privacy_of(c).show_fsp}
    best: dict[int, str] = {}
    for row in rows:
        if row.candidate_id in best or row.candidate_id in hidden:
            continue
        role = f", роль {row.team_role}" if row.team_role else ""
        note = " — владение не подтверждено, в score не учтено" if row.candidate_id in unverified else ""
        best[row.candidate_id] = (
            f"{row.place} место из {row.participants} — {row.competition_name} "
            f"({LEVEL_NAMES.get(row.level, row.level)}{role}){note}"
        )
    return best


async def _fsp_counts(db: AsyncSession, candidate_ids: list[int]) -> dict[int, int]:
    if not candidate_ids:
        return {}
    rows = await db.execute(
        select(FspAchievement.candidate_id, func.count())
        .where(FspAchievement.candidate_id.in_(candidate_ids))
        .group_by(FspAchievement.candidate_id)
    )
    return dict(rows.all())


@dataclass
class _InvitationHistory:
    """Для вероятности принятия (§8.3.1): активные приглашения по компаниям и причины прошлых отказов."""

    active: Counter = field(default_factory=Counter)
    declines: dict[str, int] = field(default_factory=dict)

    def active_except(self, employer_id: int | None) -> int:
        # Своё приглашение компания и так видит статусом; «занятость» кандидата — это чужие приглашения
        return sum(count for employer, count in self.active.items() if employer != employer_id)


async def _invitation_history(db: AsyncSession, candidate_ids: list[int]) -> dict[int, _InvitationHistory]:
    if not candidate_ids:
        return {}
    history: dict[int, _InvitationHistory] = defaultdict(_InvitationHistory)
    active = await db.execute(
        select(Invitation.candidate_id, Invitation.employer_id, func.count())
        .where(
            Invitation.candidate_id.in_(candidate_ids),
            Invitation.status.in_([InvitationStatus.sent, InvitationStatus.viewed]),
            Invitation.expires_at > datetime.now(UTC),
        )
        .group_by(Invitation.candidate_id, Invitation.employer_id)
    )
    for candidate_id, employer_id, count in active.all():
        history[candidate_id].active[employer_id] = count
    declined = await db.execute(
        select(Invitation.candidate_id, Invitation.decline_reason, func.count())
        .where(
            Invitation.candidate_id.in_(candidate_ids),
            Invitation.status == InvitationStatus.declined,
            Invitation.decline_reason.is_not(None),
        )
        .group_by(Invitation.candidate_id, Invitation.decline_reason)
    )
    for candidate_id, reason, count in declined.all():
        history[candidate_id].declines[reason.value] = count
    return history


def _facts(
    row: CandidateSearchIndex,
    best_fsp: str | None,
    now: datetime,
    candidate: Candidate | None = None,
    history: _InvitationHistory | None = None,
    employer_id: int | None = None,
) -> scoring.CandidateFacts:
    days = int((now - row.last_activity_at).total_seconds() // 86400) if row.last_activity_at else None
    return scoring.CandidateFacts(
        search_status=candidate.search_status.value if candidate is not None else None,
        active_invitations=history.active_except(employer_id) if history else 0,
        declines=dict(history.declines) if history else {},
        candidate_id=row.candidate_id,
        specialization=row.specialization,
        grade=_grade(row),
        theta=row.theta,
        percentile=row.percentile,
        topic_scores=row.topic_scores or {},
        skill_scores=row.skill_scores or {},
        skills_status=row.skills_status or {},
        fsp_score=row.fsp_score,
        has_fsp=row.has_fsp,
        fresh=freshness(row.last_activity_at, now),
        fresh_days=days,
        salary_min=row.salary_min,
        work_formats=list(row.work_formats or []),
        city=row.city,
        relocation=row.relocation,
        best_fsp=best_fsp,
    )


def _brief(row: CandidateSearchIndex, candidate: Candidate, fsp_count: int) -> CandidateBrief:
    privacy = candidates_service.privacy_of(candidate)
    last = candidate.last_name or ""
    shown_last = last if privacy.show_last_name else (f"{last[:1]}." if last else "")
    names = _skill_names()
    statuses = row.skills_status or {}
    return CandidateBrief(
        id=candidate.id,
        display_name=f"{candidate.first_name or 'Кандидат'} {shown_last}".strip(),
        category=categories_service.category_ref(row.specialization, row.grade.value)
        if row.grade is not None
        else None,
        specialization=row.specialization,
        grade_confirmed=row.grade is not None,
        percentile=row.percentile,
        # Свежесть — на сейчас; у запасной строки без текущей категории (briefs) fsp_score не заполнен
        vps=scoring.vps(
            row.percentile,
            row.fsp_score or 0.0,
            freshness(row.last_activity_at, datetime.now(UTC)),
            row.approach,
        ),
        city=row.city,
        relocation=row.relocation,
        work_formats=[WorkFormat(value) for value in row.work_formats or []],
        salary_min=row.salary_min if privacy.show_salary else None,
        fsp=FspBadge(
            has_fsp=row.has_fsp and privacy.show_fsp,
            max_rank=row.max_rank if privacy.show_fsp else None,
            achievements_count=fsp_count if privacy.show_fsp else 0,
        ),
        verified_skills=sorted(names.get(s, s) for s, status in statuses.items() if status == "verified"),
        declared_skills=sorted(names.get(s, s) for s, status in statuses.items() if status != "verified"),
        last_activity_at=row.last_activity_at,
    )


def _unconfirmed_shown(requested: bool = True) -> bool:
    return requested and get_settings().show_unconfirmed_candidates


async def _visible_rows(
    db: AsyncSession,
    employer_id: int,
    specs: set[str] | None = None,
    grades: set[str] | None = None,
    ids: list[int] | None = None,
    unconfirmed: bool = False,
) -> list[tuple[CandidateSearchIndex, Candidate]]:
    """unconfirmed — добавить строки «грейд не подтверждён» (§8.2), если они включены настройкой.

    Каталог категорий и экспертная разметка их не просят: там только категории по тесту.
    """
    shown = _unconfirmed_shown(unconfirmed)
    query = (
        select(CandidateSearchIndex, Candidate)
        .join(Candidate, Candidate.id == CandidateSearchIndex.candidate_id)
        .where(CandidateSearchIndex.visible.is_(True))
        .where(~(any_(CandidateSearchIndex.hidden_employer_ids) == employer_id))
    )
    if not shown:
        query = query.where(CandidateSearchIndex.grade.is_not(None))
    if specs:
        query = query.where(CandidateSearchIndex.specialization.in_(specs))
    if grades:
        in_grades = CandidateSearchIndex.grade.in_([Grade(g) for g in grades])
        query = query.where(or_(in_grades, CandidateSearchIndex.grade.is_(None)) if shown else in_grades)
    if ids is not None:
        query = query.where(CandidateSearchIndex.candidate_id.in_(ids))
    return [(row, candidate) for row, candidate in (await db.execute(query)).all()]


def _neighbourhood(need: scoring.NeedSpec) -> tuple[set[str], set[str]]:
    adjacent = next(
        (set(s.adjacent) for s in get_catalog().specializations if s.slug == need.specialization), set()
    )
    index = GRADE_ORDER.index(need.grade)
    grades = {GRADE_ORDER[i] for i in (index - 1, index, index + 1) if 0 <= i < len(GRADE_ORDER)}
    return {need.specialization} | adjacent, grades


def _passes(
    row: CandidateSearchIndex, facts: scoring.CandidateFacts, filters: Filters, need: scoring.NeedSpec
) -> bool:
    if filters.grade and _grade(row) != filters.grade:
        return False
    if filters.has_fsp is not None and row.has_fsp != filters.has_fsp:
        return False
    # Все обязательные навыки сразу тест не проверяет (Next.js, GraphQL…), поэтому достаточно одного
    statuses = row.skills_status or {}
    if filters.verified_only and not any(statuses.get(s) == "verified" for s in need.required):
        return False
    if filters.salary_max and row.salary_min and row.salary_min > filters.salary_max:
        return False
    if filters.work_format and row.work_formats and filters.work_format not in row.work_formats:
        return False
    if filters.city and row.city != filters.city and not row.relocation:
        return False
    return not (
        filters.fresh_days is not None and (facts.fresh_days is None or facts.fresh_days > filters.fresh_days)
    )


def _match(result: scoring.MatchResult, brief: CandidateBrief, shortlisted: bool) -> CandidateMatch:
    return CandidateMatch(
        candidate=brief,
        score=result.score,
        components=MatchComponents(**result.components),
        explanation=Explanation(lines=[ExplanationLine(**line) for line in result.lines]),
        acceptance=_acceptance(result.acceptance),
        shortlisted=shortlisted,
        out_of_filter_reasons=result.out_of_filter,
    )


def _acceptance(value: scoring.Acceptance | None) -> AcceptanceOut | None:
    if value is None:
        return None
    return AcceptanceOut(
        probability=value.probability,
        level=value.level,
        text=value.text,
        affects_score=scoring.get_rules().acceptance.get("rank_weight", 0.0) > 0,
    )


def _sort_key(match: CandidateMatch) -> tuple:
    # Грейд не подтверждён — после всех подтверждённых (§8.2); при равном score — ФСП, затем свежесть (§8.3)
    return (
        not match.candidate.grade_confirmed,
        -match.score,
        -match.components.fsp,
        -match.components.fresh,
        match.candidate.id,
    )


def _coverage(salaries: list[int | None], salary_to: int) -> float | None:
    known = [s for s in salaries if s]
    return round(sum(s <= salary_to for s in known) / len(known), 3) if known else None


async def _employer_id(db: AsyncSession, user_id: int) -> int:
    from app.modules.employers import service as employers_service

    return (await employers_service.get_by_user(db, user_id)).id


# ---------- подборка по потребности ----------


@dataclass
class _Scored:
    row: CandidateSearchIndex
    facts: scoring.CandidateFacts
    result: scoring.MatchResult
    brief: CandidateBrief


# Оценки кандидатов по потребности в памяти процесса: ключ меняется при правке потребности и любом
# пересчёте индекса выдачи, TTL — страховка для свежести (§8.3); фильтры, шорт-лист и статусы — поверх
_scored_cache: dict[tuple, tuple[float, list[_Scored]]] = {}


async def _index_stamp(db: AsyncSession) -> tuple:
    stamp = await db.execute(
        select(func.count(), func.max(CandidateSearchIndex.updated_at)).where(
            CandidateSearchIndex.visible.is_(True)
        )
    )
    return tuple(stamp.one())


async def _scored_pool(
    db: AsyncSession, need: HiringNeed, employer_id: int, spec: scoring.NeedSpec
) -> list[_Scored]:
    settings = get_settings()
    ttl = settings.recommendations_cache_seconds
    key = (need.id, need.version, employer_id, await _index_stamp(db))
    cached = _scored_cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < ttl:
        return cached[1]
    specs, grades = _neighbourhood(spec)
    rows = await _visible_rows(db, employer_id, specs, grades, unconfirmed=True)
    ids = [row.candidate_id for row, _ in rows]
    best = await _best_fsp(db, ids)
    counts = await _fsp_counts(db, ids)
    history = await _invitation_history(db, ids)
    now = datetime.now(UTC)
    scored = []
    for row, candidate in rows:
        facts = _facts(
            row, best.get(row.candidate_id), now, candidate, history.get(row.candidate_id), employer_id
        )
        result = scoring.evaluate(facts, spec, _labels(row))
        if result is not None:
            scored.append(
                _Scored(row, facts, result, _brief(row, candidate, counts.get(row.candidate_id, 0)))
            )
    if ttl > 0:
        if len(_scored_cache) >= settings.recommendations_cache_size:
            _scored_cache.pop(next(iter(_scored_cache)))
        _scored_cache[key] = (time.monotonic(), scored)
    return scored


async def recommendations(
    db: AsyncSession, user_id: int, need_id: int, filters: Filters
) -> RecommendationsOut:
    from app.modules.needs import service as needs_service

    need = await needs_service.get_own_need(db, user_id, need_id)
    employer_id = await _employer_id(db, user_id)
    spec = need_spec(need)
    scored = await _scored_pool(db, need, employer_id, spec)
    pinned = await needs_service.shortlist_candidate_ids(db, need.id)
    shortlist_ids = set(pinned)
    ids = [item.row.candidate_id for item in scored]

    matched: list[CandidateMatch] = []
    unconfirmed: list[CandidateMatch] = []
    outside: list[CandidateMatch] = []
    shortlist: list[CandidateMatch] = []
    by_category: dict[tuple[str, str], list[CandidateSearchIndex]] = defaultdict(list)
    fit_of: dict[int, str] = {}
    for item in scored:
        row, facts, result = item.row, item.facts, item.result
        if row.grade is not None:
            by_category[(row.specialization, row.grade.value)].append(row)
        fit_of[row.candidate_id] = result.fit
        match = _match(result, item.brief.model_copy(), row.candidate_id in shortlist_ids)
        if match.shortlisted:
            shortlist.append(match)
        if not _passes(row, facts, filters, spec):
            continue
        if filters.apply_hard_filters and result.out_of_filter:
            outside.append(match)
        else:
            # §8.2: без подтверждённого грейда — отдельный блок после всех подтверждённых, score не смешиваем
            (matched if row.grade is not None else unconfirmed).append(match)

    if filters.group_by == "category":
        matched.sort(key=lambda m: (FIT_ORDER[fit_of[m.candidate.id]], *_sort_key(m)))
    else:
        matched.sort(key=_sort_key)
    unconfirmed.sort(key=_sort_key)
    outside.sort(key=_sort_key)
    shortlist.sort(key=_sort_key)
    # §8.1 п.4: закреплённый остаётся в шорт-листе при любой правке. Кто после правки вне категорий
    # потребности, для того score не определён — показываем карточкой, с теми же проверками видимости
    in_pool = set(ids)
    dropped = [cid for cid in pinned if cid not in in_pool]
    visible = {
        row.candidate_id: (row, c)
        for row, c in await _visible_rows(db, employer_id, ids=dropped, unconfirmed=True)
    }
    counts = await _fsp_counts(db, list(visible))
    shortlist_outside = [_brief(*visible[cid], counts.get(cid, 0)) for cid in dropped if cid in visible]
    statuses = await invitation_statuses(db, employer_id, ids)
    for match in (*matched, *unconfirmed, *outside, *shortlist):
        match.invitation_status = statuses.get(match.candidate.id)
    limit = filters.limit or scoring.get_rules().recommendations["default_limit"]
    return RecommendationsOut(
        need_id=need.id,
        need_version=need.version,
        categories=_category_cards(by_category, spec),
        candidates=matched[:limit],
        unconfirmed=unconfirmed[:limit],
        out_of_filter=outside[:20],
        shortlist=shortlist,
        shortlist_outside=shortlist_outside,
        total=len(matched),
        unconfirmed_total=len(unconfirmed),
    )


def _category_cards(by_category: dict, spec: scoring.NeedSpec) -> list[CategoryRecommendation]:
    cards = []
    for (specialization, grade), rows in by_category.items():
        fit = scoring.category_fit(specialization, grade, spec)
        coverage = _coverage([row.salary_min for row in rows], spec.salary_to)
        higher = GRADE_ORDER.index(grade) > GRADE_ORDER.index(spec.grade)
        reason = {
            "exact": "Точное совпадение",
            "adjacent_grade": "Грейд выше" if higher else "Грейд ниже",
            "adjacent_specialization": "Смежная специализация",
            "adjacent_both": "Смежная специализация и соседний грейд",
        }[fit]
        if coverage is not None:
            reason += f" · ваша вилка покрывает ожидания {round(coverage * 100)}%"
        cards.append(
            CategoryRecommendation(
                category=categories_service.category_ref(specialization, grade),
                fit=fit,
                candidates_count=len(rows),
                with_fsp_count=sum(row.has_fsp for row in rows),
                salary_coverage=coverage,
                reason=reason,
            )
        )
    return sorted(cards, key=lambda card: (FIT_ORDER[card.fit], -card.candidates_count))


MARKET_MESSAGES = {
    "employer": {
        "ok": (
            "Вилка в рынке: покрывает ожидания {coverage}% кандидатов категории, "
            "медиана ожиданий — {median} ₽."
        ),
        "below_market": (
            "Вилка ниже рынка: покрывает ожидания только {coverage}% кандидатов категории "
            "(медиана {median} ₽). Принятых приглашений и откликов будет мало."
        ),
        "suspicious_high": (
            "Нижняя граница вилки вдвое выше медианы ожиданий категории ({median} ₽). Проверьте сумму: "
            "кандидаты увидят пометку «вилка выше рынка — уточните условия»."
        ),
        "unknown": "Пока мало данных об ожиданиях в категории, чтобы сравнить вилку с рынком.",
    },
    "candidate": {
        "ok": "Вилка в рынке: покрывает ожидания {coverage}% кандидатов вашей категории.",
        "below_market": (
            "Вилка ниже рынка: покрывает ожидания только {coverage}% кандидатов вашей категории "
            "(медиана {median} ₽)."
        ),
        "suspicious_high": (
            "Вилка заметно выше рынка вашей категории (медиана ожиданий {median} ₽) — "
            "уточните условия до собеседования."
        ),
        "unknown": "Сравнить вилку с рынком вашей категории пока не на чем.",
    },
}


async def category_expectations(db: AsyncSession, specialization: str, grade: str) -> list[int]:
    return list(
        await db.scalars(
            select(CandidateSearchIndex.salary_min).where(
                CandidateSearchIndex.visible.is_(True),
                CandidateSearchIndex.specialization == specialization,
                CandidateSearchIndex.grade == grade,
                CandidateSearchIndex.salary_min.is_not(None),
            )
        )
    )


def market_check(
    expectations: list[int], salary_from: int, salary_to: int, audience: str
) -> SalaryMarketCheck:
    result = scoring.salary_market(expectations, salary_from, salary_to)
    message = MARKET_MESSAGES[audience][result.verdict].format(
        coverage=round((result.coverage or 0) * 100),
        median=f"{result.median or 0:,}".replace(",", " "),
    )
    return SalaryMarketCheck(
        verdict=result.verdict,
        coverage=result.coverage,
        median_expectation=result.median,
        message=message,
    )


async def salary_market_for_candidate(
    db: AsyncSession, candidate_id: int, salary_from: int, salary_to: int
) -> SalaryMarketCheck | None:
    """Вилка приглашения против ожиданий категории кандидата — пометка в приглашении."""
    row = await db.get(CandidateSearchIndex, candidate_id)
    if row is None or row.grade is None:
        return None
    expectations = await category_expectations(db, row.specialization, row.grade)
    return market_check(expectations, salary_from, salary_to, "candidate")


async def salary_coverage(db: AsyncSession, user_id: int, need_id: int) -> SalaryCoverage:
    from app.modules.needs import service as needs_service

    need = await needs_service.get_own_need(db, user_id, need_id)
    salaries = await category_expectations(db, need.specialization, need.grade)
    step = scoring.get_rules().recommendations["salary_bucket"]
    buckets = Counter((salary // step) * step for salary in salaries)
    return SalaryCoverage(
        category=categories_service.category_ref(need.specialization, need.grade.value),
        coverage=_coverage(salaries, need.salary_to) or 0.0,
        median_expectation=int(median(salaries)) if salaries else None,
        histogram=[
            SalaryBucket(salary_from=bucket, salary_to=bucket + step, count=count)
            for bucket, count in sorted(buckets.items())
        ],
        market=market_check(salaries, need.salary_from, need.salary_to, "employer"),
    )


async def market_for_candidate(db: AsyncSession, user_id: int) -> CandidateMarketOut:
    """«Рынок вашей категории»: агрегаты по действующим потребностям без имён компаний (§8.5)."""
    from app.modules.needs import service as needs_service

    candidate = await candidates_service.get_by_user(db, user_id)
    row = await db.get(CandidateSearchIndex, candidate.id)
    if row is None or row.grade is None:
        return CandidateMarketOut(
            category=None,
            groups=[],
            scope=None,
            scope_needs=0,
            suppressed=True,
            min_needs=int(scoring.get_rules().insights["min_needs"]),
            salary=None,
            skills=[],
            matching_needs=None,
            suggestions=[],
        )
    facts = _facts(row, None, datetime.now(UTC))
    # Неопубликованные потребности — внутренние планы компаний; учитываются только по настройке (агрегатами)
    include_unpublished = bool(scoring.get_rules().insights.get("include_unpublished", 0))
    pool = [
        market.MarketNeed(employer_id=need.employer_id, published=need.published, spec=need_spec(need))
        for need in await needs_service.active_latest_needs(db)
        if need.published or include_unpublished
    ]
    result = market.insights(facts, pool, _skill_names(), set(scoring.skill_topics(row.specialization)))
    result.category = categories_service.category_ref(row.specialization, row.grade.value)
    return result


async def match_for(
    db: AsyncSession, employer_id: int, candidate_id: int, need: HiringNeed, *, unconfirmed: bool = True
) -> CandidateMatch | None:
    """Совпадение одного кандидата с потребностью — для карточки и снимка в приглашении.

    unconfirmed=False — без подтверждённого грейда совпадения нет (вакансии в кабинете кандидата, §8.7).
    """
    return await _match_one(db, employer_id, candidate_id, lambda row: need_spec(need), unconfirmed)


async def matches_for_needs(
    db: AsyncSession, candidate_id: int, needs: list[HiringNeed]
) -> dict[int, CandidateMatch | None]:
    """match_for для одного кандидата и многих потребностей: данные кандидата читаются один раз."""
    row = await db.get(CandidateSearchIndex, candidate_id)
    candidate = await db.get(Candidate, candidate_id)
    # Кабинет кандидата: без подтверждённого грейда совпадения с вакансиями не считаем (§8.7)
    if row is None or row.grade is None or candidate is None:
        return dict.fromkeys((need.id for need in needs), None)
    best = await _best_fsp(db, [candidate_id])
    counts = await _fsp_counts(db, [candidate_id])
    history = (await _invitation_history(db, [candidate_id])).get(candidate_id)
    now = datetime.now(UTC)
    brief = _brief(row, candidate, counts.get(candidate_id, 0))
    found: dict[int, CandidateMatch | None] = {}
    for need in needs:
        facts = _facts(row, best.get(candidate_id), now, candidate, history, need.employer_id)
        result = scoring.evaluate(facts, need_spec(need), _labels(row))
        found[need.id] = _match(result, brief.model_copy(), False) if result is not None else None
    return found


async def snapshot_for(
    db: AsyncSession, employer_id: int, candidate_id: int, need: HiringNeed | None
) -> CandidateMatch | None:
    """Снимок «почему вы» для приглашения: по потребности, а без неё (или вне её категорий) — по категории.

    Без подтверждённого грейда — по специализации: первая строка объяснения говорит, что грейд не подтверждён.
    """
    if need is not None:
        match = await match_for(db, employer_id, candidate_id, need)
        if match is not None:
            return match
    return await _match_one(
        db,
        employer_id,
        candidate_id,
        lambda row: scoring.NeedSpec(specialization=row.specialization, grade=_grade(row) or ""),
    )


async def _match_one(
    db: AsyncSession,
    employer_id: int,
    candidate_id: int,
    spec_of: Callable[[CandidateSearchIndex], scoring.NeedSpec],
    unconfirmed: bool = True,
) -> CandidateMatch | None:
    row = await db.get(CandidateSearchIndex, candidate_id)
    candidate = await db.get(Candidate, candidate_id)
    if row is None or candidate is None or (row.grade is None and not unconfirmed):
        return None
    best = await _best_fsp(db, [candidate_id])
    history = (await _invitation_history(db, [candidate_id])).get(candidate_id)
    facts = _facts(row, best.get(candidate_id), datetime.now(UTC), candidate, history, employer_id)
    result = scoring.evaluate(facts, spec_of(row), _labels(row))
    if result is None:
        return None
    counts = await _fsp_counts(db, [candidate_id])
    return _match(result, _brief(row, candidate, counts.get(candidate_id, 0)), False)


async def briefs(db: AsyncSession, candidate_ids: list[int]) -> dict[int, CandidateBrief]:
    """Обезличенные карточки для списков приглашений и откликов.

    Кандидат мог с тех пор потерять текущую категорию (строки индекса нет) — тогда берём последнюю известную,
    а если категории не было — специализацию с пометкой «грейд не подтверждён».
    """
    ids = list(set(candidate_ids))
    if not ids:
        return {}
    rows = {
        row.candidate_id: row
        for row in await db.scalars(
            select(CandidateSearchIndex).where(CandidateSearchIndex.candidate_id.in_(ids))
        )
    }
    candidates = list(await db.scalars(select(Candidate).where(Candidate.id.in_(ids))))
    counts = await _fsp_counts(db, ids)
    result: dict[int, CandidateBrief] = {}
    for candidate in candidates:
        row = rows.get(candidate.id) or await _detached_row(db, candidate)
        if row is not None:
            result[candidate.id] = _brief(row, candidate, counts.get(candidate.id, 0))
    return result


async def _detached_row(db: AsyncSession, candidate: Candidate) -> CandidateSearchIndex | None:
    last = await db.scalar(
        select(CandidateCategory)
        .where(CandidateCategory.candidate_id == candidate.id)
        .order_by(CandidateCategory.assigned_at.desc())
        .limit(1)
    )
    specialization = last.specialization if last is not None else candidate.specialization
    if specialization is None:
        return None
    # В сессию не добавляется: только источник полей для _brief
    return CandidateSearchIndex(
        candidate_id=candidate.id,
        specialization=specialization,
        grade=last.grade if last is not None else None,
        percentile=None,
        vps=0.0,
        city=candidate.city,
        relocation=candidate.relocation,
        work_formats=list(candidate.work_formats or []),
        salary_min=candidate.salary_min if candidates_service.privacy_of(candidate).show_salary else None,
        has_fsp=False,
        max_rank=None,
        skills_status={},
        last_activity_at=last.assigned_at if last is not None else None,
    )


async def reachable(db: AsyncSession, employer_id: int, candidate_id: int) -> bool:
    """Работодатель может обратиться к кандидату: тот виден компании в поиске или контакты уже открыты."""
    row = await db.get(CandidateSearchIndex, candidate_id)
    visible = (
        row is not None
        and row.visible
        and (row.grade is not None or _unconfirmed_shown())
        and employer_id not in (row.hidden_employer_ids or [])
    )
    return visible or await contacts_unlocked(db, employer_id, candidate_id)


async def invitation_statuses(
    db: AsyncSession, employer_id: int, candidate_ids: list[int]
) -> dict[int, InvitationStatus]:
    """Статус последнего приглашения компании каждому кандидату — чтобы не приглашать повторно."""
    if not candidate_ids:
        return {}
    rows = await db.execute(
        select(Invitation.candidate_id, Invitation.status)
        .where(Invitation.employer_id == employer_id, Invitation.candidate_id.in_(candidate_ids))
        .order_by(Invitation.created_at.desc(), Invitation.id.desc())
    )
    latest: dict[int, InvitationStatus] = {}
    for candidate_id, status in rows.all():
        latest.setdefault(candidate_id, status)
    return latest


# ---------- экспертная разметка (§12.2) ----------


async def rank_for_need(db: AsyncSession, need: HiringNeed) -> list[tuple[int, int]]:
    """Порядок подборки по умолчанию: по категориям, внутри — по score, «вне фильтров» в конце."""
    spec = need_spec(need)
    specs, grades = _neighbourhood(spec)
    rows = await _visible_rows(db, need.employer_id, specs, grades)
    ids = [row.candidate_id for row, _ in rows]
    best = await _best_fsp(db, ids)
    history = await _invitation_history(db, ids)
    now = datetime.now(UTC)
    ranked = []
    for row, candidate in rows:
        facts = _facts(
            row, best.get(row.candidate_id), now, candidate, history.get(row.candidate_id), need.employer_id
        )
        result = scoring.evaluate(facts, spec, _labels(row))
        if result is None:
            continue
        key = (bool(result.out_of_filter), FIT_ORDER[result.fit], -result.score, -facts.fsp_score)
        ranked.append((key, row.candidate_id, result.score))
    return [(candidate_id, score) for _key, candidate_id, score in sorted(ranked)]


async def keyword_rank(db: AsyncSession, need: HiringNeed) -> list[int]:
    """Базовая линия «как на обычной площадке»: специализация и счёт навыков профиля, без теста и score."""
    rows = await _visible_rows(db, need.employer_id, {need.specialization})
    required, optional = list(need.required_skills or []), list(need.optional_skills or [])

    def keywords(row: CandidateSearchIndex) -> float:
        skills = row.skills_status or {}
        return sum(1.0 for s in required if s in skills) + sum(0.3 for s in optional if s in skills)

    ordered = sorted(rows, key=lambda pair: (-keywords(pair[0]), pair[0].candidate_id))
    return [row.candidate_id for row, _ in ordered]


# ---------- каталог и поиск ----------


async def cities(db: AsyncSession, user_id: int) -> list[str]:
    rows = await _visible_rows(db, await _employer_id(db, user_id), unconfirmed=True)
    counts = Counter(row.city.strip() for row, _ in rows if row.city and row.city.strip())
    return [city for city, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


async def categories_catalog(db: AsyncSession, user_id: int) -> list[CategoryCatalogItem]:
    rows = await _visible_rows(db, await _employer_id(db, user_id))
    groups: dict[tuple[str, str], list[CandidateSearchIndex]] = defaultdict(list)
    for row, _ in rows:
        groups[(row.specialization, row.grade.value)].append(row)
    spec_order = [spec.slug for spec in get_catalog().specializations]
    items = []
    for (specialization, grade), members in groups.items():
        percentiles = [m.percentile for m in members if m.percentile is not None]
        salaries = [m.salary_min for m in members if m.salary_min]
        items.append(
            CategoryCatalogItem(
                category=categories_service.category_ref(specialization, grade),
                candidates_count=len(members),
                with_fsp_count=sum(m.has_fsp for m in members),
                median_percentile=round(median(percentiles), 3) if percentiles else None,
                median_salary=int(median(salaries)) if salaries else None,
            )
        )
    return sorted(
        items,
        key=lambda i: (
            spec_order.index(i.category.specialization),
            GRADE_ORDER.index(i.category.grade.value),
        ),
    )


def _visible_query(employer_id: int):
    query = (
        select(CandidateSearchIndex)
        .where(CandidateSearchIndex.visible.is_(True))
        .where(~(any_(CandidateSearchIndex.hidden_employer_ids) == employer_id))
    )
    return query if _unconfirmed_shown() else query.where(CandidateSearchIndex.grade.is_not(None))


def _search_conditions(filters: SearchFilters, now: datetime) -> list:
    """Фильтры поиска по базе в SQL: выборка, сортировка и страница — в Postgres, а не в Python."""
    index = CandidateSearchIndex
    conditions = []
    if filters.specialization:
        conditions.append(index.specialization == filters.specialization)
    if filters.grade:
        conditions.append(index.grade == Grade(filters.grade))
    if filters.skills:
        conditions.append(index.skills_status.has_all(array(filters.skills)))
        if filters.verified_only:
            conditions.append(index.skills_status.contains(dict.fromkeys(filters.skills, "verified")))
    if filters.has_fsp is not None:
        conditions.append(index.has_fsp.is_(filters.has_fsp))
    if filters.fsp_discipline:
        # Скрытый ФСП считается отсутствующим и для фильтров (§6.4): has_fsp в индексе это уже учёл
        conditions.append(index.has_fsp.is_(True))
        conditions.append(
            index.candidate_id.in_(
                select(FspAchievement.candidate_id).where(FspAchievement.discipline == filters.fsp_discipline)
            )
        )
    if filters.fsp_min_rank:
        rank_order = get_catalog().rules.fsp.rank_order
        if filters.fsp_min_rank not in rank_order:
            raise AppError(f"Неизвестный разряд: допустимы {', '.join(rank_order)}", code="unknown_rank")
        conditions.append(index.max_rank.in_(rank_order[rank_order.index(filters.fsp_min_rank) :]))
    if filters.salary_max:
        conditions.append(or_(index.salary_min.is_(None), index.salary_min <= filters.salary_max))
    if filters.work_format:
        conditions.append(
            or_(
                index.work_formats.is_(None),
                func.cardinality(index.work_formats) == 0,
                filters.work_format == any_(index.work_formats),
            )
        )
    if filters.city:
        conditions.append(or_(index.city == filters.city, index.relocation.is_(True)))
    if filters.fresh_days is not None:
        # Как (now − last).days ≤ fresh_days: целых дней не больше заданного
        conditions.append(index.last_activity_at > now - timedelta(days=filters.fresh_days + 1))
    return conditions


def _live_vps():
    """VPS для сортировки поиска со свежестью на момент запроса: в индексе она застыла на момент пересчёта.

    Та же формула, что scoring.vps (§8.3).
    """
    index = CandidateSearchIndex
    rules = scoring.get_rules()
    w = rules.vps_weights
    days = func.extract("epoch", func.now() - index.last_activity_at) / 86400
    fresh = case(
        (index.last_activity_at.is_(None), 0.0),
        else_=func.power(0.5, days / rules.freshness["half_life_days"]),
    )
    percentile = func.coalesce(index.percentile, 0.0)
    base = w["percentile"] * percentile + w["fsp"] * index.fsp_score + w["fresh"] * fresh
    return case(
        (index.approach.is_(None), base / (1 - w["approach"])),
        else_=base + w["approach"] * index.approach,
    )


SEARCH_ORDER = {
    "vps": (_live_vps().desc(),),
    "percentile": (func.coalesce(CandidateSearchIndex.percentile, 0.0).desc(),),
    "fresh": (CandidateSearchIndex.last_activity_at.desc().nulls_last(),),
}


async def search(db: AsyncSession, user_id: int, filters: SearchFilters) -> TalentSearchOut:
    employer_id = await _employer_id(db, user_id)
    query = _visible_query(employer_id).where(*_search_conditions(filters, datetime.now(UTC)))
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = SEARCH_ORDER.get(filters.sort, SEARCH_ORDER["vps"])
    page_query = (
        select(CandidateSearchIndex, Candidate)
        .join(Candidate, Candidate.id == CandidateSearchIndex.candidate_id)
        .where(
            CandidateSearchIndex.candidate_id.in_(query.with_only_columns(CandidateSearchIndex.candidate_id))
        )
        # Грейд не подтверждён — после всех подтверждённых при любой сортировке (§8.2)
        .order_by(CandidateSearchIndex.grade.is_(None), *order, CandidateSearchIndex.candidate_id)
        .offset(filters.offset)
        .limit(filters.limit)
    )
    page = (await db.execute(page_query)).all()
    counts = await _fsp_counts(db, [row.candidate_id for row, _ in page])
    return TalentSearchOut(
        items=[_brief(row, candidate, counts.get(row.candidate_id, 0)) for row, candidate in page],
        total=total,
    )


# ---------- карточка кандидата ----------


async def contacts_unlocked(db: AsyncSession, employer_id: int, candidate_id: int) -> bool:
    unlock = await db.scalar(
        select(ContactUnlock.candidate_id).where(
            ContactUnlock.employer_id == employer_id, ContactUnlock.candidate_id == candidate_id
        )
    )
    return unlock is not None


async def contacts_of(db: AsyncSession, candidate: Candidate) -> Contacts:
    user = await db.get(User, candidate.user_id)
    if user is None or user.deleted_at is not None:
        # У удалённого аккаунта служебный адрес в зоне .invalid: EmailStr его не пропустит, и писать некуда
        return Contacts(full_name="Аккаунт удалён")
    full_name = " ".join(filter(None, [candidate.last_name, candidate.first_name, candidate.middle_name]))
    return Contacts(
        full_name=full_name or "Кандидат",
        email=candidate.contact_email or user.email,
        phone=candidate.phone,
        telegram=candidate.telegram,
    )


async def candidate_card(
    db: AsyncSession, user_id: int, candidate_id: int, need_id: int | None
) -> CandidateCard:
    employer_id = await _employer_id(db, user_id)
    need = None
    if need_id is not None:
        from app.modules.needs import service as needs_service

        need = await needs_service.get_own_need(db, user_id, need_id)
    return await _card(db, employer_id, candidate_id, need, blind=False)


JSON_RESUME_LEVELS = {
    "verified": "проверено тестом",
    "fsp_confirmed": "подтверждено ФСП",
    "task_confirmed": "подтверждено заданием",
    "declared": "заявлено кандидатом",
}


async def json_resume(db: AsyncSession, user_id: int, candidate_id: int, need_id: int | None) -> JsonResume:
    """Карточка кандидата в формате JSON Resume для ATS: те же правила видимости, что у карточки."""
    card = await candidate_card(db, user_id, candidate_id, need_id)
    brief, contacts = card.brief, card.contacts
    profiles = []
    if contacts and contacts.telegram:
        profiles.append(JsonResumeProfile(network="Telegram", username=contacts.telegram.lstrip("@")))
    fsp = card.fsp if card.fsp and card.fsp.linked else None
    return JsonResume(
        basics=JsonResumeBasics(
            name=contacts.full_name if contacts else brief.display_name,
            label=brief_label(brief),
            email=contacts.email if contacts else None,
            phone=contacts.phone if contacts else None,
            summary=card.about,
            location=JsonResumeLocation(city=brief.city),
            profiles=profiles,
        ),
        work=[
            JsonResumeWork(
                name=(item.company or None) if card.contacts_unlocked else None,
                position=item.position,
                startDate=item.started_on.isoformat() if item.started_on else None,
                endDate=item.ended_on.isoformat() if item.ended_on else None,
                summary=item.description,
            )
            for item in card.experience
        ],
        skills=[
            JsonResumeSkill(
                name=skill.name, level=JSON_RESUME_LEVELS[skill.status], keywords=[skill.skill_id]
            )
            for skill in card.skills
        ],
        awards=[
            JsonResumeAward(
                title=f"{item.place} место из {item.participants}",
                date=item.held_on.isoformat(),
                awarder=item.competition_name,
                summary=f"Федерация спортивного программирования, {item.discipline}",
            )
            for item in (fsp.achievements if fsp else [])
        ],
        **{
            "x-itscout": ItscoutExtension(
                candidate_id=brief.id,
                category=brief.category,
                grade_confirmed=brief.grade_confirmed,
                percentile=brief.percentile,
                topic_scores=card.topic_scores,
                fsp_ranks=[f"{rank.rank} · {rank.discipline}" for rank in (fsp.ranks if fsp else [])],
                match=card.match,
                contacts_unlocked=card.contacts_unlocked,
                generated_at=datetime.now(UTC),
            )
        },
    )


async def _fsp_for_employer(db: AsyncSession, candidate: Candidate, unlocked: bool) -> FspProfileOut:
    """Достижения ФСП видны сразу, а номер ФСП ID — только после раскрытия контактов: по нему человека
    находят в публичном рейтинге федерации."""
    profile = await fsp_service.profile(db, candidate)
    if not unlocked:
        profile.fsp_id = None
    return profile


async def blind_card(db: AsyncSession, employer_id: int, candidate_id: int) -> CandidateCard:
    """Обезличенная карточка без score, объяснения и статусов — для экспертной разметки (§12.2)."""
    return await _card(db, employer_id, candidate_id, None, blind=True)


async def _card(
    db: AsyncSession, employer_id: int, candidate_id: int, need: HiringNeed | None, *, blind: bool
) -> CandidateCard:
    row = await db.get(CandidateSearchIndex, candidate_id)
    candidate = await db.get(Candidate, candidate_id)
    unlocked = not blind and candidate is not None and await contacts_unlocked(db, employer_id, candidate_id)
    # Кандидат, скрывший профиль, остаётся доступен только тем, кому уже открыл контакты
    if row is None or candidate is None or not await reachable(db, employer_id, candidate_id):
        raise NotFoundError("Кандидат не найден")

    privacy = candidates_service.privacy_of(candidate)
    counts = await _fsp_counts(db, [candidate_id])
    experience = list(
        await db.scalars(
            select(CandidateExperience)
            .where(CandidateExperience.candidate_id == candidate_id)
            .order_by(CandidateExperience.started_on.desc().nulls_last())
        )
    )
    topic_names = get_blueprints().topic_names
    history = list(
        await db.scalars(
            select(CandidateCategory)
            .where(CandidateCategory.candidate_id == candidate_id)
            .order_by(CandidateCategory.assigned_at)
        )
    )
    match = await match_for(db, employer_id, candidate_id, need) if need is not None else None
    statuses = {} if blind else await invitation_statuses(db, employer_id, [candidate_id])
    if match is not None:
        match.invitation_status = statuses.get(candidate_id)
        if need is not None and not blind:
            from app.modules.needs import service as needs_service

            match.shortlisted = candidate_id in await needs_service.shortlist_candidate_ids(db, need.id)
    current = await categories_service.get_current(db, candidate_id)
    approach_answers = []
    integrity = None
    evidence = None
    if current is not None and current.attempt_id is not None:
        from app.modules.testing import service as testing_service

        approach_answers = await testing_service.open_answers(db, current.attempt_id)
        # Обезличенной карточке эксперта сигналы не нужны: она для разметки релевантности (§12.2)
        integrity = None if blind else await testing_service.integrity_signals(db, current.attempt_id)
        if not blind:
            evidence = await testing_service.grade_evidence(
                db, current.attempt_id, current.grade.value, current.valid_until
            )
    # До раскрытия контактов свободный текст не должен их выдавать (инвариант contact_unlocks)
    hide = (lambda text: text) if unlocked else redact_contacts
    for answer in approach_answers:
        answer.answer = hide(answer.answer) or ""

    return CandidateCard(
        brief=_brief(row, candidate, counts.get(candidate_id, 0)),
        about=hide(candidate.about),
        experience_years=float(candidate.experience_years)
        if candidate.experience_years is not None
        else None,
        roles=list(candidate.roles or []),
        industries_exp=list(candidate.industries_exp or []),
        soft_skills=list(candidate.soft_skills or []),
        experience=[
            ExperienceItem(
                company=item.company if unlocked else "Компания скрыта до контакта",
                position=item.position,
                started_on=item.started_on,
                ended_on=item.ended_on,
                description=hide(item.description),
            )
            for item in experience
        ],
        skills=await candidates_service.skill_states(db, candidate_id, for_employer=True),
        topic_scores=[
            TopicScore(
                topic=topic,
                name=topic_names.get(topic, topic),
                score=s["score"],
                items=s["items"],
                level=get_blueprints().topic_level(s["score"], s["items"]),
            )
            for topic, s in sorted((row.topic_scores or {}).items())
        ],
        approach_answers=approach_answers,
        integrity=integrity,
        grade_evidence=evidence,
        fsp=await _fsp_for_employer(db, candidate, unlocked) if privacy.show_fsp and row.has_fsp else None,
        contacts_unlocked=unlocked,
        contacts=await contacts_of(db, candidate) if unlocked else None,
        match=match,
        invitation_status=statuses.get(candidate_id),
        grade_history=[
            CategoryRef(**categories_service.category_ref(item.specialization, item.grade.value).model_dump())
            for item in history
        ],
    )
