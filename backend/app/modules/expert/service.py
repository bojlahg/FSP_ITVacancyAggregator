"""Экспертная разметка пар «потребность — кандидат» (§12.2): набор пар, оценки 0–3 и метрики подбора.

Эксперт видит обезличенную карточку без score, объяснения и места в выдаче — разметка «вслепую».
Метрики: P@5 выдачи ITScout и базовой линии по ключевым словам на экспертных оценках, корреляция
Спирмена score со средней оценкой и согласие экспертов между собой.
"""

import hashlib
from collections import defaultdict
from itertools import combinations

from scipy.stats import spearmanr
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.auth import service as auth_service
from app.modules.catalog.service import get_catalog
from app.modules.categories import service as categories_service
from app.modules.expert.models import ExpertLabel, ExpertPair
from app.modules.expert.schemas import (
    ExpertNeed,
    ExpertProgress,
    ExpertSummary,
    ExpertTask,
    RankerQuality,
)
from app.modules.matching import scoring
from app.modules.matching import service as matching_service
from app.modules.matching.schemas import CandidateCard
from app.modules.needs import service as needs_service
from app.modules.needs.models import HiringNeed

RANKERS = {"ours": "ITScout: выдача по потребности", "keyword": "Ключевые слова профиля"}


def _config() -> dict[str, float]:
    return scoring.get_rules().expert


def _need_snapshot(need: HiringNeed) -> dict:
    catalog = get_catalog()
    skills = {skill.id: skill.name for skill in catalog.skills}
    industries = {item.slug: item.name for item in catalog.industries}
    return ExpertNeed(
        title=need.title,
        category=categories_service.category_ref(need.specialization, need.grade.value).label,
        required_skills=[skills.get(s, s) for s in need.required_skills or []],
        optional_skills=[skills.get(s, s) for s in need.optional_skills or []],
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        work_format=need.work_format.value if need.work_format else None,
        city=need.city,
        industry=industries.get(need.industry or "", need.industry),
        team_description=need.team_description,
    ).model_dump(mode="json")


def _spread(needs: list[HiringNeed], limit: int) -> list[HiringNeed]:
    """Поровну по специализациям: по одной потребности из каждой по кругу."""
    by_spec: dict[str, list[HiringNeed]] = defaultdict(list)
    for need in needs:
        by_spec[need.specialization].append(need)
    chosen: list[HiringNeed] = []
    while len(chosen) < limit and any(by_spec.values()):
        for spec in sorted(by_spec):
            if by_spec[spec] and len(chosen) < limit:
                chosen.append(by_spec[spec].pop(0))
    return chosen


async def ensure_pairs(db: AsyncSession) -> int:
    """Набор пар формируется один раз — при первом обращении эксперта; дальше он не меняется."""
    existing = await db.scalar(select(func.count()).select_from(ExpertPair))
    if existing:
        return existing
    cfg = _config()
    top_k = int(cfg["top_k"])
    for need in _spread(await needs_service.active_latest_needs(db), int(cfg["needs"])):
        ours = await matching_service.rank_for_need(db, need)
        keyword = await matching_service.keyword_rank(db, need)
        ours_rank = {cid: index + 1 for index, (cid, _score) in enumerate(ours)}
        ours_score = dict(ours)
        keyword_rank = {cid: index + 1 for index, cid in enumerate(keyword)}
        candidates = [cid for cid, _ in ours[:top_k]] + keyword[:top_k]
        snapshot = _need_snapshot(need)
        for candidate_id in dict.fromkeys(candidates):
            card = await matching_service.blind_card(db, need.employer_id, candidate_id)
            await db.execute(
                insert(ExpertPair)
                .values(
                    need_id=need.id,
                    candidate_id=candidate_id,
                    need_snapshot=snapshot,
                    candidate_snapshot=card.model_dump(mode="json"),
                    ours_rank=ours_rank.get(candidate_id),
                    ours_score=ours_score.get(candidate_id),
                    keyword_rank=keyword_rank.get(candidate_id),
                )
                .on_conflict_do_nothing()
            )
    await db.commit()
    return await db.scalar(select(func.count()).select_from(ExpertPair)) or 0


def _order_key(pair: ExpertPair, rater: str) -> tuple:
    # Пары одной потребности подряд, внутри — псевдослучайно для каждого эксперта: место в выдаче не угадать
    digest = hashlib.sha256(f"{rater}:{pair.id}".encode()).hexdigest()
    return (pair.need_id, digest)


async def _rater_email(db: AsyncSession, user_id: int) -> str:
    return (await auth_service.get_user(db, user_id)).email.lower()


async def _progress(db: AsyncSession, rater: str, total: int) -> ExpertProgress:
    query = select(func.count()).select_from(ExpertLabel).where(ExpertLabel.rater_email == rater)
    done = await db.scalar(query)
    return ExpertProgress(done=done or 0, total=total)


