"""Прогон процедуры валидации (§12): популяция → тесты движком → метрики §12.2. Детерминирован по seed."""

import random
import time
from collections import Counter, defaultdict
from dataclasses import replace

import numpy as np
from scipy.stats import chi2

from app.modules.testing.engine.bank import GRADE_ORDER, Blueprints, get_bank, get_blueprints
from app.modules.testing.engine.irt import GRID, information
from seed import data
from validation import calibration, categorization, leakage, matching_eval
from validation.engine_sim import (
    Attempt,
    Environment,
    Exposure,
    Path,
    attempt_seed,
    planner_with_rule,
    run_attempt,
    run_path,
)
from validation.population import Person, build_population, true_grade
from validation.stats import bins, cohen_kappa, confusion, mean, pearson, share

CATEGORY_LABELS = ["none", *GRADE_ORDER]


def _label(grade: str | None) -> str:
    return grade or "none"


def _truth3(theta: float, grade: str, blueprints: Blueprints) -> str:
    """Эталон трёхуровневого решения: уверенный проход — истинный уровень не ниже следующего грейда."""
    if theta < blueprints.cut(grade):
        return "fail"
    higher = blueprints.next_grade(grade)
    return "confident_pass" if higher and theta >= blueprints.cut(higher) else "pass"


def _decision3(decision: str, grade: str, blueprints: Blueprints) -> str:
    # Для старшего грейда «уверенно» не предлагает тест выше — сравниваем как «пройден»
    return "pass" if decision == "confident_pass" and blueprints.next_grade(grade) is None else decision


def _nearest_cut_distance(theta: float, blueprints: Blueprints) -> float:
    return min(abs(theta - cut) for cut in blueprints.scale.cuts.values())


# ---------- метрики основного прогона ----------


def category_metrics(people: list[Person], paths: dict[int, Path]) -> dict:
    truth = [_label(p.true_grade) for p in people]
    predicted = [_label(paths[p.pid].category) for p in people]
    diff = [
        CATEGORY_LABELS.index(b) - CATEGORY_LABELS.index(a) for a, b in zip(truth, predicted, strict=True)
    ]
    by_spec = defaultdict(list)
    for person, t, p in zip(people, truth, predicted, strict=True):
        by_spec[person.spec].append(t == p)
    return {
        "labels": CATEGORY_LABELS,
        "matrix": confusion(truth, predicted, CATEGORY_LABELS).tolist(),
        "accuracy": share([d == 0 for d in diff]),
        "within_one": share([abs(d) <= 1 for d in diff]),
        "off_more_than_one": share([abs(d) > 1 for d in diff]),
        "over": share([d > 0 for d in diff]),
        "under": share([d < 0 for d in diff]),
        "by_spec": {spec: share(hits) for spec, hits in sorted(by_spec.items())},
        "n": len(people),
    }


def decision_metrics(people: list[Person], first: dict[int, Attempt], blueprints: Blueprints) -> dict:
    binary, false_pass, false_fail, three, conf_hits, conf_found = [], [], [], [], [], []
    by_grade = defaultdict(list)
    for person in people:
        attempt = first[person.pid]
        cut = blueprints.cut(attempt.grade)
        truth_pass = person.theta >= cut
        passed = attempt.decision != "fail"
        binary.append(truth_pass == passed)
        by_grade[attempt.grade].append(truth_pass == passed)
        (false_fail if truth_pass else false_pass).append(passed != truth_pass)
        higher = blueprints.next_grade(attempt.grade)
        if higher:
            truth3 = _truth3(person.theta, attempt.grade, blueprints)
            three.append(truth3 == attempt.decision)
            if attempt.decision == "confident_pass":
                conf_hits.append(truth3 == "confident_pass")
            if truth3 == "confident_pass":
                conf_found.append(attempt.decision == "confident_pass")
    return {
        "binary_accuracy": share(binary),
        "false_pass_rate": share(false_pass),
        "false_fail_rate": share(false_fail),
        "three_level_accuracy": share(three),
        "confident_precision": share(conf_hits),
        "confident_recall": share(conf_found),
        "by_grade": {g: share(by_grade[g]) for g in GRADE_ORDER if by_grade[g]},
        "n": len(binary),
    }


