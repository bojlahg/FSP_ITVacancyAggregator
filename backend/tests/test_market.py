"""Рынок категории для кандидата (§8.5): агрегаты, порог приватности, контрфактический эффект навыка."""

from datetime import UTC, datetime

from app.core.enums import SkillSource
from app.modules.candidates.models import CandidateSkill
from app.modules.matching import market
from app.modules.matching import service as matching_service
from app.modules.matching.scoring import CandidateFacts, NeedSpec, get_rules
from tests.test_applications import publish
from tests.test_invitations import make_candidate
from tests.test_needs import API, NEED, signup

NAMES = {"python": "Python", "kafka": "Kafka", "postgresql": "PostgreSQL", "docker": "Docker"}
NAMES |= {"rabbitmq": "RabbitMQ", "redis": "Redis"}
CONFIRMABLE = {"python", "kafka", "postgresql", "redis"}


def facts(**overrides) -> CandidateFacts:
    base = dict(
        candidate_id=1,
        specialization="backend",
        grade="middle",
        theta=0.7,
        percentile=0.6,
        topic_scores={},
        skills_status={"python": "verified", "postgresql": "declared"},
        salary_min=260_000,
    )
    return CandidateFacts(**(base | overrides))


def need(employer: int, required=(), optional=(), grade="middle", salary=(200_000, 300_000), published=True):
    spec = NeedSpec(
        specialization="backend",
        grade=grade,
        required=tuple(required),
        optional=tuple(optional),
        salary_from=salary[0],
        salary_to=salary[1],
    )
    return market.MarketNeed(employer_id=employer, published=published, spec=spec)


# Порог skills_match = 0.75; skills-компонент — тот же, что в score подбора (§8.3)
POOL = [
    need(1, ["python", "kafka"], salary=(200_000, 250_000)),  # 0.50 → с Kafka 1.00
    need(1, ["python", "kafka", "postgresql"], salary=(220_000, 280_000), published=False),  # 0.50 → 0.83
    need(1, ["python"], ["kafka"], salary=(240_000, 300_000)),  # 0.77 — подходит уже сейчас
    need(1, ["kafka", "docker"], salary=(260_000, 320_000), published=False),  # 0.00 → 0.50
    need(2, ["python", "postgresql"], salary=(280_000, 340_000)),  # 0.75 — подходит
    need(3, ["python", "rabbitmq"], salary=(300_000, 360_000)),  # 0.50 → с заявленным RabbitMQ 0.75
    need(3, ["python", "postgresql", "redis"], grade="senior", salary=(400_000, 500_000)),  # соседний грейд
]


def test_market_golden_case():
    result = market.insights(facts(), POOL, NAMES, CONFIRMABLE)

    groups = {group.fit: (group.needs, group.vacancies) for group in result.groups}
    assert groups == {
        "exact": (6, 4),
        "adjacent_grade": (1, 1),
        "adjacent_specialization": (0, 0),
        "adjacent_both": (0, 0),
    }
    assert (result.scope, result.scope_needs, result.suppressed) == ("category", 6, False)
    assert result.salary.model_dump() == {
        "median_from": 250_000,
        "median_to": 310_000,
        "candidate_min": 260_000,
        "position": "within",
        "covered_share": 0.833,
    }
    skills = [(s.skill_id, s.required_share, s.optional_share, s.status) for s in result.skills]
    assert skills == [
        ("python", 0.833, 0.0, "verified"),
        ("kafka", 0.5, 0.167, "missing"),
        ("postgresql", 0.333, 0.0, "declared"),
        ("docker", 0.167, 0.0, "missing"),
        ("rabbitmq", 0.167, 0.0, "missing"),
    ]
    assert result.matching_needs == 2
    # Kafka проверяется тестом: +2 потребности; RabbitMQ — только заявить: +1; PostgreSQL и Docker — 0
    assert [(s.skill_id, s.action, s.extra_matches) for s in result.suggestions] == [
        ("kafka", "confirm", 2),
        ("rabbitmq", "declare", 1),
    ]
    assert result.suggestions[0].text == (
        "Подтвердите Kafka тестом или заданием — подходящих потребностей станет больше на 2"
    )


def test_counterfactual_matches_scoring_component():
    assert market.matching_count(facts(), POOL) == 2
    assert market.counterfactual(facts(), POOL, "kafka", "verified") == 2
    assert market.counterfactual(facts(), POOL, "postgresql", "verified") == 0
    assert get_rules().insights["skills_match"] == 0.75


