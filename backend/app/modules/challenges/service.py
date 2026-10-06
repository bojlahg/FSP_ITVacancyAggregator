"""Челленджи компании (§11.1): вопросы пишет работодатель, кандидат проходит по желанию.

Вопросы не откалиброваны и их может написать кто угодно, поэтому результат не влияет на грейд, категорию
и статусы навыков — это сигнал только для автора челленджа. Ключи ответов наружу не уходят (инвариант §13).
"""

import random
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import ChallengeAttemptStatus, ChallengeStatus
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.text_rules import check_texts
from app.modules.candidates.models import Candidate
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.challenges.models import Challenge, ChallengeAttempt
from app.modules.challenges.schemas import (
    ChallengeAttemptResult,
    ChallengeCard,
    ChallengeCreate,
    ChallengeOption,
    ChallengeOut,
    ChallengeQuestion,
    ChallengeSolver,
    ChallengeStats,
    OpenAnswer,
)
from app.modules.employers import service as employers_service
from app.modules.employers.models import Employer
from app.modules.resume.pdf import redact_contacts
from app.modules.testing.engine.bank import CONTENT_DIR
from app.modules.testing.engine.scoring import score as score_response
from app.modules.testing.schemas import AnswerAck, AnswerRequest, CurrentItem, ItemOption

CHOICE_KINDS = {"single_choice", "multi_choice"}
TEXT_RULES = "need_text_rules.yaml"


class ChallengeConfig(BaseModel):
    questions_min: int
    questions_max: int
    options_min: int
    options_max: int
    rubric_max: int
    time_per_question_min_sec: int
    time_per_question_max_sec: int
    time_per_question_default_sec: int
    skills_max: int


@lru_cache
def get_config() -> ChallengeConfig:
    with (CONTENT_DIR / "challenges.yaml").open(encoding="utf-8") as file:
        return ChallengeConfig.model_validate(yaml.safe_load(file))


class ChallengeValidationError(AppError):
    status_code = 422
    code = "invalid_challenge"


class ChallengeTextBlockedError(ConflictError):
    code = "challenge_text_discriminatory"
    message = "В тексте челленджа есть запрещённые требования — исправьте их перед публикацией"


def _now() -> datetime:
    return datetime.now(UTC)