def repeatability_metrics(
    people: list[Person],
    first_a: dict[int, Attempt],
    first_b: dict[int, Attempt],
    paths_a: dict[int, Path],
    paths_b: dict[int, Path],
    blueprints: Blueprints,
    near_cut: float,
) -> dict:
    binary, binary_far, binary_near, three, three_far, three_near = [], [], [], [], [], []
    dec_a, dec_b = [], []
    for person in people:
        a, b = first_a[person.pid], first_b[person.pid]
        same_binary = (a.decision != "fail") == (b.decision != "fail")
        da, db = _decision3(a.decision, a.grade, blueprints), _decision3(b.decision, b.grade, blueprints)
        far = abs(person.theta - blueprints.cut(a.grade)) > near_cut
        binary.append(same_binary)
        (binary_far if far else binary_near).append(same_binary)
        three.append(da == db)
        upper = blueprints.next_grade(a.grade)
        # Для трёхуровневого решения важны оба порога: cut_G и cut_{G+1}
        far3 = far and (upper is None or abs(person.theta - blueprints.cut(upper)) > near_cut)
        (three_far if far3 else three_near).append(da == db)
        dec_a.append("fail" if a.decision == "fail" else "pass")
        dec_b.append("fail" if b.decision == "fail" else "pass")
    cat_a = [_label(paths_a[p.pid].category) for p in people]
    cat_b = [_label(paths_b[p.pid].category) for p in people]
    far_category = [
        x == y
        for p, x, y in zip(people, cat_a, cat_b, strict=True)
        if _nearest_cut_distance(p.theta, blueprints) > near_cut
    ]
    return {
        "binary_agreement": share(binary),
        "binary_agreement_far": share(binary_far),
        "binary_agreement_near": share(binary_near),
        "binary_kappa": cohen_kappa(dec_a, dec_b, ["fail", "pass"]),
        "three_level_agreement": share(three),
        "three_level_agreement_far": share(three_far),
        "three_level_agreement_near": share(three_near),
        "far_share": share([abs(p.theta - blueprints.cut(first_a[p.pid].grade)) > near_cut for p in people]),
        "category_agreement": share([x == y for x, y in zip(cat_a, cat_b, strict=True)]),
        "category_agreement_far": share(far_category),
        "category_within_one": share(
            [
                abs(CATEGORY_LABELS.index(x) - CATEGORY_LABELS.index(y)) <= 1
                for x, y in zip(cat_a, cat_b, strict=True)
            ]
        ),
        "category_kappa_quadratic": cohen_kappa(cat_a, cat_b, CATEGORY_LABELS, "quadratic"),
        "theta_correlation": pearson(
            [first_a[p.pid].theta for p in people], [first_b[p.pid].theta for p in people]
        ),
    }


def theta_metrics(
    people: list[Person], first: dict[int, Attempt], config: dict, blueprints: Blueprints
) -> dict:
    true = np.array([p.theta for p in people])
    est = np.array([first[p.pid].theta for p in people])
    se = np.array([first[p.pid].se for p in people])
    errors = est - true
    rows = []
    for lo, hi in bins(**config["theta_bins"]):
        mask = (true >= lo) & (true < hi)
        if mask.sum() < 5:
            continue
        rows.append(
            {
                "from": lo,
                "to": hi,
                "n": int(mask.sum()),
                "bias": float(errors[mask].mean()),
                "rmse": float(np.sqrt((errors[mask] ** 2).mean())),
                "mean_se": float(se[mask].mean()),
            }
        )
    cuts = np.array([blueprints.cut(first[p.pid].grade) for p in people])
    near = np.abs(true - cuts) < config["retest"]["near_cut"]
    return {
        "rmse": float(np.sqrt((errors**2).mean())),
        "bias": float(errors.mean()),
        "correlation": pearson(true, est),
        "mean_se": float(se.mean()),
        "rmse_near_cut": float(np.sqrt((errors[near] ** 2).mean())) if near.any() else float("nan"),
        "mean_se_near_cut": float(se[near].mean()) if near.any() else float("nan"),
        "by_level": rows,
    }


