"""Modified Angoff для порогов грейдов (§10.4, §12.4): набор шаблонов, оценки экспертов и рекомендация.

Эксперт видит пример экземпляра без ключа ответа и без параметров IRT — только текст задания.
Пороги в content/blueprints.yaml автоматически не меняются: сводка — рекомендация для команды.
"""

import hashlib
import math
from collections import defaultdict
from functools import lru_cache
from statistics import mean, stdev

import yaml
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Grade
from app.core.errors import NotFoundError
from app.modules.auth import service as auth_service
from app.modules.catalog.service import get_catalog
from app.modules.expert.models import AngoffRating
from app.modules.expert.schemas import (
    AngoffGradeSummary,
    AngoffProgress,
    AngoffRaterCut,
    AngoffRatingRequest,
    AngoffSummary,
    AngoffTask,
    AngoffTasks,
)
from app.modules.testing import explainer_service
from app.modules.testing.engine.angoff import AngoffItem, angoff_cut
from app.modules.testing.engine.bank import CONTENT_DIR, GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.schemas import ExplainerTemplate


class AngoffConfig(BaseModel):
    items: int
    window: float
    window_step: float
    instance_seed: int
    rating_step: float


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
    db: AsyncSession, specialization: str, grade: Grade, rater: str | None = None
) -> list[AngoffRating]:
    query = select(AngoffRating).where(
        AngoffRating.specialization == specialization, AngoffRating.grade == grade
    )
    if rater is not None:
        query = query.where(AngoffRating.rater_email == rater)
    return list(await db.scalars(query))


async def _progress(db: AsyncSession, rater: str, specialization: str, grade: Grade) -> AngoffProgress:
    ids = [t.id for t in template_set(specialization, grade.value)]
    done = await db.scalar(
        select(func.count())
        .select_from(AngoffRating)
        .where(
            AngoffRating.rater_email == rater,
            AngoffRating.specialization == specialization,
            AngoffRating.grade == grade,
            AngoffRating.template_id.in_(ids),
        )
    )
    return AngoffProgress(done=done or 0, total=len(ids))


async def tasks(db: AsyncSession, user_id: int, specialization: str, grade: Grade) -> AngoffTasks:
    templates = template_set(specialization, grade.value)
    rater = await _rater_email(db, user_id)
    current = {r.template_id: r.rating for r in await _ratings(db, specialization, grade, rater)}
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
            )
        )
    return AngoffTasks(
        specialization=specialization,
        grade=grade,
        grade_name=_grade_names().get(grade.value, grade.value),
        rating_step=get_config().rating_step,
        progress=await _progress(db, rater, specialization, grade),
        tasks=items,
    )


async def rate(db: AsyncSession, user_id: int, body: AngoffRatingRequest) -> AngoffProgress:
    ids = {t.id for t in template_set(body.specialization, body.grade.value)}
    if body.template_id not in ids:
        raise NotFoundError("Шаблона нет в наборе для этого грейда", code="template_not_found")
    rater = await _rater_email(db, user_id)
    values = {
        "rater_email": rater,
        "specialization": body.specialization,
        "grade": body.grade,
        "template_id": body.template_id,
        "rating": body.rating,
    }
    await db.execute(
        insert(AngoffRating)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_angoff_ratings_rater_item",
            set_={"rating": body.rating, "updated_at": func.now()},
        )
    )
    await db.commit()
    return await _progress(db, rater, body.specialization, body.grade)


async def summary(db: AsyncSession, expert_id: int | None, specialization: str) -> AngoffSummary:
    """expert_id — для пометки «это вы»; у администратора None."""
    explainer_service.templates(specialization)  # 404, если теста нет
    me = await _rater_email(db, expert_id) if expert_id is not None else None
    blueprints, names = get_blueprints(), _grade_names()
    grades = []
    for grade in (Grade(g) for g in GRADE_ORDER):
        templates = template_set(specialization, grade.value)
        ids = [t.id for t in templates]
        items = _items(templates)
        by_rater: dict[str, dict[str, float]] = defaultdict(dict)
        for row in await _ratings(db, specialization, grade):
            if row.template_id in ids:
                by_rater[row.rater_email][row.template_id] = row.rating
        complete = sorted(email for email, values in by_rater.items() if len(values) == len(ids))
        if not complete:
            continue
        results = [angoff_cut(items, [by_rater[email][tid] for tid in ids]) for email in complete]
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
        current = blueprints.cut(grade.value)
        grades.append(
            AngoffGradeSummary(
                grade=grade,
                grade_name=names.get(grade.value, grade.value),
                items=len(ids),
                raters=len(complete),
                incomplete_raters=len(by_rater) - len(complete),
                rater_cuts=rater_cuts,
                mean_cut=round(mean(cuts), 3),
                sd=None if sd is None else round(sd, 3),
                se=None if sd is None else round(sd / math.sqrt(len(cuts)), 3),
                current_cut=current,
                difference=round(mean(cuts) - current, 3),
            )
        )
    return AngoffSummary(specialization=specialization, grades=grades)
