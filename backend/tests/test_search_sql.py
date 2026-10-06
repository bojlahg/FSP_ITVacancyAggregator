"""Поиск по базе в SQL совпадает с эталонной фильтрацией и сортировкой на Python на случайном пуле."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.enums import Grade
from app.modules.auth.models import User
from app.modules.catalog.service import get_catalog
from app.modules.fsp.models import FspAchievement
from app.modules.matching import service as matching_service
from app.modules.matching.models import CandidateSearchIndex
from app.modules.matching.scoring import get_rules
from app.modules.matching.service import SearchFilters
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, NEED, signup

SKILLS = ["python", "postgresql", "kafka", "docker", "go"]
CITIES = ["Москва", "Казань", None]
FORMATS = [["remote"], ["office"], ["remote", "hybrid"], []]


def reference(
    rows: list[CandidateSearchIndex], filters: SearchFilters, disciplines: set[int], now
) -> list[int]:
    rank_order = get_catalog().rules.fsp.rank_order
    selected = []
    for row in rows:
        statuses = row.skills_status or {}
        if filters.specialization and row.specialization != filters.specialization:
            continue
        if filters.grade and row.grade.value != filters.grade:
            continue
        if any(skill not in statuses for skill in filters.skills):
            continue
        if filters.verified_only and any(statuses.get(skill) != "verified" for skill in filters.skills):
            continue
        if filters.has_fsp is not None and row.has_fsp != filters.has_fsp:
            continue
        if filters.fsp_discipline and row.candidate_id not in disciplines:
            continue
        if filters.fsp_min_rank and (
            not row.max_rank or rank_order.index(row.max_rank) < rank_order.index(filters.fsp_min_rank)
        ):
            continue
        if filters.salary_max and row.salary_min and row.salary_min > filters.salary_max:
            continue
        if filters.work_format and row.work_formats and filters.work_format not in row.work_formats:
            continue
        if filters.city and row.city != filters.city and not row.relocation:
            continue
        days = (now - row.last_activity_at).days if row.last_activity_at else None
        if filters.fresh_days is not None and (days is None or days > filters.fresh_days):
            continue
        selected.append(row)
    keys = {
        # Свежесть — на момент запроса, как в SQL (_live_vps), а не застывшая в индексе
        "vps": lambda r: (-round(_live_vps(r, now), 6), r.candidate_id),
        "percentile": lambda r: (-(r.percentile or 0.0), r.candidate_id),
        "fresh": lambda r: (
            r.last_activity_at is None,
            -(r.last_activity_at or now).timestamp(),
            r.candidate_id,
        ),
    }
    selected.sort(key=keys[filters.sort])
    return [row.candidate_id for row in selected]


def _live_vps(row: CandidateSearchIndex, now: datetime) -> float:
    w = get_rules().vps_weights
    fresh = matching_service.freshness(row.last_activity_at, now)
    base = w["percentile"] * (row.percentile or 0.0) + w["fsp"] * row.fsp_score + w["fresh"] * fresh
    return base / (1 - w["approach"]) if row.approach is None else base + w["approach"] * row.approach


async def test_sql_search_matches_python_reference(client, session):
    rng = random.Random(7)
    await signup(client, "hr@bank.ru")
    now = datetime.now(UTC)
    ids = []
    for index in range(14):
        _, cid = await make_candidate(client, session, f"c{index}@example.com")
        ids.append(cid)
        skills = {s: rng.choice(["verified", "declared"]) for s in rng.sample(SKILLS, rng.randint(0, 4))}
        await session.execute(
            update(CandidateSearchIndex)
            .where(CandidateSearchIndex.candidate_id == cid)
            .values(
                specialization=rng.choice(["backend", "frontend"]),
                grade=rng.choice([Grade.junior, Grade.middle]),
                vps=round(rng.random(), 3),
                percentile=rng.choice([None, round(rng.random(), 3)]),
                skills_status=skills,
                has_fsp=rng.random() < 0.5,
                max_rank=rng.choice([None, "III", "I", "КМС"]),
                salary_min=rng.choice([None, 150000, 250000, 350000]),
                work_formats=rng.choice(FORMATS),
                city=rng.choice(CITIES),
                relocation=rng.random() < 0.3,
                last_activity_at=rng.choice([None, now - timedelta(days=rng.randint(0, 60))]),
            )
        )
        if rng.random() < 0.4:
            session.add(
                FspAchievement(
                    candidate_id=cid,
                    competition_id=f"c{index}",
                    competition_name="Кубок",
                    discipline=rng.choice(["алгоритмы", "продуктовое"]),
                    level="all_russian",
                    format="team",
                    held_on=now.date(),
                    place=1,
                    participants=10,
                    percentile=0.9,
                    strength=0.5,
                )
            )
    await session.commit()
    user_id = await session.scalar(select(User.id).where(User.email == "hr@bank.ru"))
    rows = list(
        await session.scalars(select(CandidateSearchIndex).where(CandidateSearchIndex.visible.is_(True)))
    )
    disciplines = set(
        await session.scalars(
            select(FspAchievement.candidate_id).where(FspAchievement.discipline == "алгоритмы")
        )
    )
    assert len(rows) == 14

    cases = [SearchFilters()]

    def maybe(value, chance: float = 0.25):
        return value if rng.random() < chance else None

    for _ in range(80):
        cases.append(
            SearchFilters(
                specialization=maybe("backend", 0.4),
                grade=maybe("middle", 0.3),
                skills=rng.sample(SKILLS, 1) if rng.random() < 0.3 else [],
                verified_only=rng.random() < 0.2,
                has_fsp=maybe(rng.choice([True, False])),
                fsp_discipline=maybe("алгоритмы", 0.15),
                fsp_min_rank=maybe("I", 0.15),
                salary_max=maybe(rng.choice([200000, 300000])),
                work_format=maybe(rng.choice(["remote", "office"])),
                city=maybe("Москва"),
                fresh_days=maybe(rng.choice([0, 30])),
                sort=rng.choice(["vps", "percentile", "fresh"]),
            )
        )
    sizes = []
    for filters in cases:
        expected = reference(rows, filters, disciplines, datetime.now(UTC))
        sizes.append(len(expected))
        filters.limit = 100
        found = await matching_service.search(session, user_id, filters)
        assert found.total == len(expected), filters
        assert [item.id for item in found.items] == expected, filters
        filters.offset, filters.limit = 2, 3
        page = await matching_service.search(session, user_id, filters)
        assert [item.id for item in page.items] == expected[2:5], filters
    assert sum(size > 1 for size in sizes) >= 30, "случаи должны давать непустые выборки"


async def test_recommendations_cache_follows_index_and_need_changes(client, session):
    employer = await signup(client, "hr@bank.ru")
    anna, _ = await make_candidate(client, session, "anna@example.com")
    await make_candidate(client, session, "boris@example.com", first_name="Борис")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    url = f"{API}/needs/{need['id']}/recommendations"

    first = (await client.get(url, headers=employer)).json()
    assert first["total"] == 2
    await client.put(f"{API}/candidates/me/search-status", json={"search_status": "hidden"}, headers=anna)
    assert (await client.get(url, headers=employer)).json()["total"] == 1, "скрытый профиль уходит сразу"

    edited = await client.put(f"{API}/needs/{need['id']}", json=NEED | {"grade": "junior"}, headers=employer)
    fresh = (await client.get(f"{API}/needs/{edited.json()['id']}/recommendations", headers=employer)).json()
    assert fresh["need_version"] == 2
    assert fresh["candidates"][0]["score"] < first["candidates"][0]["score"], "новая версия — новый расчёт"


async def test_json_resume_hides_contacts_until_unlock(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    url = f"{API}/talent/candidates/{cid}/resume.json"

    blind = (await client.get(url, headers=employer)).json()
    assert blind["$schema"].endswith("schema.json")
    assert blind["basics"]["name"] == "Анна К." and blind["basics"]["email"] is None
    assert blind["basics"]["profiles"] == [] and "@anna" not in str(blind)
    assert blind["basics"]["label"] == "Backend · Middle"
    assert blind["x-itscout"]["contacts_unlocked"] is False

    other = await signup(client, "hr@other.ru")
    assert (await client.get(f"{API}/talent/candidates/999999/resume.json", headers=other)).status_code == 404
    assert (await client.get(url, headers=candidate)).status_code == 403

    invitation = (await client.post(f"{API}/invitations", json=invite(cid), headers=employer)).json()
    await client.post(f"{API}/invitations/{invitation['id']}/accept", headers=candidate)
    full = (await client.get(url, headers=employer)).json()
    assert full["basics"]["name"] == "Ковалёва Анна"
    assert full["basics"]["profiles"] == [{"network": "Telegram", "username": "anna"}]
    assert full["x-itscout"]["contacts_unlocked"] is True