def length_metrics(paths_a: dict[int, Path], first: dict[int, Attempt]) -> dict:
    attempts = [a for path in paths_a.values() for a in path.attempts]
    by_grade = defaultdict(list)
    for attempt in first.values():
        by_grade[attempt.grade].append(attempt)
    return {
        "scored_mean": mean([len(a.scored_items) for a in attempts]),
        "scored_min": min(len(a.scored_items) for a in attempts),
        "scored_max": max(len(a.scored_items) for a in attempts),
        "shown_mean": mean([len(a.items) for a in attempts]),
        "extra_share": share([a.extra_items > 0 for a in attempts]),
        "attempts_per_candidate": mean([len(path.attempts) for path in paths_a.values()]),
        "attempts_distribution": dict(
            sorted(Counter(len(path.attempts) for path in paths_a.values()).items())
        ),
        "by_grade": {
            grade: {
                "n": len(items),
                "scored_mean": mean([len(a.scored_items) for a in items]),
                "extra_share": share([a.extra_items > 0 for a in items]),
                "mean_se": mean([a.se for a in items]),
            }
            for grade in GRADE_ORDER
            if (items := by_grade.get(grade))
        },
    }


def exposure_metrics(exposure: Exposure, env: Environment) -> dict:
    cap = env.blueprints.selection.exposure_cap
    result = {}
    for spec in env.blueprints.specializations:
        active = [t.id for t in env.bank.for_spec(spec) if t.status == "active" and t.kind != "open_approach"]
        rates = exposure.rates(spec)
        values = sorted((rates.get(t, 0.0) for t in active), reverse=True)
        result[spec] = {
            "attempts": exposure.attempts[spec],
            "templates": len(active),
            "used_share": share([v > 0 for v in values]),
            "max": max(values, default=0.0),
            "p90": float(np.percentile(values, 90)) if values else 0.0,
            "over_cap_share": share([v > cap for v in values]),
            "sorted": values,
        }
    return {"cap": cap, "by_spec": result}


def discrimination_metrics(attempts: list[Attempt], config: dict, env: Environment, first: dict) -> dict:
    cfg = config["discrimination"]
    per_template: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
    for attempt in attempts:
        for item in attempt.scored_items:
            scores, thetas = per_template[item.template_id]
            scores.append(item.score)
            thetas.append(attempt.theta)
    rows = []
    for template_id, (scores, thetas) in sorted(per_template.items()):
        if len(scores) >= cfg["min_responses"]:
            rows.append({"template_id": template_id, "n": len(scores), "r": pearson(scores, thetas)})
    values = [row["r"] for row in rows if not np.isnan(row["r"])]
    tif = {}
    for grade in GRADE_ORDER:
        group = [a for a in first.values() if a.grade == grade]
        if not group:
            continue
        total = np.zeros_like(GRID)
        for attempt in group:
            for item in attempt.scored_items:
                t = env.bank.templates[item.template_id]
                total += information(GRID, t.irt.a, t.irt.b, t.guessing)
        curve = total / len(group)
        at_cut = float(np.interp(env.blueprints.cut(grade), GRID, curve))
        tif[grade] = {
            "curve": curve.tolist(),
            "at_cut": at_cut,
            "se_at_cut": float(1 / np.sqrt(at_cut + 1.0)),
            "peak": float(GRID[int(np.argmax(curve))]),
            "cut": env.blueprints.cut(grade),
        }
    return {
        "templates": rows,
        "median_r": float(np.median(values)) if values else float("nan"),
        "weak_share": share([v < cfg["weak_r"] for v in values]),
        "weak_r": cfg["weak_r"],
        "weakest": sorted(rows, key=lambda row: row["r"])[:5],
        "tif": tif,
        "grid": GRID.tolist(),
    }


def bank_metrics(env: Environment) -> dict:
    """Покрытие шкалы банком: есть ли оценённые шаблоны у крайних порогов."""
    blueprints = env.blueprints
    low, high = blueprints.cut(GRADE_ORDER[1]), blueprints.cut(GRADE_ORDER[-1])
    result = {}
    for spec in blueprints.specializations:
        bs = [t.irt.b for t in env.bank.for_spec(spec) if t.status == "active" and t.kind != "open_approach"]
        result[spec] = {
            "active": len(bs),
            "b_min": min(bs),
            "b_max": max(bs),
            "below_junior_cut": sum(b < low for b in bs),
            "above_senior_cut": sum(b > high for b in bs),
        }
    return result


