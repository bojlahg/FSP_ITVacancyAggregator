"""Аудит предвзятости (§12.2 «Справедливость»): golden-кейсы impact ratio, ДИ и Мантеля–Хензеля."""

import math

import pytest
from validation.fairness import adverse_impact, impact_ratio, mantel_haenszel, markdown, ratio_ci, run
from validation.run import load_config


def test_impact_ratio() -> None:
    assert impact_ratio(0.4, 0.5) == pytest.approx(0.8)
    assert impact_ratio(0.3, 0.6) == pytest.approx(0.5)
    assert math.isnan(impact_ratio(0.3, 0.0))


def test_ratio_ci_katz_golden() -> None:
    # 40/100 против 60/100: RR = 0,6667; Var ln RR = 1/40 − 1/100 + 1/60 − 1/100 = 0,021667
    ratio, low, high = ratio_ci(40, 100, 60, 100)
    assert ratio == pytest.approx(2 / 3)
    assert low == pytest.approx(0.49959, abs=1e-4)
    assert high == pytest.approx(0.88962, abs=1e-4)


def test_ratio_ci_zero_cell_uses_correction() -> None:
    ratio, low, high = ratio_ci(0, 50, 10, 50)
    assert 0 < low < ratio < high
    assert ratio == pytest.approx((0.5 / 50.5) / (10.5 / 50.5))


def test_mantel_haenszel_removes_ability_confounding() -> None:
    """Парадокс Симпсона: в каждом слое доли равны (0,2 и 0,8), но фокальная группа в основном в слабом слое.
    Общий impact ratio 0,32/0,68 = 0,47, при равной способности — ровно 1."""
    strata = [(16, 80, 4, 20), (16, 20, 64, 80)]
    crude = impact_ratio(32 / 100, 68 / 100)
    assert crude == pytest.approx(0.470588, abs=1e-6)
    ratio, low, high = mantel_haenszel(strata)
    assert ratio == pytest.approx(1.0)
    # Var ln RR_MH (Greenland–Robins) = (2,56 + 2,56) / (16 · 16) = 0,02
    assert low == pytest.approx(math.exp(-1.96 * math.sqrt(0.02)), abs=1e-6)
    assert high == pytest.approx(math.exp(1.96 * math.sqrt(0.02)), abs=1e-6)


def test_mantel_haenszel_edge_cases() -> None:
    # Слой с одной группой не влияет на оценку
    assert mantel_haenszel([(5, 10, 5, 10), (3, 3, 0, 0)])[0] == pytest.approx(1.0)
    assert mantel_haenszel([(0, 10, 5, 10)])[0] == 0.0
    assert math.isnan(mantel_haenszel([(5, 10, 0, 10)])[0])


def test_adverse_impact_flags() -> None:
    counts = {
        "ref": {("middle", 0): (25, 100), ("middle", 1): (80, 100)},
        # Ниже 4/5 только из-за состава: в слоях та же доля, но 80% в слабом слое
        "weaker": {("middle", 0): (20, 80), ("middle", 1): (16, 20)},
        # Ниже 4/5 и при равной способности
        "biased": {("middle", 0): (10, 50), ("middle", 1): (10, 50)},
        "tiny": {("middle", 0): (0, 5)},
    }
    rows = {row["group"]: row for row in adverse_impact(counts, threshold=0.8, min_group=30)}
    assert rows["ref"]["flag"] == "reference"
    assert rows["weaker"]["ratio"] == pytest.approx((36 / 100) / (105 / 200))
    assert rows["weaker"]["flag"] == "below"
    assert rows["weaker"]["conditional"] == pytest.approx(1.0)
    assert rows["biased"]["flag"] == "below_conditional"
    assert rows["tiny"]["flag"] == "small"


def test_adverse_impact_conditional_only() -> None:
    """Общая доля в норме, но при равной способности ниже: группа сильнее, а отбирается как слабая."""
    counts = {
        "ref": {("junior", 0): (20, 80), ("junior", 1): (16, 20)},
        "strong": {("junior", 0): (1, 20), ("junior", 1): (32, 80)},
    }
    rows = {row["group"]: row for row in adverse_impact(counts, threshold=0.8, min_group=30)}
    assert rows["strong"]["ratio"] >= 0.8
    assert rows["strong"]["conditional"] < 0.8
    assert rows["strong"]["flag"] == "conditional_only"


@pytest.fixture(scope="module")
def audit() -> dict:
    config = load_config(seed=3)
    config["matching"]["needs"] = 10
    config["fairness"]["bootstrap"] = 50
    return run(config, size=80, log=lambda _: None)


def test_fsp_never_penalizes(audit: dict) -> None:
    """Инвариант §8.3: без ФСП score равен нейтральной базе, ФСП добавляет не больше заявленного веса."""
    inv = audit["fsp_invariant"]
    assert inv["holds"]
    assert inv["no_fsp_changed"] == 0
    assert inv["negative"] == 0
    assert inv["over_declared"] == 0
    assert inv["no_fsp_pairs"] > 0
    assert 0 <= inv["max_delta"] <= inv["declared_max"] + 1


def test_audit_structure_and_report(audit: dict) -> None:
    assert set(audit["selections"]) == {"test_pass", "top_k", "top_k_remote"}
    assert set(audit["selections"]["test_pass"]) == {"city", "fsp", "work_format"}
    for rows in audit["selections"]["test_pass"].values():
        assert sum(row["flag"] == "reference" for row in rows) == 1
        assert sum(row["n"] for row in rows) == 80
    text = "\n".join(markdown(audit))
    assert "Инвариант «ФСП не штрафует»** **выполняется" in text
