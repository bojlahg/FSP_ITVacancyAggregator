"""Доказательность ФСП (§9.2): сила результата, компетенции (noisy-OR), нижняя граница по разряду. Без БД."""

from dataclasses import dataclass, field
from datetime import date

from app.modules.catalog.service import Catalog

CONFIRMED_MIN_SCORE = 0.5


@dataclass(frozen=True)
class ResultRecord:
    competition_id: str
    competition_name: str
    discipline: str
    level: str
    format: str
    held_on: date
    place: int
    participants: int
    team_role: str | None = None
    prize: str | None = None


@dataclass(frozen=True)
class RankRecord:
    discipline: str
    rank: str
    awarded_at: date


@dataclass
class CompetencyEvidence:
    competency_id: str
    score: float = 0.0
    direct: bool = False
    ranked: bool = False
    evidence: list[dict] = field(default_factory=list)

    @property
    def status(self) -> str:
        """confirmed — прямое измерение (score ≥ 0.5) или разряд; supported — только через роль в команде."""
        confirmed = (self.direct and self.score >= CONFIRMED_MIN_SCORE) or self.ranked
        return "confirmed" if confirmed else "supported"


@dataclass
class FspEvidence:
    strengths: list[float]
    competencies: dict[str, CompetencyEvidence]
    supported_families: set[str]
    max_rank: str | None


def percentile(place: int, participants: int) -> float:
    return 1.0 - (place - 1) / max(participants - 1, 1)


def strength(result: ResultRecord, today: date, catalog: Catalog) -> float:
    """strength = percentile × level_weight × 0.5^(возраст / полураспад) — §9.2."""
    rules = catalog.rules.fsp
    age_years = max((today - result.held_on).days / 365.25, 0.0)
    recency = 0.5 ** (age_years / rules.recency_half_life_years)
    return percentile(result.place, result.participants) * rules.level_weight.get(result.level, 0.4) * recency


def evaluate(
    results: list[ResultRecord], ranks: list[RankRecord], today: date, catalog: Catalog
) -> FspEvidence:
    rules = catalog.rules.fsp
    competencies: dict[str, CompetencyEvidence] = {}
    families: set[str] = set()
    strengths: list[float] = []

    def add(competency_id: str, value: float, direct: bool, result: ResultRecord) -> None:
        item = competencies.setdefault(competency_id, CompetencyEvidence(competency_id))
        # noisy-OR: независимые результаты накапливаются, но не превышают 1
        item.score = 1.0 - (1.0 - item.score) * (1.0 - value)
        item.direct = item.direct or direct
        item.evidence.append(
            {
                "competition": result.competition_name,
                "level": result.level,
                "place": result.place,
                "participants": result.participants,
                "held_on": result.held_on.isoformat(),
                "team_role": result.team_role,
                "link": "direct" if direct else "role",
                "strength": round(value, 3),
            }
        )

    for result in results:
        value = strength(result, today, catalog)
        strengths.append(value)
        discipline = catalog.disciplines.get(result.discipline)
        if discipline is None:
            continue
        for competency_id in discipline.direct:
            add(competency_id, value, True, result)
        link = discipline.by_role.get(result.team_role or "")
        if link:
            for competency_id in link.competencies:
                add(competency_id, value * rules.role_link_factor, False, result)
            if link.supports_family:
                families.add(link.supports_family)

    best_rank = None
    for rank in ranks:
        discipline = catalog.disciplines.get(rank.discipline)
        floor = rules.rank_floor.get(rank.rank, 0.0)
        if discipline is not None:
            for competency_id in discipline.direct:
                item = competencies.setdefault(competency_id, CompetencyEvidence(competency_id))
                item.score = max(item.score, floor)
                item.ranked = True
        if best_rank is None or rules.rank_order.index(rank.rank) > rules.rank_order.index(best_rank):
            best_rank = rank.rank

    return FspEvidence(strengths, competencies, families, best_rank)


def fsp_score(evidence: FspEvidence, specialization: str, catalog: Catalog) -> float:
    """Вклад ФСП в подбор: max(competency × relevance(специализация, компетенция)) — §8.3."""
    relevance = catalog.competency_relevance.get(specialization, {})
    return max(
        (item.score * relevance.get(item.competency_id, 0.0) for item in evidence.competencies.values()),
        default=0.0,
    )