def calibration_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {"n_templates": 0}
    b_err = np.array([r["b_hat"] - r["b"] for r in rows])
    a_err = np.array([r["a_hat"] - r["a"] for r in rows])
    n = np.array([r["n"] for r in rows])
    groups = []
    for lo, hi in ((0, 150), (150, 400), (400, 10**9)):
        mask = (n >= lo) & (n < hi)
        if mask.any():
            groups.append(
                {
                    "from": lo,
                    "to": hi,
                    "templates": int(mask.sum()),
                    "rmse_b": float(np.sqrt((b_err[mask] ** 2).mean())),
                    "rmse_a": float(np.sqrt((a_err[mask] ** 2).mean())),
                }
            )
    return {
        "n_templates": len(rows),
        "median_responses": float(np.median(n)),
        "rmse_b": float(np.sqrt((b_err**2).mean())),
        "bias_b": float(b_err.mean()),
        "corr_b": pearson([r["b"] for r in rows], [r["b_hat"] for r in rows]),
        "rmse_a": float(np.sqrt((a_err**2).mean())),
        "bias_a": float(a_err.mean()),
        "corr_a": pearson([r["a"] for r in rows], [r["a_hat"] for r in rows]),
        "by_responses": groups,
        "rows": rows,
    }


# ---------- дополнительные эксперименты ----------


def forms_experiment(env: Environment, exposure: Exposure, config: dict) -> dict:
    """Один θ_true — разные формы (стек-модули и случайные варианты): совпадает ли среднее θ̂."""
    cfg = config["forms"]
    rows = []
    for spec in sorted(data.SPEC_STACKS):
        for theta in cfg["thetas"]:
            grade = true_grade(theta, env.blueprints) or GRADE_ORDER[0]
            for module in sorted(data.SPEC_STACKS[spec]):
                clone = Person(
                    pid=-1, spec=spec, module=module, theta=theta, true_grade=grade, declared=grade
                )
                estimates = [
                    run_attempt(
                        clone, grade, attempt_seed("forms", spec, module, theta, i), env, exposure.rates(spec)
                    ).theta
                    for i in range(cfg["attempts"])
                ]
                rows.append(
                    {
                        "spec": spec,
                        "module": module or "—",
                        "theta": theta,
                        "mean": float(np.mean(estimates)),
                        "sd": float(np.std(estimates)),
                        "n": len(estimates),
                    }
                )
    spread = []
    for spec in sorted(data.SPEC_STACKS):
        for theta in cfg["thetas"]:
            group = [r for r in rows if r["spec"] == spec and r["theta"] == theta]
            means = [r["mean"] for r in group]
            se_mean = max(r["sd"] / np.sqrt(r["n"]) for r in group)
            # χ² однородности средних по модулям: малое p — формы систематически расходятся
            weights = np.array([r["n"] / r["sd"] ** 2 for r in group])
            pooled = float(np.sum(weights * np.array(means)) / weights.sum())
            chi = float(np.sum(weights * (np.array(means) - pooled) ** 2))
            p_value = float(chi2.sf(chi, len(group) - 1)) if len(group) > 1 else float("nan")
            spread.append(
                {
                    "spec": spec,
                    "theta": theta,
                    "modules": len(group),
                    "bias": float(np.mean(means) - theta),
                    "spread": float(max(means) - min(means)),
                    "se_mean": float(se_mean),
                    "p_value": p_value,
                }
            )
    return {"rows": rows, "spread": spread}


def _path_scores(people: list[Person], env: Environment, frozen: Exposure, label: str) -> dict:
    paths = {p.pid: run_path(p, env, None, label, frozen) for p in people}
    first = {pid: path.attempts[0] for pid, path in paths.items()}
    blueprints = env.blueprints
    errors = [(first[p.pid].theta - p.theta) ** 2 for p in people]
    return {
        "paths": paths,
        "first": first,
        "binary_accuracy": share(
            [
                (p.theta >= blueprints.cut(first[p.pid].grade)) == (first[p.pid].decision != "fail")
                for p in people
            ]
        ),
        "category_accuracy": share([_label(p.true_grade) == _label(paths[p.pid].category) for p in people]),
        "rmse": float(np.sqrt(np.mean(errors))),
    }


