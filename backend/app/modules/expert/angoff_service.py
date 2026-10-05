"""Modified Angoff для порогов грейдов (§10.4, §12.4): набор шаблонов, оценки экспертов и рекомендация.

Эксперт видит пример экземпляра без ключа ответа и без параметров IRT — только текст задания.
Два раунда: после раунда 1 — данные о последствиях (доли кандидатов по грейдам) и оценки группы,
в раунде 2 — пересмотр. Проверка Hofstee сравнивает порог Angoff с окном допустимых значений экспертов.
Пороги в content/blueprints.yaml автоматически не меняются: сводка — рекомендация для команды.
"""

import hashlib
import math
import random
from collections import defaultdict
from functools import lru_cache
from statistics import mean, median, stdev
from typing import Literal

import yaml
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Grade
from app.core.errors import ConflictError, NotFoundError
from app.modules.auth import service as auth_service
from app.modules.catalog.service import get_catalog
from app.modules.expert.models import AngoffHofstee, AngoffRating
from app.modules.expert.schemas import (
    AngoffBandShare,
    AngoffGradeSummary,
    AngoffGroupFeedback,
    AngoffHofsteeCheck,
    AngoffHofsteeRequest,
    AngoffHofsteeValues,
    AngoffImpact,
    AngoffItemFeedback,
    AngoffProgress,
    AngoffRaterCut,
    AngoffRatingRequest,
    AngoffRoundSummary,
    AngoffSummary,
    AngoffTask,
    AngoffTasks,
)
from app.modules.testing import explainer_service
from app.modules.testing import service as testing_service
from app.modules.testing.engine.angoff import (
    AngoffCut,
    AngoffItem,
    HofsteeBox,
    angoff_cut,
    fail_rate,
    hofstee,
    in_hofstee_box,
    share_to_theta,
    theta_to_share,
)
from app.modules.testing.engine.bank import CONTENT_DIR, GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.confidence import BELOW, band_of
from app.modules.testing.schemas import ExplainerTemplate

ROUNDS = (1, 2)
ImpactSource = Literal["results", "synthetic"]


class SyntheticPopulation(BaseModel):
    size: int
    seed: int
    grade_share: dict[str, float]
    theta_mean: dict[str, float]
    theta_sd: float


class ImpactConfig(BaseModel):
    min_candidates: int
    synthetic: SyntheticPopulation


class HofsteeDefaults(BaseModel):
    min_cut: float
    max_cut: float
    min_fail: float
    max_fail: float


class AngoffConfig(BaseModel):
    items: int
    window: float
    window_step: float
    instance_seed: int
    rating_step: float
    recommended_raters: int
    feedback_min_raters: int
    impact: ImpactConfig
    hofstee_defaults: dict[str, HofsteeDefaults]


@lru_cache
def get_config() -> AngoffConfig:
    with (CONTENT_DIR / "angoff.yaml").open(encoding="utf-8") as file:
        return AngoffConfig.model_validate(yaml.safe_load(file))