async def next_task(db: AsyncSession, user_id: int) -> ExpertTask:
    total = await ensure_pairs(db)
    rater = await _rater_email(db, user_id)
    labeled = select(ExpertLabel.pair_id).where(ExpertLabel.rater_email == rater)
    pending = list(await db.scalars(select(ExpertPair).where(ExpertPair.id.not_in(labeled))))
    progress = await _progress(db, rater, total)
    if not pending:
        return ExpertTask(progress=progress, pair_id=None, need=None, candidate=None)
    pair = min(pending, key=lambda item: _order_key(item, rater))
    return ExpertTask(
        progress=progress,
        pair_id=pair.id,
        need=ExpertNeed.model_validate(pair.need_snapshot),
        candidate=CandidateCard.model_validate(pair.candidate_snapshot),
    )


async def label(db: AsyncSession, user_id: int, pair_id: int, value: int) -> ExpertProgress:
    if await db.get(ExpertPair, pair_id) is None:
        raise NotFoundError("Пара не найдена")
    rater = await _rater_email(db, user_id)
    await db.execute(
        insert(ExpertLabel)
        .values(pair_id=pair_id, rater_email=rater, label=value)
        .on_conflict_do_update(constraint="uq_expert_labels_pair_rater", set_={"label": value})
    )
    await db.commit()
    total = await db.scalar(select(func.count()).select_from(ExpertPair)) or 0
    return await _progress(db, rater, total)


def _precision_at_5(pairs: list[ExpertPair], means: dict[int, float], attr: str, relevant: float) -> tuple:
    by_need: dict[int, list[ExpertPair]] = defaultdict(list)
    for pair in pairs:
        rank = getattr(pair, attr)
        if rank is not None and rank <= 5:
            by_need[pair.need_id].append(pair)
    values = [
        sum(means[p.id] >= relevant for p in top) / 5
        for top in by_need.values()
        if len(top) == 5 and all(p.id in means for p in top)
    ]
    return (round(sum(values) / len(values), 3) if values else None), len(values)


def _weighted_kappa(pairs: list[tuple[int, int]], categories: int = 4) -> float | None:
    """Квадратично взвешенная κ Коэна по парам оценок двух экспертов (симметризованная)."""
    if len(pairs) < 2:
        return None
    observed = [[0.0] * categories for _ in range(categories)]
    for a, b in pairs:
        observed[a][b] += 0.5
        observed[b][a] += 0.5
    total = len(pairs)
    marginal = [sum(row) / total for row in observed]
    weight = [[(i - j) ** 2 / (categories - 1) ** 2 for j in range(categories)] for i in range(categories)]
    cells = [(i, j) for i in range(categories) for j in range(categories)]
    disagreement = sum(weight[i][j] * observed[i][j] / total for i, j in cells)
    expected = sum(weight[i][j] * marginal[i] * marginal[j] for i, j in cells)
    return round(1 - disagreement / expected, 3) if expected else None


async def summary(db: AsyncSession) -> ExpertSummary:
    cfg = _config()
    relevant = float(cfg["relevant_from"])
    pairs = list(await db.scalars(select(ExpertPair)))
    labels = list(await db.scalars(select(ExpertLabel)))
    by_pair: dict[int, list[int]] = defaultdict(list)
    for item in labels:
        by_pair[item.pair_id].append(item.label)
    means = {pair_id: sum(values) / len(values) for pair_id, values in by_pair.items()}

    rankers = []
    for attr, name in (("ours_rank", RANKERS["ours"]), ("keyword_rank", RANKERS["keyword"])):
        precision, needs = _precision_at_5(pairs, means, attr, relevant)
        rankers.append(RankerQuality(name=name, precision_at_5=precision, needs=needs))

    scored = [(p.ours_score, means[p.id]) for p in pairs if p.id in means and p.ours_score is not None]
    rho = None
    if len(scored) >= 5 and len({s for s, _ in scored}) > 1 and len({m for _, m in scored}) > 1:
        rho = round(float(spearmanr([s for s, _ in scored], [m for _, m in scored]).statistic), 3)

    rater_pairs = [
        pair for values in by_pair.values() if len(values) >= 2 for pair in combinations(values, 2)
    ]
    multi = sum(len(values) >= 2 for values in by_pair.values())
    exact = round(sum(a == b for a, b in rater_pairs) / len(rater_pairs), 3) if rater_pairs else None
    return ExpertSummary(
        raters=len({item.rater_email for item in labels}),
        labels=len(labels),
        pairs_total=len(pairs),
        pairs_labeled=len(by_pair),
        relevant_from=relevant,
        rankers=rankers,
        spearman=rho,
        spearman_pairs=len(scored),
        agreement_pairs=multi,
        exact_agreement=exact,
        weighted_kappa=_weighted_kappa(rater_pairs),
    )