def sensitivity_experiment(
    people: list[Person], env: Environment, frozen: Exposure, config: dict
) -> list[dict]:
    """Устойчивость к σ_b экземпляров и к ошибке экспертных b шаблонов (движок знает только экспертные)."""
    cfg = config["sensitivity"]
    subset = people[: cfg["subset"]]
    rows = []
    for sd in cfg["instance_sd"]:
        result = _path_scores(subset, replace(env, instance_sd=sd), frozen, "sens")
        rows.append({"scenario": "instance_sd", "value": sd, **_strip(result)})
    for sigma in cfg["bank_b_error"]:
        rng = random.Random(f"b-error:{config['seed']}:{sigma}")
        errors = {template_id: rng.gauss(0.0, sigma) for template_id in sorted(env.bank.templates)}
        result = _path_scores(subset, replace(env, b_error=errors), frozen, "sens")
        rows.append({"scenario": "bank_b_error", "value": sigma, **_strip(result)})
    return rows


def _strip(result: dict) -> dict:
    return {k: v for k, v in result.items() if k not in {"paths", "first"}}


def whatif_experiment(people: list[Person], env: Environment, frozen: Exposure, config: dict) -> list[dict]:
    """Альтернативные правила «пройден уверенно»: точность и повторяемость категории, число тестов."""
    cfg = config["whatif"]
    subset = people[: cfg["subset"]]
    blueprints = env.blueprints
    rows = []
    for rule in cfg["rules"]:
        variant = replace(env, planner_cls=planner_with_rule(rule["low_k"], rule["high_k"]))
        if rule.get("mode"):
            modes = dict(env.blueprints.modes)
            modes[env.mode] = modes[env.mode].model_copy(update=rule["mode"])
            variant = replace(variant, blueprints=env.blueprints.model_copy(update={"modes": modes}))
        a = _path_scores(subset, variant, frozen, "whatif-a")
        b = _path_scores(subset, variant, frozen, "whatif-b")
        decisions = decision_metrics(subset, a["first"], blueprints)
        three = [
            _decision3(a["first"][p.pid].decision, p.declared, blueprints)
            == _decision3(b["first"][p.pid].decision, p.declared, blueprints)
            for p in subset
        ]
        cat_a = [_label(a["paths"][p.pid].category) for p in subset]
        cat_b = [_label(b["paths"][p.pid].category) for p in subset]
        truth = [_label(p.true_grade) for p in subset]
        rows.append(
            {
                "rule": rule["name"],
                "low_k": rule["low_k"],
                "high_k": rule["high_k"],
                "category_accuracy": a["category_accuracy"],
                "under_assigned": share(
                    [
                        CATEGORY_LABELS.index(x) < CATEGORY_LABELS.index(t)
                        for x, t in zip(cat_a, truth, strict=True)
                    ]
                ),
                "category_agreement": share([x == y for x, y in zip(cat_a, cat_b, strict=True)]),
                "three_level_agreement": share(three),
                "confident_share": share([a["first"][p.pid].decision == "confident_pass" for p in subset]),
                "confident_precision": decisions["confident_precision"],
                "confident_recall": decisions["confident_recall"],
                "tests_per_candidate": mean([len(path.attempts) for path in a["paths"].values()]),
                "scored_mean": mean(
                    [len(t.scored_items) for path in a["paths"].values() for t in path.attempts]
                ),
            }
        )
    return rows


# ---------- общий прогон ----------