def _at(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


# ---------- работодатель ----------


def _validate(body: ChallengeCreate) -> int:
    """Проверки по content/challenges.yaml; возвращает лимит времени на вопрос."""
    cfg = get_config()
    catalog = get_catalog()
    if body.specialization not in {spec.slug for spec in catalog.specializations}:
        raise ChallengeValidationError("Неизвестная специализация", code="unknown_specialization")
    known = {skill.id for skill in catalog.skills}
    if len(body.skills) > cfg.skills_max or not set(body.skills) <= known:
        raise ChallengeValidationError(f"Навыки — из справочника, не больше {cfg.skills_max}")
    if not cfg.questions_min <= len(body.questions) <= cfg.questions_max:
        raise ChallengeValidationError(f"Вопросов — от {cfg.questions_min} до {cfg.questions_max}")
    for question in body.questions:
        if question.kind in CHOICE_KINDS and not cfg.options_min <= len(question.options) <= cfg.options_max:
            raise ChallengeValidationError(f"Вариантов ответа — от {cfg.options_min} до {cfg.options_max}")
        if len(question.rubric) > cfg.rubric_max:
            raise ChallengeValidationError(f"Критериев у открытого вопроса — не больше {cfg.rubric_max}")
    limit = body.time_per_question_sec or cfg.time_per_question_default_sec
    if not cfg.time_per_question_min_sec <= limit <= cfg.time_per_question_max_sec:
        raise ChallengeValidationError(
            f"Время на вопрос — от {cfg.time_per_question_min_sec} до {cfg.time_per_question_max_sec} секунд"
        )
    sample = body.questions_per_attempt
    if sample is not None and not cfg.questions_min <= sample <= len(body.questions):
        raise ChallengeValidationError(
            f"Показывать кандидату — от {cfg.questions_min} вопросов и не больше, чем написано"
        )
    return limit


def stored_questions(questions: list[ChallengeQuestion]) -> list[dict[str, Any]]:
    stored = []
    for index, question in enumerate(questions, 1):
        options = [{"id": f"o{i}", "text": o.text.strip()} for i, o in enumerate(question.options, 1)]
        key: dict[str, Any] = {}
        if question.kind in CHOICE_KINDS:
            key = {
                "choice_ids": sorted(
                    o["id"] for o, src in zip(options, question.options, strict=True) if src.correct
                )
            }
        elif question.kind == "numeric":
            key = {"number": question.number, "tolerance": question.tolerance}
        stored.append(
            {
                "id": f"q{index}",
                "kind": question.kind,
                "text": question.text.strip(),
                "code": question.code or None,
                "options": options if question.kind in CHOICE_KINDS else [],
                "key": key,
                "rubric": [item.strip() for item in question.rubric],
            }
        )
    return stored


def _question_out(stored: dict[str, Any]) -> ChallengeQuestion:
    key = stored["key"]
    return ChallengeQuestion(
        kind=stored["kind"],
        text=stored["text"],
        code=stored["code"],
        options=[
            ChallengeOption(text=o["text"], correct=o["id"] in key.get("choice_ids", []))
            for o in stored["options"]
        ],
        number=key.get("number"),
        tolerance=key.get("tolerance", 0.0),
        rubric=stored["rubric"],
    )


async def _stats(db: AsyncSession, challenge_id: int) -> ChallengeStats:
    completed = ChallengeAttempt.status == ChallengeAttemptStatus.completed
    row = await db.execute(
        select(
            func.count(),
            func.count().filter(completed),
            func.avg(ChallengeAttempt.score).filter(completed),
        ).where(ChallengeAttempt.challenge_id == challenge_id)
    )
    started, done, average = row.one()
    return ChallengeStats(
        started=started, completed=done, average_score=round(average, 4) if average is not None else None
    )


async def _out(db: AsyncSession, challenge: Challenge) -> ChallengeOut:
    return ChallengeOut(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description,
        specialization=challenge.specialization,
        grade=challenge.grade,
        skills=list(challenge.skills or []),
        time_per_question_sec=challenge.time_per_question_sec,
        questions_per_attempt=challenge.questions_per_attempt,
        questions=[_question_out(q) for q in challenge.questions],
        status=challenge.status,
        stats=await _stats(db, challenge.id),
        created_at=challenge.created_at,
        published_at=challenge.published_at,
        closed_at=challenge.closed_at,
    )


async def _own(db: AsyncSession, user_id: int, challenge_id: int) -> Challenge:
    employer = await employers_service.get_by_user(db, user_id)
    challenge = await db.get(Challenge, challenge_id)
    # Чужой челлендж неотличим от несуществующего
    if challenge is None or challenge.employer_id != employer.id:
        raise NotFoundError("Челлендж не найден")
    return challenge


def _apply(challenge: Challenge, body: ChallengeCreate, limit: int) -> None:
    challenge.title = body.title.strip()
    challenge.description = body.description.strip()
    challenge.specialization = body.specialization
    challenge.grade = body.grade
    challenge.skills = list(dict.fromkeys(body.skills))
    challenge.time_per_question_sec = limit
    challenge.questions_per_attempt = body.questions_per_attempt
    challenge.questions = stored_questions(body.questions)


async def create(db: AsyncSession, user_id: int, body: ChallengeCreate) -> ChallengeOut:
    employer = await employers_service.get_by_user(db, user_id)
    limit = _validate(body)
    challenge = Challenge(employer_id=employer.id, status=ChallengeStatus.draft)
    _apply(challenge, body, limit)
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return await _out(db, challenge)


async def update(db: AsyncSession, user_id: int, challenge_id: int, body: ChallengeCreate) -> ChallengeOut:
    challenge = await _own(db, user_id, challenge_id)
    if challenge.status != ChallengeStatus.draft:
        # Иначе кандидаты, уже прошедшие челлендж, сравнивались бы по разным вопросам
        raise ConflictError(
            "Опубликованный челлендж не меняется — закройте его и создайте новый", code="challenge_not_draft"
        )
    _apply(challenge, body, _validate(body))
    await db.commit()
    await db.refresh(challenge)
    return await _out(db, challenge)


def _ensure_publishable(challenge: Challenge) -> None:
    if get_settings().need_text_check != "block":
        return
    texts = [challenge.title, challenge.description]
    for question in challenge.questions:
        texts += [question["text"], *(o["text"] for o in question["options"])]
    blocking = [issue for issue in check_texts(TEXT_RULES, *texts) if issue.severity == "block"]
    if blocking:
        issues = [
            {"rule": i.rule, "label": i.label, "message": i.message, "fragment": i.fragment} for i in blocking
        ]
        raise ChallengeTextBlockedError(details={"issues": issues})


async def publish(db: AsyncSession, user_id: int, challenge_id: int) -> ChallengeOut:
    challenge = await _own(db, user_id, challenge_id)
    if challenge.status == ChallengeStatus.closed:
        raise ConflictError("Закрытый челлендж нельзя опубликовать снова", code="challenge_closed")
    if challenge.status == ChallengeStatus.draft:
        _ensure_publishable(challenge)
        challenge.status = ChallengeStatus.published
        challenge.published_at = _now()
        await db.commit()
        await db.refresh(challenge)
    return await _out(db, challenge)


async def close(db: AsyncSession, user_id: int, challenge_id: int) -> ChallengeOut:
    challenge = await _own(db, user_id, challenge_id)
    if challenge.status != ChallengeStatus.closed:
        challenge.status = ChallengeStatus.closed
        challenge.closed_at = _now()
        await db.commit()
        await db.refresh(challenge)
    return await _out(db, challenge)


async def list_own(db: AsyncSession, user_id: int) -> list[ChallengeOut]:
    employer = await employers_service.get_by_user(db, user_id)
    rows = await db.scalars(
        select(Challenge)
        .where(Challenge.employer_id == employer.id)
        .order_by(Challenge.created_at.desc(), Challenge.id.desc())
    )
    return [await _out(db, challenge) for challenge in rows]


async def get_own(db: AsyncSession, user_id: int, challenge_id: int) -> ChallengeOut:
    return await _out(db, await _own(db, user_id, challenge_id))


async def solvers(db: AsyncSession, user_id: int, challenge_id: int) -> list[ChallengeSolver]:
    """Решившие по убыванию результата: обезличенно, текст ответов без контактов до раскрытия (§13)."""
    from app.modules.matching import service as matching_service

    challenge = await _own(db, user_id, challenge_id)
    attempts = list(
        await db.scalars(
            select(ChallengeAttempt)
            .where(
                ChallengeAttempt.challenge_id == challenge.id,
                ChallengeAttempt.status == ChallengeAttemptStatus.completed,
            )
            .order_by(
                ChallengeAttempt.score.desc().nulls_last(),
                ChallengeAttempt.finished_at,
                ChallengeAttempt.id,
            )
        )
    )
    briefs = await matching_service.briefs(db, [a.candidate_id for a in attempts])
    questions = {q["id"]: q for q in challenge.questions}
    result = []
    for attempt in attempts:
        if attempt.candidate_id not in briefs:
            continue
        unlocked = await matching_service.contacts_unlocked(db, challenge.employer_id, attempt.candidate_id)
        open_answers = []
        for item in attempt.items:
            question = questions[item["question_id"]]
            if question["kind"] != "open_approach":
                continue
            text = (item.get("response") or {}).get("text")
            open_answers.append(
                OpenAnswer(
                    question=question["text"],
                    answer=text if unlocked else redact_contacts(text),
                    rubric=question["rubric"],
                )
            )
        result.append(
            ChallengeSolver(
                attempt_id=attempt.id,
                candidate=briefs[attempt.candidate_id],
                correct=attempt.correct,
                scored_total=attempt.scored_total,
                score=attempt.score,
                finished_at=attempt.finished_at,
                open_answers=open_answers,
            )
        )
    return result


# ---------- кандидат ----------


async def _eligible(db: AsyncSession, candidate: Candidate, challenge: Challenge) -> bool:
    if challenge.status != ChallengeStatus.published:
        return False
    if challenge.employer_id in set(candidate.hidden_employer_ids or []):
        return False
    current = await categories_service.get_current(db, candidate.id)
    specialization = current.specialization if current else candidate.specialization
    if challenge.specialization != specialization:
        return False
    return challenge.grade is None or (current is not None and current.grade == challenge.grade)


async def _company_names(db: AsyncSession, employer_ids: set[int]) -> dict[int, str]:
    if not employer_ids:
        return {}
    rows = await db.execute(select(Employer.id, Employer.company_name).where(Employer.id.in_(employer_ids)))
    return {employer_id: name or "Компания" for employer_id, name in rows}


def _sample_size(challenge: Challenge) -> int:
    return challenge.questions_per_attempt or len(challenge.questions)


async def available(db: AsyncSession, candidate: Candidate) -> list[ChallengeCard]:
    """Опубликованные челленджи по категории кандидата и те, что он уже начинал."""
    mine = {
        attempt.challenge_id: attempt
        for attempt in await db.scalars(
            select(ChallengeAttempt).where(ChallengeAttempt.candidate_id == candidate.id)
        )
    }
    rows = await db.scalars(
        select(Challenge)
        .where((Challenge.status == ChallengeStatus.published) | Challenge.id.in_(list(mine)))
        .order_by(Challenge.published_at.desc().nulls_last(), Challenge.id.desc())
    )
    challenges = [c for c in rows if c.id in mine or await _eligible(db, candidate, c)]
    names = await _company_names(db, {c.employer_id for c in challenges})
    skill_names = {skill.id: skill.name for skill in get_catalog().skills}
    cards = []
    for challenge in challenges:
        attempt = mine.get(challenge.id)
        done = attempt is not None and attempt.status == ChallengeAttemptStatus.completed
        cards.append(
            ChallengeCard(
                id=challenge.id,
                company_name=names.get(challenge.employer_id, "Компания"),
                title=challenge.title,
                description=challenge.description,
                specialization=challenge.specialization,
                grade=challenge.grade,
                skills=[skill_names.get(s, s) for s in challenge.skills or []],
                questions=_sample_size(challenge),
                time_per_question_sec=challenge.time_per_question_sec,
                published_at=challenge.published_at,
                attempt_id=attempt.id if attempt else None,
                attempt_status=attempt.status if attempt else None,
                score=attempt.score if done else None,
            )
        )
    return cards


def _new_items(challenge: Challenge) -> list[dict[str, Any]]:
    # Свой набор вопросов, порядок и метки вариантов у каждой попытки: «ответ — b» из чата не подходит
    rng = random.SystemRandom()
    chosen = rng.sample(challenge.questions, _sample_size(challenge))
    items = []
    for question in chosen:
        shuffled = rng.sample(question["options"], len(question["options"]))
        items.append(
            {
                "question_id": question["id"],
                "option_map": {str(i): option["id"] for i, option in enumerate(shuffled, 1)},
                "shown_at": None,
                "answered_at": None,
                "response": None,
                "score": None,
                "late": False,
            }
        )
    return items


async def start(db: AsyncSession, candidate: Candidate, challenge_id: int) -> ChallengeAttemptResult:
    challenge = await db.get(Challenge, challenge_id)
    existing = await db.scalar(
        select(ChallengeAttempt).where(
            ChallengeAttempt.challenge_id == challenge_id, ChallengeAttempt.candidate_id == candidate.id
        )
    )
    if existing is not None:
        return await _result(db, existing)  # одна попытка на кандидата: повторный старт возвращает её же
    if challenge is None or not await _eligible(db, candidate, challenge):
        raise NotFoundError("Челлендж не найден")
    attempt = ChallengeAttempt(
        challenge_id=challenge.id,
        candidate_id=candidate.id,
        status=ChallengeAttemptStatus.in_progress,
        items=_new_items(challenge),
    )
    db.add(attempt)
    try:
        await db.commit()
    except IntegrityError:
        # Параллельный старт: уникальность (challenge_id, candidate_id) оставила одну попытку
        await db.rollback()
        attempt = await db.scalar(
            select(ChallengeAttempt).where(
                ChallengeAttempt.challenge_id == challenge_id, ChallengeAttempt.candidate_id == candidate.id
            )
        )
    await db.refresh(attempt)
    return await _result(db, attempt)


async def _own_attempt(
    db: AsyncSession, candidate: Candidate, attempt_id: int, lock: bool = False
) -> tuple[ChallengeAttempt, Challenge]:
    # lock — ответы и выдача вопросов по одной попытке идут последовательно (как в тесте, §10.3)
    attempt = await db.get(ChallengeAttempt, attempt_id, with_for_update=lock)
    if attempt is None or attempt.candidate_id != candidate.id:
        raise NotFoundError("Попытка не найдена")
    return attempt, await db.get(Challenge, attempt.challenge_id)


def _deadline(item: dict[str, Any], challenge: Challenge) -> datetime:
    return _at(item["shown_at"]) + timedelta(seconds=challenge.time_per_question_sec)


def _is_late(item: dict[str, Any], challenge: Challenge, at: datetime) -> bool:
    return at > _deadline(item, challenge) + timedelta(seconds=get_settings().answer_grace_seconds)


def finalize(
    attempt: ChallengeAttempt, challenge: Challenge, items: list[dict[str, Any]], at: datetime
) -> None:
    kinds = {q["id"]: q["kind"] for q in challenge.questions}
    scored = [item for item in items if kinds[item["question_id"]] != "open_approach"]
    attempt.correct = sum(1 for item in scored if item["score"] == 1.0)
    attempt.scored_total = len(scored)
    attempt.score = round(attempt.correct / len(scored), 4) if scored else None
    attempt.status = ChallengeAttemptStatus.completed
    attempt.finished_at = at


def _item_out(
    index: int, item: dict[str, Any], question: dict[str, Any], challenge: Challenge, total: int
) -> CurrentItem:
    texts = {option["id"]: option["text"] for option in question["options"]}
    return CurrentItem(
        finished=False,
        item_id=index + 1,
        position=index + 1,
        total_estimate=total,
        total_max=total,
        kind=question["kind"],
        stem=question["text"],
        code=question["code"],
        options=[
            ItemOption(id=shown, text=texts[original]) for shown, original in item["option_map"].items()
        ],
        topics=0,
        time_limit_sec=challenge.time_per_question_sec,
        deadline_at=_deadline(item, challenge),
    )


async def current(db: AsyncSession, candidate: Candidate, attempt_id: int) -> CurrentItem:
    attempt, challenge = await _own_attempt(db, candidate, attempt_id, lock=True)
    if attempt.status == ChallengeAttemptStatus.completed:
        return CurrentItem(finished=True, topics=0)
    now = _now()
    items = [dict(item) for item in attempt.items]
    questions = {q["id"]: q for q in challenge.questions}
    for index, item in enumerate(items):
        if item["answered_at"] is not None:
            continue
        if item["shown_at"] is None:
            item["shown_at"] = now.isoformat()
        elif _is_late(item, challenge, now):
            # Время вышло без ответа — засчитывается как неверный, открытый — как пустой
            kind = questions[item["question_id"]]["kind"]
            item.update(
                answered_at=now.isoformat(), late=True, score=None if kind == "open_approach" else 0.0
            )
            continue
        attempt.items = items
        await db.commit()
        return _item_out(index, item, questions[item["question_id"]], challenge, len(items))
    attempt.items = items
    finalize(attempt, challenge, items, now)
    await db.commit()
    return CurrentItem(finished=True, topics=0)


async def answer(db: AsyncSession, candidate: Candidate, attempt_id: int, body: AnswerRequest) -> AnswerAck:
    attempt, challenge = await _own_attempt(db, candidate, attempt_id, lock=True)
    if attempt.status == ChallengeAttemptStatus.completed:
        raise ConflictError("Челлендж уже пройден", code="attempt_finished")
    items = [dict(item) for item in attempt.items]
    index = next((i for i, item in enumerate(items) if item["answered_at"] is None), None)
    if index is None or items[index]["shown_at"] is None or body.item_id != index + 1:
        raise ConflictError("Это вопрос уже не текущий", code="not_current_item")
    item = items[index]
    question = next(q for q in challenge.questions if q["id"] == item["question_id"])
    now = _now()
    late = _is_late(item, challenge, now)
    response = body.response.model_dump(exclude_none=True)
    if question["kind"] == "open_approach":
        text = (response.get("text") or "").strip()
        item.update(response={"text": text} if text else None, score=None)
    else:
        if "choice_ids" in response:
            response["choice_ids"] = sorted(
                item["option_map"][shown] for shown in response["choice_ids"] if shown in item["option_map"]
            )
        item.update(
            response=response,
            score=0.0 if late else score_response(question["kind"], question["key"], response),
        )
    item.update(answered_at=now.isoformat(), late=late)
    attempt.items = items
    finished = all(entry["answered_at"] is not None for entry in items)
    if finished:
        finalize(attempt, challenge, items, now)
    await db.commit()
    return AnswerAck(accepted=True, late=late, finished=finished)


async def _result(db: AsyncSession, attempt: ChallengeAttempt) -> ChallengeAttemptResult:
    challenge = await db.get(Challenge, attempt.challenge_id)
    names = await _company_names(db, {challenge.employer_id})
    return ChallengeAttemptResult(
        attempt_id=attempt.id,
        challenge_id=challenge.id,
        title=challenge.title,
        company_name=names.get(challenge.employer_id, "Компания"),
        status=attempt.status,
        answered=sum(1 for item in attempt.items if item["answered_at"] is not None),
        total=len(attempt.items),
        correct=attempt.correct,
        scored_total=attempt.scored_total,
        score=attempt.score,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
    )


async def result(db: AsyncSession, candidate: Candidate, attempt_id: int) -> ChallengeAttemptResult:
    attempt, _ = await _own_attempt(db, candidate, attempt_id)
    return await _result(db, attempt)


async def forget_candidate(db: AsyncSession, candidate_id: int) -> None:
    """Удаление аккаунта: текст открытых ответов — ПДн и удаляется, баллы остаются. Коммитит вызывающий."""
    attempts = await db.scalars(select(ChallengeAttempt).where(ChallengeAttempt.candidate_id == candidate_id))
    for attempt in attempts:
        attempt.items = [
            {**item, "response": None} if item.get("response") and "text" in item["response"] else item
            for item in attempt.items
        ]
