"""Регулярные задания (§11): работодатель создаёт, кандидату категории предлагается одно в неделю.

Автопроверяемое задание — экземпляр шаблона банка, проверяется тем же кодом, что и тест; верное
решение подтверждает навыки шаблона (статус task_confirmed). Задание на подход оценивается по
чек-листу: LLM только отмечает критерии, долю выполненных считает код; без LLM — оценка работодателя.
Грейд и категорию задания не меняют: их определяет только тест.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import yaml
from pydantic import BaseModel
from sqlalchemy import any_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm
from app.core.enums import AssignmentStatus, GradedBy, SkillSource, TaskKind
from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.needs import service as needs_service
from app.modules.resume.pdf import redact_contacts
from app.modules.survey import service as survey_service
from app.modules.tasks.models import EmployerTask, TaskAssignment
from app.modules.tasks.schemas import (
    EmployerTaskCreate,
    EmployerTaskOut,
    TaskAssignmentForCandidate,
    TaskRating,
    TaskSubmissionForEmployer,
    TaskSubmit,
    TaskTemplateOption,
)
from app.modules.testing.engine.bank import CONTENT_DIR, GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.model import Template
from app.modules.testing.engine.render import render
from app.modules.testing.engine.scoring import score as score_response
from app.modules.testing.schemas import AnswerPayload, CurrentItem, ItemOption


class TaskConfig(BaseModel):
    offer_interval_days: int
    due_days: int
    confirm_min_score: float
    rubric_max: int


@lru_cache
def get_config() -> TaskConfig:
    with (CONTENT_DIR / "tasks.yaml").open(encoding="utf-8") as file:
        return TaskConfig.model_validate(yaml.safe_load(file))


class TaskValidationError(AppError):
    status_code = 422
    code = "invalid_task"


def _now() -> datetime:
    return datetime.now(UTC)


def _skill_names() -> dict[str, str]:
    return {skill.id: skill.name for skill in get_catalog().skills}


def _level(b: float) -> str:
    """Самый высокий грейд, порог которого не выше b; ниже порога стажёра — below."""
    blueprints = get_blueprints()
    return next((g for g in reversed(GRADE_ORDER) if b >= blueprints.cut(g)), "below")


def _level_name(level: str) -> str:
    names = {item.slug.value: item.name for item in get_catalog().grades}
    return f"уровень {names[level]}" if level in names else "ниже уровня стажёра"


def pool_key(template: Template) -> str:
    """Группа «тема:стек:уровень» — работодатель выбирает её, а не конкретный шаблон (§10.6)."""
    return f"{template.topic}:{template.stack_module or '-'}:{_level(template.irt.b)}"


def _pool_templates(specialization: str, key: str) -> list[Template]:
    return sorted(
        (
            t
            for t in get_bank().for_spec(specialization)
            if t.status == "active" and t.kind != "open_approach" and pool_key(t) == key
        ),
        key=lambda t: t.id,
    )


def _pick(pool: list[Template]) -> Template:
    return secrets.choice(pool)


def _pool_name(key: str | None) -> str | None:
    if not key:
        return None
    topic, module, level = key.split(":")
    topic_name = get_blueprints().topic_names.get(topic, topic)
    return " · ".join(filter(None, [topic_name, None if module == "-" else module, _level_name(level)]))


# ---------- работодатель ----------


async def _own_task(db: AsyncSession, employer: Employer, task_id: int) -> EmployerTask:
    task = await db.get(EmployerTask, task_id)
    # Чужое задание неотличимо от несуществующего
    if task is None or task.employer_id != employer.id:
        raise NotFoundError("Задание не найдено")
    return task


async def _task_out(db: AsyncSession, task: EmployerTask) -> EmployerTaskOut:
    ungraded = TaskAssignment.score.is_(None)
    rows = await db.execute(
        select(TaskAssignment.status, ungraded, func.count())
        .where(TaskAssignment.task_id == task.id)
        .group_by(TaskAssignment.status, ungraded)
    )
    total = submitted = awaiting = 0
    for status, is_ungraded, count in rows:
        total += count
        if status == AssignmentStatus.submitted:
            submitted += count
            awaiting += count if is_ungraded else 0
    return EmployerTaskOut(
        id=task.id,
        title=task.title,
        kind=task.kind,
        specialization=task.specialization,
        grade=task.grade,
        need_id=task.need_id,
        pool=task.template_pool,
        pool_name=_pool_name(task.template_pool),
        prompt=task.prompt,
        rubric=list(task.rubric or []),
        assignments_total=total,
        submissions=submitted,
        awaiting_rating=awaiting,
        created_at=task.created_at,
    )


async def list_tasks(db: AsyncSession, user_id: int) -> list[EmployerTaskOut]:
    employer = await employers_service.get_by_user(db, user_id)
    tasks = await db.scalars(
        select(EmployerTask)
        .where(EmployerTask.employer_id == employer.id)
        .order_by(EmployerTask.created_at.desc(), EmployerTask.id.desc())
    )
    return [await _task_out(db, task) for task in tasks]


async def create_task(db: AsyncSession, user_id: int, body: EmployerTaskCreate) -> EmployerTaskOut:
    employer = await employers_service.get_by_user(db, user_id)
    specialization, grade = body.specialization, body.grade
    if body.need_id is not None:
        need = await needs_service.get_own_need(db, user_id, body.need_id)
        specialization, grade = need.specialization, body.grade or need.grade
    if specialization not in get_blueprints().specializations:
        raise TaskValidationError(
            "Для этой специализации нет банка заданий", code="no_test_for_specialization"
        )
    if len(body.rubric) > get_config().rubric_max:
        raise TaskValidationError(f"В чек-листе не больше {get_config().rubric_max} критериев")

    pool = None
    if body.kind == TaskKind.auto:
        if not _pool_templates(specialization, body.pool or ""):
            raise TaskValidationError("Нет заданий для этой темы и уровня", code="unknown_pool")
        pool = body.pool
    task = EmployerTask(
        employer_id=employer.id,
        need_id=body.need_id,
        specialization=specialization,
        grade=grade,
        kind=body.kind,
        template_pool=pool,
        title=body.title.strip(),
        prompt=body.prompt.strip() if body.kind == TaskKind.approach and body.prompt else None,
        rubric=[item.strip() for item in body.rubric] if body.kind == TaskKind.approach else [],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return await _task_out(db, task)


async def template_options(
    db: AsyncSession, user_id: int, specialization: str | None, need_id: int | None
) -> list[TaskTemplateOption]:
    """Группы заданий «тема × стек × уровень»; с need_id — сначала с навыками потребности (§10.7 п.5).

    Тексты, id и сложность шаблонов не отдаются: иначе любой работодатель выгрузит банк (§10.6).
    """
    wanted: set[str] = set()
    modules: set[str] | None = None
    grade = "middle"
    if need_id is not None:
        need = await needs_service.get_own_need(db, user_id, need_id)
        specialization, grade = need.specialization, need.grade.value
        wanted = set(need.required_skills or []) | set(need.optional_skills or [])
        modules = set(survey_service.stack_modules_for(specialization, {"stack": sorted(wanted)}))
    if not specialization or specialization not in get_blueprints().specializations:
        raise TaskValidationError("Укажите специализацию с банком заданий", code="no_test_for_specialization")
    blueprints = get_blueprints()
    names = _skill_names()
    templates = [
        t
        for t in get_bank().for_spec(specialization)
        if t.status == "active"
        and t.kind != "open_approach"
        and (modules is None or t.stack_module is None or t.stack_module in modules)
    ]
    groups: dict[str, list[Template]] = {}
    for template in templates:
        groups.setdefault(pool_key(template), []).append(template)
    levels = [*GRADE_ORDER, "below"]
    options = []
    for key, members in groups.items():
        topic, _, level = key.split(":")
        skills = sorted({s for t in members for s in t.skills})
        options.append(
            TaskTemplateOption(
                key=key,
                name=_pool_name(key) or key,
                topic_name=blueprints.topic_names.get(topic, topic),
                level=_level_name(level),
                skills=[names.get(s, s) for s in skills],
                matches_need=bool(wanted & set(skills)),
            )
        )
    distance = {key: abs(levels.index(key.split(":")[2]) - levels.index(grade)) for key in groups}
    return sorted(options, key=lambda o: (not o.matches_need, distance[o.key], o.name))


def _payload_of(assignment: TaskAssignment) -> AnswerPayload | None:
    if not assignment.response:
        return None
    return AnswerPayload.model_validate(assignment.response)


async def submissions(db: AsyncSession, user_id: int, task_id: int) -> list[TaskSubmissionForEmployer]:
    from app.modules.matching import service as matching_service

    employer = await employers_service.get_by_user(db, user_id)
    task = await _own_task(db, employer, task_id)
    rows = list(
        await db.scalars(
            select(TaskAssignment)
            .where(TaskAssignment.task_id == task.id, TaskAssignment.status == AssignmentStatus.submitted)
            .order_by(TaskAssignment.submitted_at.desc(), TaskAssignment.id.desc())
        )
    )
    # Кандидат, скрывший компанию, ей не виден — и его решения тоже
    hidden = set(
        await db.scalars(
            select(Candidate.id).where(
                Candidate.id.in_([row.candidate_id for row in rows]),
                any_(Candidate.hidden_employer_ids) == employer.id,
            )
        )
    )
    rows = [row for row in rows if row.candidate_id not in hidden]
    briefs = await matching_service.briefs(db, [row.candidate_id for row in rows])
    return [
        _submission_out(
            row,
            briefs[row.candidate_id],
            await matching_service.contacts_unlocked(db, employer.id, row.candidate_id),
        )
        for row in rows
        if row.candidate_id in briefs
    ]


def _submission_out(assignment: TaskAssignment, brief, unlocked: bool) -> TaskSubmissionForEmployer:
    response = _payload_of(assignment)
    # До раскрытия контактов свободный текст решения их не выдаёт (инвариант contact_unlocks, §13)
    if response is not None and not unlocked:
        response = response.model_copy(update={"text": redact_contacts(response.text)})
    return TaskSubmissionForEmployer(
        assignment_id=assignment.id,
        candidate=brief,
        status=assignment.status,
        response=response,
        score=assignment.score,
        graded_by=assignment.graded_by,
        rubric_hits=list(assignment.rubric_hits or []),
        employer_rating=assignment.employer_rating,
        submitted_at=assignment.submitted_at,
    )


async def rate(
    db: AsyncSession, user_id: int, task_id: int, assignment_id: int, body: TaskRating
) -> TaskSubmissionForEmployer:
    from app.modules.matching import service as matching_service

    employer = await employers_service.get_by_user(db, user_id)
    task = await _own_task(db, employer, task_id)
    assignment = await db.get(TaskAssignment, assignment_id)
    if assignment is None or assignment.task_id != task.id:
        raise NotFoundError("Решение не найдено")
    if assignment.status != AssignmentStatus.submitted:
        raise ConflictError("Оценить можно только присланное решение", code="not_submitted")
    assignment.employer_rating = body.rating
    # Автопроверка и чек-лист главнее; без них score — нормированная оценка работодателя 1–5
    if assignment.graded_by in (None, GradedBy.employer):
        assignment.score = round((body.rating - 1) / 4, 4)
        assignment.graded_by = GradedBy.employer
    await matching_service.refresh_candidate(db, assignment.candidate_id)
    await db.commit()
    briefs = await matching_service.briefs(db, [assignment.candidate_id])
    if assignment.candidate_id not in briefs:
        raise NotFoundError("Кандидат больше не в выдаче")
    unlocked = await matching_service.contacts_unlocked(db, employer.id, assignment.candidate_id)
    return _submission_out(assignment, briefs[assignment.candidate_id], unlocked)


# ---------- кандидат ----------


async def _expire(db: AsyncSession, candidate_id: int, now: datetime) -> None:
    await db.execute(
        update(TaskAssignment)
        .where(
            TaskAssignment.candidate_id == candidate_id,
            TaskAssignment.status == AssignmentStatus.offered,
            TaskAssignment.due_at < now,
        )
        .values(status=AssignmentStatus.expired)
    )


async def _offer(db: AsyncSession, candidate: Candidate, now: datetime) -> None:
    """Ленивое «раз в неделю» (§11): новое задание при открытии списка, если нет активного."""
    current = await categories_service.get_current(db, candidate.id)
    if current is None:
        return
    config = get_config()
    active = await db.scalar(
        select(func.count())
        .select_from(TaskAssignment)
        .where(TaskAssignment.candidate_id == candidate.id, TaskAssignment.status == AssignmentStatus.offered)
    )
    last_offer = await db.scalar(
        select(func.max(TaskAssignment.offered_at)).where(TaskAssignment.candidate_id == candidate.id)
    )
    if active or (last_offer and now - last_offer < timedelta(days=config.offer_interval_days)):
        return
    taken = select(TaskAssignment.task_id).where(TaskAssignment.candidate_id == candidate.id)
    query = (
        select(EmployerTask)
        .where(
            EmployerTask.specialization == current.specialization,
            (EmployerTask.grade.is_(None)) | (EmployerTask.grade == current.grade),
            EmployerTask.id.not_in(taken),
        )
        .order_by(EmployerTask.created_at.desc(), EmployerTask.id.desc())
    )
    hidden = set(candidate.hidden_employer_ids or [])
    task = next((t for t in await db.scalars(query) if t.employer_id not in hidden), None)
    if task is None:
        return
    await offer_task(db, task, candidate.id, now)


async def offer_task(
    db: AsyncSession, task: EmployerTask, candidate_id: int, now: datetime
) -> TaskAssignment:
    """Предложить задание кандидату: для auto — новый экземпляр шаблона, ключ остаётся в БД.

    Для задания-группы шаблон выбирается здесь, свой для каждого кандидата.
    """
    payload = answer_key = template_id = None
    if task.kind == TaskKind.auto:
        if task.template_pool:
            pool = _pool_templates(task.specialization, task.template_pool)
            template_id = _pick(pool).id if pool else None
        else:
            template_id = task.template_id
    if template_id:
        instance = render(get_bank().templates[template_id], secrets.randbits(31))
        payload, answer_key = instance.public_payload(), instance.key
    assignment = TaskAssignment(
        task_id=task.id,
        candidate_id=candidate_id,
        offered_at=now,
        due_at=now + timedelta(days=get_config().due_days),
        status=AssignmentStatus.offered,
        template_id=template_id,
        payload=payload,
        answer_key=answer_key,
    )
    db.add(assignment)
    await db.flush()
    return assignment


async def _confirmed_skills(db: AsyncSession, candidate_id: int) -> dict[int, list[str]]:
    rows = await db.scalars(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id, CandidateSkill.source == SkillSource.task
        )
    )
    by_assignment: dict[int, list[str]] = {}
    for row in rows:
        assignment_id = (row.evidence or {}).get("assignment_id")
        if assignment_id is not None:
            by_assignment.setdefault(int(assignment_id), []).append(row.skill_id)
    return by_assignment


def _item_out(assignment: TaskAssignment) -> CurrentItem | None:
    payload = assignment.payload
    if not payload:
        return None
    return CurrentItem(
        finished=assignment.status != AssignmentStatus.offered,
        item_id=assignment.id,
        position=1,
        total_estimate=1,
        kind=payload["kind"],
        stem=payload["stem"],
        code=payload.get("code"),
        code_language=payload.get("code_language"),
        options=[ItemOption(**option) for option in payload["options"]],
        max_length=payload.get("max_length"),
        time_limit_sec=payload.get("time_limit_sec"),
        deadline_at=assignment.due_at,
    )


def _assignment_out(
    assignment: TaskAssignment, task: EmployerTask, company: str, confirmed: list[str]
) -> TaskAssignmentForCandidate:
    names = _skill_names()
    return TaskAssignmentForCandidate(
        id=assignment.id,
        company_name=company,
        title=task.title,
        kind=task.kind,
        item=_item_out(assignment),
        prompt=task.prompt,
        rubric=list(task.rubric or []),
        status=assignment.status,
        offered_at=assignment.offered_at,
        due_at=assignment.due_at,
        submitted_at=assignment.submitted_at,
        response=_payload_of(assignment),
        score=assignment.score,
        graded_by=assignment.graded_by,
        confirmed_skills=sorted(names.get(s, s) for s in confirmed),
    )


async def _company_names(db: AsyncSession, employer_ids: set[int]) -> dict[int, str]:
    if not employer_ids:
        return {}
    rows = await db.execute(select(Employer.id, Employer.company_name).where(Employer.id.in_(employer_ids)))
    return {employer_id: name or "Компания" for employer_id, name in rows}


async def my_tasks(db: AsyncSession, candidate: Candidate) -> list[TaskAssignmentForCandidate]:
    now = _now()
    # Параллельные открытия списка не должны выдать два задания (§11: не больше одного активного)
    await db.execute(select(Candidate.id).where(Candidate.id == candidate.id).with_for_update())
    await _expire(db, candidate.id, now)
    await _offer(db, candidate, now)
    await db.commit()
    rows = (
        await db.execute(
            select(TaskAssignment, EmployerTask)
            .join(EmployerTask, EmployerTask.id == TaskAssignment.task_id)
            .where(TaskAssignment.candidate_id == candidate.id)
            .order_by(TaskAssignment.offered_at.desc(), TaskAssignment.id.desc())
        )
    ).all()
    companies = await _company_names(db, {task.employer_id for _, task in rows})
    confirmed = await _confirmed_skills(db, candidate.id)
    return [
        _assignment_out(
            assignment, task, companies.get(task.employer_id, "Компания"), confirmed.get(assignment.id, [])
        )
        for assignment, task in rows
    ]


async def _own_assignment(
    db: AsyncSession, candidate: Candidate, assignment_id: int
) -> tuple[TaskAssignment, EmployerTask]:
    # Блокировка строки: параллельные ответы иначе перебирают варианты за одну попытку
    assignment = await db.get(TaskAssignment, assignment_id, with_for_update=True, populate_existing=True)
    if assignment is None or assignment.candidate_id != candidate.id:
        raise NotFoundError("Задание не найдено")
    task = await db.get(EmployerTask, assignment.task_id)
    return assignment, task


def _check_open(assignment: TaskAssignment, now: datetime) -> None:
    if assignment.status == AssignmentStatus.offered and assignment.due_at < now:
        assignment.status = AssignmentStatus.expired
    if assignment.status != AssignmentStatus.offered:
        raise ConflictError(
            "Задание уже закрыто", code="assignment_closed", details={"status": assignment.status}
        )


async def _rubric_hits(task: EmployerTask, text: str, user_id: int) -> list[bool] | None:
    """Отметки LLM по чек-листу или None (LLM выключен, ошибка, ответ не по форме)."""
    return await llm.rubric_hits(task.prompt or "", list(task.rubric or []), text, user_id)


async def _confirm_skills(
    db: AsyncSession, candidate_id: int, assignment: TaskAssignment, template: Template, now: datetime
) -> None:
    for skill in template.skills:
        existing = await db.get(CandidateSkill, (candidate_id, skill, SkillSource.task))
        evidence = {"task_id": assignment.task_id, "assignment_id": assignment.id, "template_id": template.id}
        if existing is None:
            db.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    skill_id=skill,
                    source=SkillSource.task,
                    evidence=evidence,
                    updated_at=now,
                )
            )
        else:
            existing.evidence, existing.updated_at = evidence, now


async def submit(
    db: AsyncSession, candidate: Candidate, user_id: int, assignment_id: int, body: TaskSubmit
) -> TaskAssignmentForCandidate:
    from app.modules.matching import service as matching_service

    now = _now()
    assignment, task = await _own_assignment(db, candidate, assignment_id)
    try:
        _check_open(assignment, now)
    except ConflictError:
        await db.commit()
        raise
    response = body.response.model_dump(exclude_none=True)

    if task.kind == TaskKind.auto:
        if not assignment.answer_key or not assignment.payload:
            raise ConflictError("Задание повреждено", code="assignment_broken")
        assignment.score = score_response(assignment.payload["kind"], assignment.answer_key, response)
        assignment.graded_by = GradedBy.auto
        template = get_bank().templates.get(assignment.template_id or task.template_id or "")
        if template is not None and (assignment.score or 0.0) >= get_config().confirm_min_score:
            await _confirm_skills(db, candidate.id, assignment, template, now)
    else:
        text = (body.response.text or "").strip()
        if not text:
            raise TaskValidationError("Опишите подход текстом", code="empty_answer")
        response = {"text": text}
        hits = await _rubric_hits(task, text, user_id)
        if hits is not None:
            assignment.rubric_hits = hits
            assignment.score = round(sum(hits) / len(hits), 4)
            assignment.graded_by = GradedBy.llm

    assignment.response = response
    assignment.submitted_at = now
    assignment.status = AssignmentStatus.submitted
    await db.flush()
    await matching_service.refresh_candidate(db, candidate.id)
    await db.commit()
    companies = await _company_names(db, {task.employer_id})
    confirmed = await _confirmed_skills(db, candidate.id)
    return _assignment_out(
        assignment, task, companies.get(task.employer_id, "Компания"), confirmed.get(assignment.id, [])
    )


async def skip(db: AsyncSession, candidate: Candidate, assignment_id: int) -> TaskAssignmentForCandidate:
    now = _now()
    assignment, task = await _own_assignment(db, candidate, assignment_id)
    try:
        _check_open(assignment, now)
    except ConflictError:
        await db.commit()
        raise
    assignment.status = AssignmentStatus.skipped
    await db.commit()
    companies = await _company_names(db, {task.employer_id})
    return _assignment_out(assignment, task, companies.get(task.employer_id, "Компания"), [])


# ---------- сигналы для индекса выдачи ----------


@dataclass(frozen=True)
class TaskSignals:
    last_graded_at: datetime | None
    approach_scores: list[float]


async def signals(db: AsyncSession, candidate_id: int) -> TaskSignals:
    """Для fresh и approach в индексе (§11): последнее проверенное решение и оценки заданий на подход."""
    rows = (
        await db.execute(
            select(TaskAssignment.submitted_at, TaskAssignment.score, EmployerTask.kind)
            .join(EmployerTask, EmployerTask.id == TaskAssignment.task_id)
            .where(
                TaskAssignment.candidate_id == candidate_id,
                TaskAssignment.status == AssignmentStatus.submitted,
                TaskAssignment.score.is_not(None),
            )
        )
    ).all()
    return TaskSignals(
        last_graded_at=max((at for at, _, _ in rows if at is not None), default=None),
        approach_scores=[score for _, score, kind in rows if kind == TaskKind.approach],
    )


async def forget_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Удаление аккаунта: текст решений — ПДн и удаляется, оценка остаётся. Коммитит вызывающий."""
    await db.execute(
        update(TaskAssignment)
        .where(TaskAssignment.candidate_id == candidate_id, TaskAssignment.response.has_key("text"))
        .values(response=TaskAssignment.response.op("-")("text"))
    )
