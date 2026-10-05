"""Smoke-тест процедуры валидации (§12): на маленькой популяции метрики считаются и детерминированы."""

import json

import pytest
from validation.report import rounded, write_report
from validation.run import load_config
from validation.simulate import run_validation


def small_config(seed: int = 11) -> dict:
    config = load_config(size=60, seed=seed)
    config["sensitivity"]["subset"] = 15
    config["whatif"]["subset"] = 15
    config["whatif"]["rules"] = config["whatif"]["rules"][:2]
    config["forms"]["attempts"] = 3
    config["leak"].update(cheaters=8, leaked_instances=3, variant_renders=6, pair_samples=50)
    config["calibration"]["min_responses"] = 5
    config["discrimination"]["min_responses"] = 5
    config["matching"]["needs"] = 5
    return config


def snapshot(results: dict) -> str:
    return json.dumps(rounded(results), ensure_ascii=False, sort_keys=True)


@pytest.fixture(scope="module")
def results() -> dict:
    return run_validation(small_config(), log=lambda _: None)


def test_all_metric_groups_present(results: dict) -> None:
    for key in (
        "category",
        "decision",
        "repeatability",
        "theta",
        "length",
        "exposure",
        "discrimination",
        "bank",
        "leak",
        "calibration",
        "forms",
        "sensitivity",
        "whatif",
        "survey",
        "matching",
    ):
        assert key in results, key
    assert results["population"]["size"] == 60
    assert 0.0 <= results["category"]["accuracy"] <= 1.0
    assert sum(map(sum, results["category"]["matrix"])) == 60
    assert results["length"]["scored_min"] >= 18
    assert set(results["leak"]["scenarios"]) == {
        "adaptive_honest",
        "adaptive_leak_template",
        "adaptive_leak_instance",
        "fixed_honest",
        "fixed_leak",
    }
    assert set(results["matching"]["summary"]) >= {"match_grouped", "declared_grade", "keywords"}


def test_deterministic_by_seed(results: dict) -> None:
    again = run_validation(small_config(), log=lambda _: None)
    assert snapshot(again) == snapshot(results)


def test_report_written(results: dict, tmp_path) -> None:
    report = write_report(results, tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "## 12. Ограничения" in text
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "category_confusion.png").exists()


def test_integrity_check_separates_groups() -> None:
    """§10.9: на малой популяции быстрое угадывание помечается чаще честных; отчёт строится."""
    from validation.integrity_check import build_markdown, run

    config = load_config(seed=5)
    results = run(config, size=40)
    groups = results["groups"]
    assert set(groups) == {"honest", "preknowledge", "rapid"}
    assert groups["rapid"]["flagged"] > groups["honest"]["flagged"]
    assert groups["preknowledge"]["theta_bias"] > groups["honest"]["theta_bias"]
    assert run(config, size=40) == results
    assert "Ложные срабатывания" in "\n".join(build_markdown(results, config))
