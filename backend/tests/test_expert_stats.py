"""Golden-кейсы статистики экспертной разметки (§12.4): bootstrap, парное сравнение, согласие."""

import pytest

from app.modules.expert import stats


def test_bootstrap_ci_is_deterministic_and_contains_mean():
    values = [0.2, 0.4, 0.6, 0.8, 1.0, 0.6]
    low, high = stats.bootstrap_ci(values, 2000, seed=7)
    assert low < sum(values) / len(values) < high
    assert stats.bootstrap_ci(values, 2000, seed=7) == (low, high)
    assert stats.bootstrap_ci([1.0, 1.0, 1.0]) == (1.0, 1.0)
    assert stats.bootstrap_ci([0.5]) is None


def test_paired_bootstrap_golden():
    # Везде ITScout лучше на 1: разница 1, интервал вырожден, p = 0
    assert stats.paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0]) == (1.0, 1.0, 1.0, 0.0)
    # Одинаковые выдачи: разница 0, p = 1
    diff, low, high, p_value = stats.paired_bootstrap([0.4, 0.6, 0.8], [0.4, 0.6, 0.8])
    assert (diff, low, high, p_value) == (0.0, 0.0, 0.0, 1.0)
    # Шум вокруг нуля — разница незначима
    noisy = stats.paired_bootstrap([0.8, 0.2, 0.6, 0.4, 0.6], [0.6, 0.4, 0.4, 0.6, 0.6], seed=1)
    assert noisy[1] < 0 < noisy[2] and noisy[3] > 0.5
    assert stats.paired_bootstrap([1], [0]) is None


def test_sign_test_golden():
    # 6 побед из 6: p = 2 · 0,5⁶ = 0,03125
    assert stats.sign_test([1] * 6, [0] * 6) == (6, 0, 0, pytest.approx(0.03125))
    assert stats.sign_test([1, 0, 0.5], [0, 1, 0.5])[:3] == (1, 1, 1)
    assert stats.sign_test([0.5, 0.5], [0.5, 0.5]) == (0, 0, 2, None)


def test_needs_for_power_golden():
    # σ разницы nDCG 0,15, разница 0,1, α 0,05, мощность 0,8: ((1,96 + 0,84) · 1,5)² = 17,7 → 18 (≈ 20 в цели)
    assert stats.needs_for_power(0.15, 0.1) == 18
    assert stats.needs_for_power(0.0, 0.1) is None


def test_ndcg_golden():
    assert stats.ndcg([3, 2, 0], [3, 2, 0], 5) == pytest.approx(1.0)
    # dcg = 3/log2(3) + 7/2 = 5,3928; идеал = 7 + 3/log2(3) = 8,8928
    assert stats.ndcg([0, 2, 3], [3, 2, 0], 3) == pytest.approx(0.6064, abs=1e-4)
    assert stats.ndcg([0, 0], [0, 0], 5) is None


def test_krippendorff_alpha_golden():
    assert stats.krippendorff_alpha([[1, 1], [2, 2], [3, 3, 3]]) == 1.0
    # Наблюдаемое расхождение 36, ожидаемое 72 / 3 = 24: α = 1 − 36/24 = −0,5
    assert stats.krippendorff_alpha([[0, 3], [3, 0]]) == -0.5
    assert stats.krippendorff_alpha([[2], [3]]) is None


def test_bootstrap_kappa_ci_and_landis_koch():
    pairs = [(3, 3), (2, 2), (0, 1), (1, 1), (3, 2), (0, 0), (2, 3), (1, 0)]
    kappa = stats.weighted_kappa(pairs)
    low, high = stats.bootstrap_statistic_ci(pairs, stats.weighted_kappa, 500, seed=3)
    assert low <= kappa <= high <= 1.0
    assert stats.bootstrap_statistic_ci(pairs[:1], stats.weighted_kappa) is None
    assert [stats.landis_koch(k) for k in (-0.1, 0.1, 0.3, 0.5, 0.7, 0.9)] == [
        "хуже случайного",
        "незначительное",
        "слабое",
        "умеренное",
        "существенное",
        "почти полное",
    ]
    assert stats.landis_koch(None) is None
