"""Попытки теста (§10): движок + БД. Ключи ответов не покидают сервер, время считает сервер."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm
from app.core.config import get_settings
from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade, SkillSource, TemplateStatus
from app.core.errors import AppError, ConflictError, NotFoundError
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.matching import service as matching_service
from app.modules.survey import service as survey_service
from app.modules.testing.engine import confidence, integrity
from app.modules.testing.engine.bank import GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.render import render
from app.modules.testing.engine.scoring import score
from app.modules.testing.engine.session import STAGE_OPEN, Answered, AttemptConfig, Planner
from app.modules.testing.models import TemplateStat, TestAttempt, TestAttemptItem
from app.modules.testing.schemas import (
    AnswerAck,
    AnswerRequest,
    ApproachAnswer,
    ApproachCriterion,
    AttemptCreate,
    AttemptOut,
    AttemptResultOut,
    CurrentItem,
    GradeBandProbability,
    GradeConfidence,
    GradeEvidence,
    IntegrityReason,
    IntegritySignals,
    ItemOption,
    NextAction,
    TopicScore,
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _owned_attempt(db: AsyncSession, candidate: Candidate, attempt_id: int) -> TestAttempt:
    attempt = await db.get(TestAttempt, attempt_id)
    # Чужая попытка неотличима от несуществующей
    if attempt is None or attempt.candidate_id != candidate.id:
        raise NotFoundError("Попытка не найдена")
    return attempt


async def _items(db: AsyncSession, attempt_id: int) -> list[TestAttemptItem]:
    query = (
        select(TestAttemptItem)
        .where(TestAttemptItem.attempt_id == attempt_id)
        .order_by(TestAttemptItem.position)
    )
    return list(await db.scalars(query))


def _history(items: list[TestAttemptItem]) -> list[Answered]:
    return [Answered(i.template_id, i.stage, i.scored, i.score) for i in items if i.answered_at is not None]


async def _exposure(db: AsyncSession, specialization: str) -> dict[str, float]:
    """Доля попыток специализации, в которых показывался шаблон (§10.3)."""
    attempts = await db.scalar(
        select(func.count()).select_from(TestAttempt).where(TestAttempt.specialization == specialization)
    )
    rows = await db.execute(select(TemplateStat.template_id, TemplateStat.exposures))
    return {template_id: exposures / max(attempts or 1, 1) for template_id, exposures in rows}


async def _planner(db: AsyncSession, attempt: TestAttempt) -> Planner:
    config = AttemptConfig(
        specialization=attempt.specialization,
        grade_target=attempt.grade_target.value,
        seed=attempt.seed,
        mode=attempt.blueprint.get("mode", "full"),
        stack_modules=tuple(attempt.blueprint.get("stack_modules", [])),
    )
    return Planner(config, get_bank(), get_blueprints(), await _exposure(db, attempt.specialization))


def _total_estimate(planner: Planner) -> int:
    mode = planner.mode
    open_item = GRADE_ORDER.index(planner.config.grade_target) >= GRADE_ORDER.index(
        planner.blueprints.open_approach_from_grade
    )
    return mode.stage1_items + mode.stage2_items + mode.pilot_slots + int(open_item)


def _attempt_out(attempt: TestAttempt, items: list[TestAttemptItem], planner: Planner) -> AttemptOut:
    return AttemptOut(
        id=attempt.id,
        specialization=attempt.specialization,
        grade_target=attempt.grade_target,
        purpose=attempt.purpose,
        status=attempt.status,
        answered=sum(item.answered_at is not None for item in items),
        total_estimate=max(_total_estimate(planner), len(items)),
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
    )


async def start(db: AsyncSession, candidate: Candidate, body: AttemptCreate) -> AttemptOut:
    if not candidate.specialization:
        raise ConflictError("Сначала пройдите опрос и выберите специализацию", code="survey_required")
    if body.specialization != candidate.specialization:
        raise ConflictError("Тест доступен по вашей специализации", code="specialization_mismatch")
    spec = next(s for s in get_catalog().specializations if s.slug == candidate.specialization)
    if not spec.has_test:
        raise AppError("Для этой специализации тест появится позже", code="no_test_for_specialization")

    in_progress = await db.scalar(
        select(TestAttempt).where(
            TestAttempt.candidate_id == candidate.id, TestAttempt.status == AttemptStatus.in_progress
        )
    )
    if in_progress is not None:
        raise ConflictError(
            "Есть незавершённый тест", code="attempt_in_progress", details={"attempt_id": in_progress.id}
        )

    decision = await categories_service.check_can_start(db, candidate, body.grade_target.value)
    if not decision.allowed:
        details = {"available_at": decision.available_at.isoformat()} if decision.available_at else None
        raise ConflictError(
            decision.reason or "Сейчас нельзя", code=decision.code or "conflict", details=details
        )

    response = await survey_service.latest_response(db, candidate.id)
    stack_modules = survey_service.stack_modules_for(
        candidate.specialization, response.answers if response else {}
    )
    attempt = TestAttempt(
        candidate_id=candidate.id,
        specialization=candidate.specialization,
        grade_target=body.grade_target,
        purpose=AttemptPurpose(decision.purpose),
        blueprint={"mode": get_settings().test_mode, "stack_modules": stack_modules},
        seed=secrets.randbits(31),
        status=AttemptStatus.in_progress,
        flags={},
    )
    db.add(attempt)
    await db.commit()
    return _attempt_out(attempt, [], await _planner(db, attempt))


async def get_attempt(db: AsyncSession, candidate: Candidate, attempt_id: int) -> AttemptOut:
    attempt = await _owned_attempt(db, candidate, attempt_id)
    return _attempt_out(attempt, await _items(db, attempt.id), await _planner(db, attempt))


def _deadline(item: TestAttemptItem) -> datetime:
    return item.shown_at + timedelta(seconds=item.payload["time_limit_sec"])


def _is_late(item: TestAttemptItem, at: datetime) -> bool:
    return at > _deadline(item) + timedelta(seconds=get_settings().answer_grace_seconds)


def _current_out(item: TestAttemptItem, total: int) -> CurrentItem:
    payload = item.payload
    return CurrentItem(
        finished=False,
        item_id=item.id,
        position=item.position + 1,
        total_estimate=max(total, item.position + 1),
        kind=payload["kind"],
        stem=payload["stem"],
        code=payload.get("code"),
        code_language=payload.get("code_language"),
        options=[ItemOption(**option) for option in payload["options"]],
        max_length=payload.get("max_length"),
        time_limit_sec=payload["time_limit_sec"],
        deadline_at=_deadline(item),
    )


async def _record_stat(db: AsyncSession, template_id: str, *, shown: int = 0, correct: float = 0.0) -> None:
    template = get_bank().templates[template_id]
    statement = insert(TemplateStat).values(
        template_id=template_id,
        version=template.version,
        status=TemplateStatus(template.status),
        irt_a=template.irt.a,
        irt_b=template.irt.b,
        irt_c=template.guessing,
        exposures=shown,
        correct=int(correct),
    )
    statement = statement.on_conflict_do_update(
        index_elements=[TemplateStat.template_id, TemplateStat.version],
        set_={
            "exposures": TemplateStat.exposures + shown,
            "correct": TemplateStat.correct + int(correct),
        },
    )
    await db.execute(statement)


def _mark_answered(item: TestAttemptItem, response: dict | None, at: datetime, late: bool) -> None:
    item.response = {**(response or {}), "late": late} if response or late else response
    item.answered_at = at
    item.time_ms = int((at - item.shown_at).total_seconds() * 1000)
    item.score = (
        0.0
        if late and item.payload["kind"] != "open_approach"
        else score(item.payload["kind"], item.answer_key, response)
    )


async def current_item(db: AsyncSession, candidate: Candidate, attempt_id: int) -> CurrentItem:
    attempt = await _owned_attempt(db, candidate, attempt_id)
    if attempt.status != AttemptStatus.in_progress:
        return CurrentItem(finished=True)
    planner = await _planner(db, attempt)
    items = await _items(db, attempt.id)
    now = _now()

    pending = next((item for item in items if item.answered_at is None), None)
    if pending is not None:
        if not _is_late(pending, now):
            return _current_out(pending, _total_estimate(planner))
        _mark_answered(pending, None, now, late=True)  # время вышло — засчитывается как неверный

    next_item = planner.next_item(_history(items))
    if next_item is None:
        await _finalize(db, attempt, planner, items)
        await db.commit()
        return CurrentItem(finished=True)

    instance = render(next_item.template, next_item.instance_seed)
    item = TestAttemptItem(
        attempt_id=attempt.id,
        template_id=instance.template_id,
        template_version=instance.version,
        instance_seed=next_item.instance_seed,
        stage=next_item.stage,
        position=len(items),
        scored=next_item.scored,
        payload=instance.public_payload(),
        answer_key=instance.key,
        shown_at=now,
    )
    db.add(item)
    await _record_stat(db, instance.template_id, shown=1)
    attempt.stage = max(attempt.stage, next_item.stage)
    await db.commit()
    return _current_out(item, _total_estimate(planner))


async def answer(db: AsyncSession, candidate: Candidate, attempt_id: int, body: AnswerRequest) -> AnswerAck:
    attempt = await _owned_attempt(db, candidate, attempt_id)
    if attempt.status != AttemptStatus.in_progress:
        raise ConflictError("Тест уже завершён", code="attempt_finished")
    items = await _items(db, attempt.id)
    pending = next((item for item in items if item.answered_at is None), None)
    if pending is None or pending.id != body.item_id:
        raise ConflictError("Это задание уже не текущее", code="not_current_item")

    now = _now()
    late = _is_late(pending, now)
    _mark_answered(pending, body.response.model_dump(exclude_none=True), now, late)
    if pending.stage == STAGE_OPEN and not late:
        await _grade_open_answer(attempt, pending, candidate.user_id)
    if pending.score:
        await _record_stat(db, pending.template_id, correct=pending.score)
    if body.focus_lost_count:
        flags = dict(attempt.flags or {})
        flags["focus_lost"] = flags.get("focus_lost", 0) + body.focus_lost_count
        attempt.flags = flags

    planner = await _planner(db, attempt)
    finished = planner.next_item(_history(items)) is None
    if finished:
        await _finalize(db, attempt, planner, items)
    await db.commit()
    return AnswerAck(accepted=True, late=late, finished=finished)


async def _grade_open_answer(attempt: TestAttempt, item: TestAttemptItem, user_id: int) -> None:
    """§10.5: LLM отмечает критерии чек-листа, approach = доля отмеченных; в θ̂ не входит."""
    text = str((item.response or {}).get("text") or "")
    rubric = list((item.answer_key or {}).get("rubric") or [])
    hits = await llm.rubric_hits(item.payload.get("stem", ""), rubric, text, user_id)
    if hits is None:
        return
    item.response = {**(item.response or {}), "rubric_hits": hits}
    attempt.approach_score = round(sum(hits) / len(hits), 4)


async def _finalize(
    db: AsyncSession, attempt: TestAttempt, planner: Planner, items: list[TestAttemptItem]
) -> None:
    summary = planner.summarize(_history(items))
    attempt.theta = round(summary.theta, 4)
    attempt.se = round(summary.se, 4)
    attempt.result = AttemptResult(summary.result)
    attempt.topic_scores = summary.topic_scores
    attempt.skill_scores = summary.skill_scores
    attempt.status = AttemptStatus.completed
    attempt.finished_at = _now()
    flags = dict(attempt.flags or {})
    flags["open_answers"] = [i.id for i in items if i.stage == STAGE_OPEN and i.answered_at is not None]
    if get_settings().integrity_signals_enabled:
        flags["integrity"] = _integrity(items, summary.theta).as_dict()
    attempt.flags = flags

    category = await categories_service.apply_attempt_result(db, attempt)
    if category is None or attempt.candidate_id is None:
        return
    await db.execute(
        delete(CandidateSkill).where(
            CandidateSkill.candidate_id == attempt.candidate_id, CandidateSkill.source == SkillSource.test
        )
    )
    now = _now()
    for skill in summary.verified_skills:
        evidence = {"attempt_id": attempt.id, **summary.skill_scores.get(skill, {})}
        db.add(
            CandidateSkill(
                candidate_id=attempt.candidate_id,
                skill_id=skill,
                source=SkillSource.test,
                evidence=evidence,
                updated_at=now,
            )
        )
    await db.flush()
    await matching_service.refresh_candidate(db, attempt.candidate_id)
    await matching_service.refresh_category(db, category.specialization, category.grade)


def _integrity(items: list[TestAttemptItem], theta: float) -> integrity.IntegrityResult:
    """§10.9: сигналы по оценённым ответам и итоговой θ̂ — только пометка, в результат попытки не входят."""
    templates = get_bank().templates
    responses = [
        integrity.TimedResponse(
            a=template.irt.a,
            b=template.irt.b,
            c=template.guessing,
            score=item.score,
            time_sec=item.time_ms / 1000 if item.time_ms is not None else None,
            time_limit_sec=float(item.payload["time_limit_sec"]),
        )
        for item in items
        if item.scored
        and item.score is not None
        and item.answered_at is not None
        and (template := templates.get(item.template_id)) is not None
    ]
    return integrity.evaluate(responses, theta, integrity.get_rules())


async def integrity_signals(db: AsyncSession, attempt_id: int) -> IntegritySignals | None:
    """Сигналы честности для карточки кандидата у работодателя; None — выключены или не считались."""
    if not get_settings().integrity_signals_enabled:
        return None
    attempt = await db.get(TestAttempt, attempt_id)
    data = (attempt.flags or {}).get("integrity") if attempt is not None else None
    if not data:
        return None
    texts = integrity.get_rules().texts
    reasons = [IntegrityReason(code=code, text=texts.reasons[code]) for code in data.get("reasons", [])]
    note = texts.insufficient if not data["enough_data"] else texts.note if data["flagged"] else texts.clean
    return IntegritySignals(
        enough_data=data["enough_data"],
        flagged=data["flagged"],
        reasons=reasons,
        note=note,
        items=data["items"],
        lz_star=data.get("lz_star"),
        rapid_share=data.get("rapid_share"),
        fast_correct_hard=data.get("fast_correct_hard"),
    )


def grade_confidence(theta: float, se: float, grade: str, *, for_candidate: bool = False) -> GradeConfidence:
    """§10.4.1: вероятности полос грейда по θ̂ и SE с порогами правила грейда; сам грейд не меняет."""
    rules = confidence.get_rules()
    cuts = get_blueprints().scale.cuts
    names = {item.slug.value: item.name for item in get_catalog().grades}
    at_least = confidence.probability_at_least(theta, se, cuts[grade])
    level = confidence.level_for(at_least, rules)
    phrase = {"percent": confidence.display_percent(at_least, rules), "grade": names.get(grade, grade)}
    bands = confidence.band_probabilities(theta, se, cuts)
    return GradeConfidence(
        grade=Grade(grade),
        at_least=round(at_least, 4),
        level=level.code,
        level_label=level.label,
        text=(rules.texts.candidate if for_candidate else rules.texts.statement).format(**phrase),
        bands=[
            GradeBandProbability(
                grade=None if band == confidence.BELOW else Grade(band),
                label=rules.texts.below if band == confidence.BELOW else names.get(band, band),
                probability=round(probability, 4),
            )
            for band, probability in bands.items()
        ],
        note=rules.texts.note,
    )


async def grade_evidence(
    db: AsyncSession,
    attempt_id: int | None,
    grade: str,
    valid_until: datetime,
    *,
    for_candidate: bool = False,
) -> GradeEvidence | None:
    """Блок «Почему этому грейду можно верить»: тест, по которому присвоена категория; None — теста нет."""
    attempt = await db.get(TestAttempt, attempt_id) if attempt_id is not None else None
    if attempt is None or attempt.theta is None or attempt.se is None:
        return None
    items = await db.scalar(
        select(func.count())
        .select_from(TestAttemptItem)
        .where(
            TestAttemptItem.attempt_id == attempt.id,
            TestAttemptItem.scored.is_(True),
            TestAttemptItem.score.is_not(None),
        )
    )
    rules = confidence.get_rules()
    return GradeEvidence(
        tested_at=attempt.finished_at,
        valid_until=valid_until,
        adaptive=True,
        short_mode=(attempt.blueprint or {}).get("mode") == "short",
        items_scored=items or 0,
        theta=attempt.theta,
        se=attempt.se,
        confidence=grade_confidence(attempt.theta, attempt.se, grade, for_candidate=for_candidate),
        how_it_works_path=rules.how_it_works_path,
        validation_url=rules.validation_url,
    )


async def open_answers(db: AsyncSession, attempt_id: int) -> list[ApproachAnswer]:
    """Ответы на открытый вопрос о подходе с отметками по чек-листу (§10.5) — для карточки кандидата."""
    items = await db.scalars(
        select(TestAttemptItem)
        .where(
            TestAttemptItem.attempt_id == attempt_id,
            TestAttemptItem.stage == STAGE_OPEN,
            TestAttemptItem.answered_at.is_not(None),
        )
        .order_by(TestAttemptItem.position)
    )
    answers = []
    for item in items:
        text = str((item.response or {}).get("text") or "").strip()
        if not text:
            continue
        rubric = list((item.answer_key or {}).get("rubric") or [])
        hits = (item.response or {}).get("rubric_hits")
        marks = hits if isinstance(hits, list) and len(hits) == len(rubric) else [None] * len(rubric)
        answers.append(
            ApproachAnswer(
                question=item.payload.get("stem", ""),
                answer=text,
                criteria=[ApproachCriterion(text=c, met=m) for c, m in zip(rubric, marks, strict=True)],
                score=round(sum(marks) / len(marks), 4) if marks and None not in marks else None,
            )
        )
    return answers


async def result(db: AsyncSession, candidate: Candidate, attempt_id: int) -> AttemptResultOut:
    attempt = await _owned_attempt(db, candidate, attempt_id)
    if attempt.status != AttemptStatus.completed or attempt.result is None:
        raise ConflictError("Тест ещё не завершён", code="attempt_not_finished")
    blueprints = get_blueprints()
    current = await categories_service.get_current(db, candidate.id)
    category = None
    percentile = None
    if current is not None:
        category = categories_service.category_ref(current.specialization, current.grade.value)
        percentile = current.percentile if current.attempt_id == attempt.id else None

    verified = sorted(
        skill
        for skill, stats in (attempt.skill_scores or {}).items()
        if stats["items"] >= blueprints.verify_skill.min_items
        and stats["correct"] / stats["items"] >= blueprints.verify_skill.min_share
    )
    return AttemptResultOut(
        attempt_id=attempt.id,
        specialization=attempt.specialization,
        grade_target=attempt.grade_target,
        result=attempt.result,
        theta=attempt.theta,
        se=attempt.se,
        percentile=percentile,
        category=category,
        topic_scores=[
            TopicScore(
                topic=topic, name=blueprints.topic_names.get(topic, topic), score=s["score"], items=s["items"]
            )
            for topic, s in sorted((attempt.topic_scores or {}).items())
        ],
        verified_skills=verified,
        approach_score=attempt.approach_score,
        confidence=grade_confidence(
            attempt.theta, attempt.se, attempt.grade_target.value, for_candidate=True
        ),
        next_actions=await _next_actions(db, candidate, attempt),
    )


async def _next_actions(db: AsyncSession, candidate: Candidate, attempt: TestAttempt) -> list[NextAction]:
    blueprints = get_blueprints()
    grade = attempt.grade_target.value
    if attempt.result == AttemptResult.fail:
        target, action, text = blueprints.previous_grade(grade), "retake_lower", "Пройти тест на грейд ниже"
    else:
        target, action, text = blueprints.next_grade(grade), "try_higher", "Попробовать грейд выше"
    if target is None:
        return [NextAction(action="none", message="Это крайний грейд шкалы")]
    decision = await categories_service.check_can_start(db, candidate, target)
    message = text if decision.allowed else f"{text} — {decision.reason or 'позже'}"
    return [
        NextAction(action=action, grade=Grade(target), available_at=decision.available_at, message=message)
    ]