def run_validation(config: dict, log=print) -> dict:
    started = time.perf_counter()
    blueprints = get_blueprints()
    env = Environment(
        bank=get_bank(),
        blueprints=blueprints,
        instance_sd=config["response"]["instance_sd"],
        mode=config["response"]["mode"],
        upgrade_accept=config["response"]["upgrade_accept"],
    )
    topics = {spec: sorted(bp.topics) for spec, bp in blueprints.specializations.items()}
    people = build_population(config, blueprints, topics)
    log(f"популяция: {len(people)}")

    exposure = Exposure()
    paths_a: dict[int, Path] = {}
    paths_b: dict[int, Path] = {}
    for person in people:
        paths_a[person.pid] = run_path(person, env, exposure, "path-a")
        paths_b[person.pid] = run_path(person, env, exposure, "path-b")
    first_a = {pid: path.attempts[0] for pid, path in paths_a.items()}
    first_b = {pid: path.attempts[0] for pid, path in paths_b.items()}
    all_attempts = [a for paths in (paths_a, paths_b) for path in paths.values() for a in path.attempts]
    log(f"основной прогон: {len(all_attempts)} попыток, {time.perf_counter() - started:.0f} с")

    near_cut = config["retest"]["near_cut"]
    results: dict = {
        "config": {k: v for k, v in config.items()},
        "population": {
            "size": len(people),
            "by_spec": dict(sorted(Counter(p.spec for p in people).items())),
            "by_true_grade": {g: sum(_label(p.true_grade) == g for p in people) for g in CATEGORY_LABELS},
            "declared_over": share(
                [
                    p.true_grade is not None
                    and GRADE_ORDER.index(p.declared) > GRADE_ORDER.index(p.true_grade)
                    for p in people
                ]
            ),
            "fsp_share": share([p.has_fsp for p in people]),
            "attempts": len(all_attempts),
        },
        "cuts": dict(blueprints.scale.cuts),
        "category": category_metrics(people, paths_a),
        "decision": decision_metrics(people, first_a, blueprints),
        "repeatability": repeatability_metrics(
            people, first_a, first_b, paths_a, paths_b, blueprints, near_cut
        ),
        "theta": theta_metrics(people, first_a, config, blueprints),
        "length": length_metrics(paths_a, first_a),
        "exposure": exposure_metrics(exposure, env),
        "discrimination": discrimination_metrics(all_attempts, config, env, first_a),
        "bank": bank_metrics(env),
    }
    pairs_retest = [leakage.overlap(first_a[p.pid], first_b[p.pid]) for p in people]
    pairs_random = [
        leakage.overlap(x, y)
        for x, y in leakage.random_pairs(
            list(first_a.values()), config["leak"]["pair_samples"], config["seed"]
        )
    ]
    diversity = leakage.variant_diversity(
        env, config["leak"]["variant_renders"], config["leak"]["leaked_instances"]
    )
    results["leak"] = {
        "retest_templates": mean([t for t, _ in pairs_retest]),
        "retest_instances": mean([i for _, i in pairs_retest]),
        "random_templates": mean([t for t, _ in pairs_random]),
        "random_instances": mean([i for _, i in pairs_random]),
        "diversity": diversity,
        "diversity_median_hit": float(np.median([r["hit_rate"] for r in diversity])) if diversity else 0.0,
        "diversity_mean_hit": mean([r["hit_rate"] for r in diversity]),
        "diversity_high_hit_share": share([r["hit_rate"] >= 0.5 for r in diversity]),
        "most_leakable": sorted(diversity, key=lambda r: (-r["hit_rate"], r["template_id"]))[:8],
        **leakage.scenario(people, env, exposure, config),
    }
    log(f"утечки: {time.perf_counter() - started:.0f} с")
    results["calibration"] = calibration_metrics(calibration.recover(all_attempts, env.bank, config))
    log(f"калибровка: {time.perf_counter() - started:.0f} с")
    results["forms"] = forms_experiment(env, exposure, config)
    results["sensitivity"] = sensitivity_experiment(people, env, exposure, config)
    results["whatif"] = whatif_experiment(people, env, exposure, config)
    log(f"эксперименты: {time.perf_counter() - started:.0f} с")
    results["survey"] = categorization.evaluate_survey(people, config)
    results["matching"] = matching_eval.evaluate_matching(people, paths_a, config)
    results["raw"] = {
        "theta_true": [p.theta for p in people],
        "theta_hat": [first_a[p.pid].theta for p in people],
        "theta_hat_retest": [first_b[p.pid].theta for p in people],
        "se": [first_a[p.pid].se for p in people],
        "true_grade": [_label(p.true_grade) for p in people],
        "distance": [p.theta - blueprints.cut(first_a[p.pid].grade) for p in people],
        "passed": [first_a[p.pid].decision != "fail" for p in people],
        "passed_retest": [first_b[p.pid].decision != "fail" for p in people],
    }
    log(f"готово: {time.perf_counter() - started:.0f} с")
    return results
