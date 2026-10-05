"""Golden-кейсы формул ФСП (§9.2)."""

from datetime import date

import pytest

from app.modules.catalog.service import get_catalog
from app.modules.fsp.evidence import RankRecord, ResultRecord, evaluate, fsp_score, percentile, strength

TODAY = date(2026, 10, 6)
CATALOG = get_catalog()


def result(discipline="algorithmic", level="national", place=1, participants=101, years_ago=0.0, role=None):
    held = date.fromordinal(TODAY.toordinal() - round(years_ago * 365.25))
    return ResultRecord(
        "c1",
        "Соревнование",
        discipline,
        level,
        "team" if role else "individual",
        held,
        place,
        participants,
        role,
    )


def test_percentile_bounds():
    assert percentile(1, 101) == 1.0
    assert percentile(101, 101) == 0.0
    assert percentile(51, 101) == pytest.approx(0.5)
    assert percentile(1, 1) == 1.0


def test_strength_combines_percentile_level_and_recency():
    assert strength(result(level="national", place=1), TODAY, CATALOG) == pytest.approx(0.9)
    # Полураспад 3 года: через 3 года сила вдвое меньше
    assert strength(result(level="international", years_ago=3), TODAY, CATALOG) == pytest.approx(
        0.5, abs=0.01
    )
    assert strength(result(level="regional", place=51), TODAY, CATALOG) == pytest.approx(0.3)


def test_noisy_or_accumulates_but_stays_below_one():
    two = evaluate(
        [result(level="regional", place=51), result(level="regional", place=51)], [], TODAY, CATALOG
    )
    algorithms = two.competencies["algorithms"]
    assert algorithms.score == pytest.approx(1 - 0.7 * 0.7)
    assert algorithms.status == "confirmed"


def test_role_link_is_weaker_and_only_supported():
    evidence = evaluate([result("product", place=1, role="backend")], [], TODAY, CATALOG)
    assert evidence.competencies["product_team_dev"].score == pytest.approx(0.9)
    assert evidence.competencies["backend_dev"].score == pytest.approx(0.9 * 0.7)
    assert evidence.competencies["backend_dev"].status == "supported"
    assert evidence.supported_families == {"backend"}


def test_rank_sets_floor_and_confirms():
    evidence = evaluate([], [RankRecord("algorithmic", "КМС", date(2025, 5, 1))], TODAY, CATALOG)
    assert evidence.competencies["algorithms"].score == pytest.approx(0.85)
    assert evidence.competencies["algorithms"].status == "confirmed"
    assert evidence.max_rank == "КМС"


def test_fsp_score_uses_specialization_relevance():
    evidence = evaluate([result("infosec", place=1)], [], TODAY, CATALOG)
    devops = fsp_score(evidence, "devops", CATALOG)
    backend = fsp_score(evidence, "backend", CATALOG)
    assert devops == pytest.approx(0.9 * CATALOG.competency_relevance["devops"]["infosec_ctf"])
    assert backend < devops


def test_no_history_gives_zero_not_penalty():
    evidence = evaluate([], [], TODAY, CATALOG)
    assert fsp_score(evidence, "backend", CATALOG) == 0.0
    assert evidence.max_rank is None