def _hash(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()


@lru_cache(maxsize=64)
def template_set(specialization: str, grade: str) -> tuple[ExplainerTemplate, ...]:
    """Детерминированный набор шаблонов у порога грейда, равномерно по сложности (content/angoff.yaml)."""
    cfg = get_config()
    pool = explainer_service.templates(specialization)  # 404 specialization_not_found
    cut = get_blueprints().cut(grade)
    window = cfg.window
    while True:
        near = sorted((t for t in pool if abs(t.b - cut) <= window), key=lambda t: (t.b, t.id))
        if len(near) >= cfg.items or len(near) == len(pool):
            break
        window += cfg.window_step
    count = min(cfg.items, len(near))
    groups = [near[i * len(near) // count : (i + 1) * len(near) // count] for i in range(count)]
    chosen = [min(group, key=lambda t: _hash(specialization, grade, t.id)) for group in groups]
    # Порядок показа не по сложности: иначе эксперт угадывает b по месту в списке
    return tuple(sorted(chosen, key=lambda t: _hash("order", specialization, grade, t.id)))


def _grade_names() -> dict[str, str]:
    return {item.slug.value: item.name for item in get_catalog().grades}


def _items(templates: tuple[ExplainerTemplate, ...]) -> list[AngoffItem]:
    bank = get_bank().templates
    # c берём из банка без округления: ExplainerTemplate.c округлён до 4 знаков
    return [AngoffItem(t.a, t.b, bank[t.id].guessing) for t in templates]


async def _rater_email(db: AsyncSession, user_id: int) -> str:
    return (await auth_service.get_user(db, user_id)).email.lower()


async def _ratings(
    db: AsyncSession, specialization: str, grade: Grade, rater: str | None = None, round_: int | None = None
) -> list[AngoffRating]:
    query = select(AngoffRating).where(
        AngoffRating.specialization == specialization, AngoffRating.grade == grade
    )
    if rater is not None:
        query = query.where(AngoffRating.rater_email == rater)
    if round_ is not None:
        query = query.where(AngoffRating.round == round_)
    return list(await db.scalars(query))


def _by_rater(rows: list[AngoffRating], ids: list[str], round_: int) -> dict[str, dict[str, float]]:
    by_rater: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        if row.round == round_ and row.template_id in ids:
            by_rater[row.rater_email][row.template_id] = row.rating
    return by_rater


def _complete(by_rater: dict[str, dict[str, float]], ids: list[str]) -> list[str]:
    return sorted(email for email, values in by_rater.items() if len(values) == len(ids))


async def _progress(
    db: AsyncSession, rater: str, specialization: str, grade: Grade, round_: int
) -> AngoffProgress:
    ids = [t.id for t in template_set(specialization, grade.value)]
    done = await db.scalar(
        select(func.count())
        .select_from(AngoffRating)
        .where(
            AngoffRating.rater_email == rater,
            AngoffRating.specialization == specialization,
            AngoffRating.grade == grade,
            AngoffRating.round == round_,
            AngoffRating.template_id.in_(ids),
        )
    )
    return AngoffProgress(done=done or 0, total=len(ids))


async def _require_round1(db: AsyncSession, rater: str, specialization: str, grade: Grade) -> None:
    progress = await _progress(db, rater, specialization, grade, 1)
    if progress.done < progress.total:
        raise ConflictError(
            "Сначала оцените все задания в раунде 1 — затем откроются данные о последствиях и раунд 2",
            code="round1_incomplete",
        )


async def _own_hofstee(
    db: AsyncSession, rater: str, specialization: str, grade: Grade
) -> AngoffHofsteeValues | None:
    row = await db.scalar(
        select(AngoffHofstee).where(
            AngoffHofstee.rater_email == rater,
            AngoffHofstee.specialization == specialization,
            AngoffHofstee.grade == grade,
        )
    )
    return None if row is None else _hofstee_values(row)


def _hofstee_values(row: AngoffHofstee | HofsteeDefaults) -> AngoffHofsteeValues:
    return AngoffHofsteeValues(
        min_cut=row.min_cut, max_cut=row.max_cut, min_fail=row.min_fail, max_fail=row.max_fail
    )


def _group_feedback(rows: list[AngoffRating], ids: list[str]) -> dict[str, AngoffItemFeedback]:
    """Оценки группы в раунде 1 по каждому заданию — только экспертов, прошедших раунд 1 целиком."""
    by_rater = _by_rater(rows, ids, 1)
    complete = _complete(by_rater, ids)
    if len(complete) < get_config().feedback_min_raters:
        return {}
    result = {}
    for template_id in ids:
        values = [by_rater[email][template_id] for email in complete]
        result[template_id] = AngoffItemFeedback(
            raters=len(values), median=round(median(values), 3), low=min(values), high=max(values)
        )
    return result


async def tasks(
    db: AsyncSession, user_id: int, specialization: str, grade: Grade, round_: int = 1
) -> AngoffTasks:
    templates = template_set(specialization, grade.value)
    ids = [t.id for t in templates]
    rater = await _rater_email(db, user_id)
    round1 = await _progress(db, rater, specialization, grade, 1)
    round1_complete = round1.done == round1.total
    if round_ == 2 and not round1_complete:
        await _require_round1(db, rater, specialization, grade)
    own = await _ratings(db, specialization, grade, rater)
    current = {r.template_id: r.rating for r in own if r.round == round_}
    first = {r.template_id: r.rating for r in own if r.round == 1}
    group = _group_feedback(await _ratings(db, specialization, grade, round_=1), ids) if round_ == 2 else {}
    seed = get_config().instance_seed
    items = []
    for template in templates:
        # Тот же рендер без ключа, что и на странице «Как работает тест»
        instance = explainer_service.instances(template.id, [seed]).instances[0]
        items.append(
            AngoffTask(
                template_id=template.id,
                topic_name=template.topic_name,
                kind=template.kind,
                instance=instance,
                rating=current.get(template.id),
                round1_rating=first.get(template.id) if round_ == 2 else None,
                group=group.get(template.id),
            )
        )
    defaults = get_config().hofstee_defaults[grade.value]
    return AngoffTasks(
        specialization=specialization,
        grade=grade,
        grade_name=_grade_names().get(grade.value, grade.value),
        round=round_,
        rating_step=get_config().rating_step,
        progress=round1 if round_ == 1 else await _progress(db, rater, specialization, grade, 2),
        round1_complete=round1_complete,
        round2_started=any(r.round == 2 for r in own),
        hofstee=await _own_hofstee(db, rater, specialization, grade),
        hofstee_defaults=_hofstee_values(defaults),
        tasks=items,
    )


async def rate(db: AsyncSession, user_id: int, body: AngoffRatingRequest) -> AngoffProgress:
    ids = {t.id for t in template_set(body.specialization, body.grade.value)}
    if body.template_id not in ids:
        raise NotFoundError("Шаблона нет в наборе для этого грейда", code="template_not_found")
    rater = await _rater_email(db, user_id)
    if body.round == 2:
        await _require_round1(db, rater, body.specialization, body.grade)
    values = {
        "rater_email": rater,
        "specialization": body.specialization,
        "grade": body.grade,
        "template_id": body.template_id,
        "round": body.round,
        "rating": body.rating,
    }
    await db.execute(
        insert(AngoffRating)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_angoff_ratings_rater_item_round",
            set_={"rating": body.rating, "updated_at": func.now()},
        )
    )
    await db.commit()
    return await _progress(db, rater, body.specialization, body.grade, body.round)


async def start_round2(db: AsyncSession, user_id: int, specialization: str, grade: Grade) -> AngoffProgress:
    """Раунд 2 начинается с копии оценок раунда 1: эксперт меняет только то, что хочет пересмотреть."""
    template_set(specialization, grade.value)  # 404, если теста нет
    rater = await _rater_email(db, user_id)
    await _require_round1(db, rater, specialization, grade)
    first = await _ratings(db, specialization, grade, rater, round_=1)
    rows = [
        {
            "rater_email": rater,
            "specialization": specialization,
            "grade": grade,
            "template_id": row.template_id,
            "round": 2,
            "rating": row.rating,
        }
        for row in first
    ]
    if rows:
        await db.execute(
            insert(AngoffRating)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_angoff_ratings_rater_item_round")
        )
        await db.commit()
    return await _progress(db, rater, specialization, grade, 2)


async def save_hofstee(db: AsyncSession, user_id: int, body: AngoffHofsteeRequest) -> AngoffHofsteeValues:
    template_set(body.specialization, body.grade.value)  # 404, если теста нет
    rater = await _rater_email(db, user_id)
    values = body.model_dump(include={"min_cut", "max_cut", "min_fail", "max_fail"})
    await db.execute(
        insert(AngoffHofstee)
        .values(rater_email=rater, specialization=body.specialization, grade=body.grade, **values)
        .on_conflict_do_update(
            constraint="uq_angoff_hofstee_rater_grade", set_={**values, "updated_at": func.now()}
        )
    )
    await db.commit()
    return AngoffHofsteeValues(**values)


# ---------- данные о последствиях ----------


@lru_cache
def synthetic_thetas() -> tuple[float, ...]:
    """Синтетическая популяция (как в validation/population.py): смесь нормальных распределений по грейдам."""
    cfg = get_config().impact.synthetic
    rng = random.Random(f"angoff-impact:{cfg.seed}")
    components = list(cfg.grade_share)
    weights = list(cfg.grade_share.values())
    return tuple(
        rng.gauss(cfg.theta_mean[component], cfg.theta_sd)
        for component in rng.choices(components, weights=weights, k=cfg.size)
    )


async def population(db: AsyncSession, specialization: str) -> tuple[list[float], ImpactSource]:
    thetas = await testing_service.latest_thetas(db, specialization)
    if len(thetas) >= get_config().impact.min_candidates:
        return thetas, "results"
    return list(synthetic_thetas()), "synthetic"


def _bands(
    thetas: list[float], current: dict[str, float], proposed: dict[str, float]
) -> list[AngoffBandShare]:
    names = {BELOW: "Ниже стажёра", **_grade_names()}
    now = [band_of(theta, current) for theta in thetas]
    then = [band_of(theta, proposed) for theta in thetas]
    total = max(len(thetas), 1)
    return [
        AngoffBandShare(
            band=band,
            name=names.get(band, band),
            current=round(now.count(band) / total, 4),
            proposed=round(then.count(band) / total, 4),
        )
        for band in (BELOW, *GRADE_ORDER)
    ]


async def impact(db: AsyncSession, user_id: int, specialization: str, grade: Grade) -> AngoffImpact:
    """Данные о последствиях после раунда 1: что изменится в распределении кандидатов при таком пороге."""
    templates = template_set(specialization, grade.value)
    ids = [t.id for t in templates]
    rater = await _rater_email(db, user_id)
    await _require_round1(db, rater, specialization, grade)
    items = _items(templates)
    by_rater = _by_rater(await _ratings(db, specialization, grade, round_=1), ids, 1)
    complete = _complete(by_rater, ids)
    cuts = {email: angoff_cut(items, [by_rater[email][tid] for tid in ids]).theta for email in complete}
    thetas, source = await population(db, specialization)
    current_cuts = dict(get_blueprints().scale.cuts)
    current = current_cuts[grade.value]
    group = None
    proposed = cuts[rater]
    if len(complete) >= get_config().feedback_min_raters:
        values = list(cuts.values())
        proposed = median(values)
        group = AngoffGroupFeedback(
            raters=len(values),
            median_cut=round(proposed, 3),
            min_cut=round(min(values), 3),
            max_cut=round(max(values), 3),
            sd=round(stdev(values), 3) if len(values) >= 2 else None,
        )
    return AngoffImpact(
        specialization=specialization,
        grade=grade,
        grade_name=_grade_names().get(grade.value, grade.value),
        source=source,
        candidates=len(thetas),
        your_cut=round(cuts[rater], 3),
        your_fail_rate=round(fail_rate(thetas, cuts[rater]), 4),
        group=group,
        current_cut=current,
        current_fail_rate=round(fail_rate(thetas, current), 4),
        proposed_cut=round(proposed, 3),
        proposed_fail_rate=round(fail_rate(thetas, proposed), 4),
        bands=_bands(thetas, current_cuts, {**current_cuts, grade.value: proposed}),
    )


# ---------- сводка ----------


def _round_summary(
    round_: int, items: list[AngoffItem], ids: list[str], rows: list[AngoffRating], me: str | None
) -> tuple[AngoffRoundSummary, list[float]] | None:
    by_rater = _by_rater(rows, ids, round_)
    complete = _complete(by_rater, ids)
    if not complete:
        return None
    results: list[AngoffCut] = [
        angoff_cut(items, [by_rater[email][tid] for tid in ids]) for email in complete
    ]
    rater_cuts = [
        AngoffRaterCut(
            rater=f"Эксперт {index}",
            you=email == me,
            cut=round(cut.theta, 3),
            expected_share=round(cut.expected / len(ids), 3),
            clamped=cut.clamped,
        )
        for index, (email, cut) in enumerate(zip(complete, results, strict=True), start=1)
    ]
    # Среднее и разброс — по неокруглённым порогам экспертов
    cuts = [cut.theta for cut in results]
    sd = stdev(cuts) if len(cuts) >= 2 else None
    summary = AngoffRoundSummary(
        round=round_,
        raters=len(complete),
        incomplete_raters=len(by_rater) - len(complete),
        rater_cuts=rater_cuts,
        mean_cut=round(mean(cuts), 3),
        median_cut=round(median(cuts), 3),
        sd=None if sd is None else round(sd, 3),
        se=None if sd is None else round(sd / math.sqrt(len(cuts)), 3),
    )
    return summary, cuts


def hofstee_check(
    items: list[AngoffItem], boxes: list[HofsteeBox], angoff_theta: float, thetas: list[float]
) -> AngoffHofsteeCheck:
    """Окно — средние границы экспертов; кривая — доля кандидатов ниже θ, соответствующего доле верных."""
    box = HofsteeBox(
        min_cut=mean(b.min_cut for b in boxes),
        max_cut=mean(b.max_cut for b in boxes),
        min_fail=mean(b.min_fail for b in boxes),
        max_fail=mean(b.max_fail for b in boxes),
    )
    result = hofstee(box, lambda share: fail_rate(thetas, share_to_theta(items, share)))
    angoff_share = theta_to_share(items, angoff_theta)
    angoff_fail = fail_rate(thetas, angoff_theta)
    return AngoffHofsteeCheck(
        raters=len(boxes),
        box=AngoffHofsteeValues(
            min_cut=round(box.min_cut, 4),
            max_cut=round(box.max_cut, 4),
            min_fail=round(box.min_fail, 4),
            max_fail=round(box.max_fail, 4),
        ),
        cut_share=round(result.cut, 4),
        cut_theta=round(share_to_theta(items, result.cut), 3),
        fail_rate=round(result.fail, 4),
        intersects=result.intersects,
        angoff_share=round(angoff_share, 4),
        angoff_fail_rate=round(angoff_fail, 4),
        in_box=in_hofstee_box(box, angoff_share, angoff_fail),
    )


async def summary(db: AsyncSession, expert_id: int | None, specialization: str) -> AngoffSummary:
    """expert_id — для пометки «это вы»; у администратора None."""
    explainer_service.templates(specialization)  # 404, если теста нет
    me = await _rater_email(db, expert_id) if expert_id is not None else None
    blueprints, names, cfg = get_blueprints(), _grade_names(), get_config()
    thetas, source = await population(db, specialization)
    hofstee_rows = list(
        await db.scalars(select(AngoffHofstee).where(AngoffHofstee.specialization == specialization))
    )
    grades = []
    for grade in (Grade(g) for g in GRADE_ORDER):
        templates = template_set(specialization, grade.value)
        ids = [t.id for t in templates]
        items = _items(templates)
        rows = await _ratings(db, specialization, grade)
        rounds = [result for r in (1, 2) if (result := _round_summary(r, items, ids, rows, me))]
        if not rounds:
            continue
        latest, cuts = rounds[-1]
        recommended = mean(cuts)
        current = blueprints.cut(grade.value)
        boxes = [
            HofsteeBox(row.min_cut, row.max_cut, row.min_fail, row.max_fail)
            for row in hofstee_rows
            if row.grade == grade
        ]
        grades.append(
            AngoffGradeSummary(
                grade=grade,
                grade_name=names.get(grade.value, grade.value),
                items=len(ids),
                rounds=[item for item, _ in rounds],
                recommended_round=latest.round,
                recommended_cut=round(recommended, 3),
                se=latest.se,
                current_cut=current,
                difference=round(recommended - current, 3),
                recommended_raters=cfg.recommended_raters,
                hofstee=hofstee_check(items, boxes, recommended, thetas) if boxes else None,
                impact_source=source,
                impact_candidates=len(thetas),
            )
        )
    return AngoffSummary(specialization=specialization, grades=grades)