def test_small_samples_are_suppressed():
    few = POOL[4:6]  # 2 потребности от 2 компаний — меньше min_needs
    result = market.insights(facts(), few, NAMES, CONFIRMABLE)
    assert result.suppressed and result.scope is None
    assert result.salary is None and result.skills == [] and result.suggestions == []
    assert result.matching_needs is None
    assert {g.fit: g.needs for g in result.groups}["exact"] == 2  # счётчики видны всегда

    one_employer = POOL[:4]  # 4 потребности, но одна компания — вилки выдали бы её
    assert market.insights(facts(), one_employer, NAMES, CONFIRMABLE).suppressed

    # Своей категории мало, но вместе с соседним грейдом выборка проходит порог
    widened = [*POOL[4:6], POOL[6]]
    result = market.insights(facts(), widened, NAMES, CONFIRMABLE)
    assert (result.scope, result.scope_needs, result.suppressed) == ("neighbourhood", 3, False)


def test_salary_position():
    pool = POOL[:6]
    assert market.salary(pool, 200_000).position == "below"
    assert market.salary(pool, 400_000).position == "above"
    unknown = market.salary(pool, None)
    assert (unknown.position, unknown.covered_share) == ("unknown", None)


async def test_market_endpoint_aggregates_without_employer_identity(client, session):
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    now = datetime.now(UTC)
    session.add(CandidateSkill(candidate_id=cid, skill_id="python", source=SkillSource.test, updated_at=now))
    session.add(
        CandidateSkill(candidate_id=cid, skill_id="postgresql", source=SkillSource.declared, updated_at=now)
    )
    await session.flush()
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    companies = ["Тайный Банк", "Секретный Маркет", "Скрытая Студия"]
    for index, company in enumerate(companies):
        employer = await signup(client, f"hr{index}@corp.ru")
        await client.put(f"{API}/employers/me", json={"company_name": company}, headers=employer)
        title = f"Закрытая потребность {company}"
        response = await client.post(f"{API}/needs", json=NEED | {"title": title}, headers=employer)
        assert response.status_code == 201, response.text
    await publish(client, await signup(client, "hr@open.ru"), title="Открытая вакансия")

    response = await client.get(f"{API}/candidates/me/market", headers=candidate)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["category"]["label"] == "Backend · Middle"
    exact = next(group for group in body["groups"] if group["fit"] == "exact")
    assert (exact["needs"], exact["vacancies"]) == (4, 1)
    assert (body["scope"], body["suppressed"]) == ("category", False)
    assert body["salary"]["median_from"] == NEED["salary_from"]
    assert body["salary"]["position"] == "within"
    assert {skill["skill_id"] for skill in body["skills"]} == {"python", "postgresql", "kafka"}
    statuses = {skill["skill_id"]: skill["status"] for skill in body["skills"]}
    assert statuses == {"python": "verified", "postgresql": "declared", "kafka": "missing"}
    # (1 + 0.5 + 0)/2.3 = 0.65 < 0.75; подтверждённый PostgreSQL или Kafka поднимает все 4 потребности
    assert body["matching_needs"] == 0
    assert {(s["skill_id"], s["action"], s["extra_matches"]) for s in body["suggestions"]} == {
        ("postgresql", "confirm", 4),
        ("kafka", "confirm", 4),
    }
    for secret in [*companies, "Закрытая потребность", "Банк", "employer"]:
        assert secret not in response.text


async def test_market_suppressed_below_min_and_no_category(client, session):
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    employer = await signup(client, "hr@bank.ru")
    await client.post(f"{API}/needs", json=NEED, headers=employer)

    body = (await client.get(f"{API}/candidates/me/market", headers=candidate)).json()
    assert body["suppressed"] is True and body["salary"] is None and body["skills"] == []
    assert next(group for group in body["groups"] if group["fit"] == "exact")["needs"] == 1

    newcomer = await signup(client, "new@example.com", role="candidate")
    empty = (await client.get(f"{API}/candidates/me/market", headers=newcomer)).json()
    assert empty["category"] is None and empty["groups"] == []


async def test_market_is_candidate_only(client, session):
    employer = await signup(client, "hr@bank.ru")
    response = await client.get(f"{API}/candidates/me/market", headers=employer)
    assert response.status_code == 403
    assert (await client.get(f"{API}/candidates/me/market")).status_code == 401
