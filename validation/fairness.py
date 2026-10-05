"""Аудит предвзятости на синтетике (§12.2 «Справедливость»): доли отбора и правило 4/5 по прокси-признакам.

`make fairness-check` или `cd backend && uv run python ../validation/fairness.py` → docs/validation/fairness.md;
тот же раздел входит в отчёт `make validate`.

Пол, возраст и национальность ITScout не собирает, поэтому их нет и в синтетике — проверяются только
признаки, которые есть в данных: город (Москва и Санкт-Петербург против регионов), история ФСП и формат
работы. «Отбор» — (1) прохождение теста на заявленный грейд и (2) попадание в топ-k выдачи по синтетическим
потребностям. Impact ratio — доля отбора группы к доле самой успешной группы (правило 4/5, EEOC Uniform
Guidelines, 29 CFR 1607.4(D); NYC Local Law 144). Чтобы отделить различия, объяснимые способностью,
то же отношение считается при равной истинной способности: Mantel–Haenszel в слоях «грейд × бин θ_true − порог».

Отдельно — инвариант «ФСП не штрафует» (§8.3): score без истории ФСП совпадает с нейтральной базой
(тот же кандидат с обнулённым ФСП), а история ФСП добавляет не больше заявленного веса.
"""

import argparse
import math
import random
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.modules.matching.scoring import CandidateFacts, evaluate, get_rules, vps  # noqa: E402
from app.modules.testing.engine.bank import Blueprints  # noqa: E402
from seed import data  # noqa: E402
from validation import matching_eval  # noqa: E402
from validation.engine_sim import Attempt  # noqa: E402
from validation.engine_sim import Path as TestPath  # noqa: E402
from validation.population import Person  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "validation" / "fairness.md"
CAPITALS = {"Москва", "Санкт-Петербург"}
Stratum = tuple[str, int]

ATTRIBUTES = {
    "city": "Город",
    "fsp": "История ФСП",
    "work_format": "Формат работы",
}
GROUP_NAMES = {
    "capitals": "Москва и Санкт-Петербург",
    "regions": "регионы",
    "fsp": "есть история ФСП",
    "no_fsp": "нет истории ФСП",
    "remote_only": "только удалённо",
    "no_remote": "офис или гибрид, без удалёнки",
    "mixed": "удалёнка и офис/гибрид",
}
SELECTIONS = {
    "test_pass": "Тест на заявленный грейд пройден",
    "top_k": "Попадание в топ-k выдачи",
    "top_k_remote": "Попадание в топ-k, только удалённые потребности",
}


def group_of(person: Person, attribute: str) -> str:
    if attribute == "city":
        return "capitals" if person.city in CAPITALS else "regions"
    if attribute == "fsp":
        return "fsp" if person.has_fsp else "no_fsp"
    formats = set(person.work_formats)
    if formats == {"remote"}:
        return "remote_only"
    return "mixed" if "remote" in formats else "no_remote"


# ---------- статистика: чистые функции, golden-тесты в backend/tests/test_fairness.py ----------


def impact_ratio(rate: float, reference_rate: float) -> float:
    """Отношение долей отбора группы и референтной группы (правило 4/5: < 0,8 — неблагоприятное влияние)."""
    return rate / reference_rate if reference_rate > 0 else float("nan")


def ratio_ci(a: int, n1: int, c: int, n0: int, z: float = 1.96) -> tuple[float, float, float]:
    """Отношение долей a/n1 к c/n0 и ДИ Каца на лог-шкале; при нулевой клетке — поправка 0,5."""
    if n1 == 0 or n0 == 0:
        return float("nan"), float("nan"), float("nan")
    if a == 0 or c == 0:
        a, c, n1, n0 = a + 0.5, c + 0.5, n1 + 0.5, n0 + 0.5
    ratio = (a / n1) / (c / n0)
    # Var ln RR = 1/a − 1/n1 + 1/c − 1/n0 (Katz и др., 1978)
    se = math.sqrt(max(1 / a - 1 / n1 + 1 / c - 1 / n0, 0.0))
    log = math.log(ratio)
    return ratio, math.exp(log - z * se), math.exp(log + z * se)


def mantel_haenszel(strata: list[tuple[int, int, int, int]], z: float = 1.96) -> tuple[float, float, float]:
    """Отношение долей при равной способности: RR Мантеля–Хензеля по слоям (a, n1, c, n0).

    RR_MH = Σ a·n0/N / Σ c·n1/N; дисперсия ln RR_MH — Greenland & Robins (1985). Слой, где есть только
    одна группа, в оценку не входит.
    """
    num = den = var_num = 0.0
    for a, n1, c, n0 in strata:
        total = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += a * n0 / total
        den += c * n1 / total
        var_num += (n1 * n0 * (a + c) - a * c * total) / total**2
    if den == 0:
        return float("nan"), float("nan"), float("nan")
    if num == 0:
        return 0.0, 0.0, float("nan")
    ratio = num / den
    se = math.sqrt(max(var_num / (num * den), 0.0))
    return ratio, math.exp(math.log(ratio) - z * se), math.exp(math.log(ratio) + z * se)


def adverse_impact(
    counts: dict[str, dict[Stratum, tuple[int, int]]], threshold: float, min_group: int, z: float = 1.96
) -> list[dict]:
    """counts: группа → слой способности → (отобрано, всего). Референт — группа с наибольшей долей отбора
    среди групп не меньше min_group. Флаги: below — impact ratio ниже порога, но при равной способности нет;
    below_conditional — ниже порога и при равной способности; conditional_only — ниже только при равной."""
    totals = {g: (sum(s for s, _ in by.values()), sum(n for _, n in by.values())) for g, by in counts.items()}
    eligible = {g: s / n for g, (s, n) in totals.items() if n >= min_group and n > 0}
    if not eligible:
        return []
    reference = max(sorted(eligible), key=lambda g: eligible[g])
    ref_sel, ref_n = totals[reference]
    rows = []
    for group in sorted(counts):
        sel, n = totals[group]
        row = {"group": group, "n": n, "selected": sel, "rate": sel / n if n else float("nan")}
        if group == reference:
            row.update(ratio=1.0, ci=[1.0, 1.0], conditional=1.0, conditional_ci=[1.0, 1.0], flag="reference")
        else:
            ratio, low, high = ratio_ci(sel, n, ref_sel, ref_n, z)
            layers = sorted(set(counts[group]) | set(counts[reference]))
            strata = [(*counts[group].get(k, (0, 0)), *counts[reference].get(k, (0, 0))) for k in layers]
            cond, cond_low, cond_high = mantel_haenszel(strata, z)
            row.update(ratio=ratio, ci=[low, high], conditional=cond, conditional_ci=[cond_low, cond_high])
            row["flag"] = _flag(n, ratio, cond, threshold, min_group)
        rows.append(row)
    return rows


def _flag(n: int, ratio: float, conditional: float, threshold: float, min_group: int) -> str:
    if n < min_group:
        return "small"
    unexplained = math.isnan(conditional) or conditional < threshold
    if ratio < threshold:
        return "below_conditional" if unexplained else "below"
    # Общая доля в норме, но при равной способности группа отбирается реже
    return "conditional_only" if unexplained else "ok"


def ability_stratum(grade: str, distance: float, cfg: dict) -> Stratum:
    """Слой «грейд × бин θ_true − порог»: внутри слоя кандидаты сравниваются при равной способности.

    Грейд в слое нужен потому, что точность теста у разных порогов разная, а группы (например, с ФСП)
    распределены по грейдам неравномерно — без него разница порогов выглядела бы как разница групп.
    """
    low, high = cfg["ability_range"]
    value = min(max(distance, low), high - 1e-9)
    return grade, math.floor(value / cfg["ability_bin"])


# ---------- отбор 1: тест на заявленный грейд ----------


def test_selection(
    people: list[Person],
    first: dict[int, Attempt],
    paths: dict[int, TestPath],
    blueprints: Blueprints,
    cfg: dict,
) -> dict:
    result = {}
    for attribute in ATTRIBUTES:
        counts: dict[str, dict[Stratum, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        accuracy: dict[str, list[bool]] = defaultdict(list)
        for person in people:
            group = group_of(person, attribute)
            stratum = ability_stratum(person.declared, person.theta - blueprints.cut(person.declared), cfg)
            cell = counts[group][stratum]
            cell[0] += first[person.pid].decision != "fail"
            cell[1] += 1
            accuracy[group].append(paths[person.pid].category == person.true_grade)
        rows = adverse_impact(_freeze(counts), cfg["threshold"], cfg["min_group"], cfg["z"])
        for row in rows:
            row["category_accuracy"] = float(np.mean(accuracy[row["group"]]))
        result[attribute] = rows
    return result


def _freeze(counts: dict) -> dict[str, dict[Stratum, tuple[int, int]]]:
    return {g: {k: (v[0], v[1]) for k, v in by.items()} for g, by in counts.items()}


# ---------- отбор 2: топ-k выдачи и инвариант «ФСП не штрафует» ----------


def fairness_needs(config: dict) -> list[matching_eval.Need]:
    """Потребности как в §12.2 «Подбор», но город — из распределения городов, а не только Москва."""
    rng = random.Random(f"fairness-needs:{config['seed']}")
    cities = [city for city, _ in data.CITIES]
    weights = [weight for _, weight in data.CITIES]
    return [
        replace(need, spec=replace(need.spec, city=rng.choices(cities, weights=weights, k=1)[0]))
        for need in matching_eval.build_needs(config)
    ]


def neutral(facts: CandidateFacts) -> CandidateFacts:
    """Нейтральная база: тот же кандидат без истории ФСП."""
    return replace(facts, fsp_score=0.0, has_fsp=False, best_fsp=None)


def _top_k_counts(
    order: list[int], k: int, people: dict[int, Person], grade: str, cut: float, cfg: dict
) -> dict[str, dict[str, dict[Stratum, list[int]]]]:
    top = set(order[:k])
    counts: dict = {a: defaultdict(lambda: defaultdict(lambda: [0, 0])) for a in ATTRIBUTES}
    for pid in order:
        person = people[pid]
        stratum = ability_stratum(grade, person.theta - cut, cfg)
        for attribute in ATTRIBUTES:
            cell = counts[attribute][group_of(person, attribute)][stratum]
            cell[0] += pid in top
            cell[1] += 1
    return counts


def _sum_counts(per_need: list[dict], weights: list[int] | None = None) -> dict:
    total: dict = {a: defaultdict(lambda: defaultdict(lambda: [0, 0])) for a in ATTRIBUTES}
    for index, counts in enumerate(per_need):
        times = 1 if weights is None else weights[index]
        if not times:
            continue
        for attribute, groups in counts.items():
            for group, strata in groups.items():
                for stratum, (sel, n) in strata.items():
                    cell = total[attribute][group][stratum]
                    cell[0] += times * sel
                    cell[1] += times * n
    return {a: _freeze(groups) for a, groups in total.items()}


def _bootstrap(per_need: list[dict], rows: dict[str, list[dict]], cfg: dict, seed: str) -> None:
    """ДИ для топ-k — bootstrap по потребностям: пары «потребность — кандидат» внутри потребности зависимы."""
    if not per_need:
        return
    rng = np.random.default_rng(hash_seed(seed))
    samples: dict[tuple[str, str], tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
    for _ in range(cfg["bootstrap"]):
        weights = rng.multinomial(len(per_need), [1 / len(per_need)] * len(per_need)).tolist()
        total = _sum_counts(per_need, weights)
        for attribute, attribute_rows in rows.items():
            reference = next((r["group"] for r in attribute_rows if r["flag"] == "reference"), None)
            if reference is None or reference not in total[attribute]:
                continue
            ref = total[attribute][reference]
            ref_sel, ref_n = sum(s for s, _ in ref.values()), sum(n for _, n in ref.values())
            for row in attribute_rows:
                if row["flag"] == "reference" or row["group"] not in total[attribute]:
                    continue
                own = total[attribute][row["group"]]
                sel, size = sum(s for s, _ in own.values()), sum(m for _, m in own.values())
                if size and ref_n and ref_sel:
                    samples[(attribute, row["group"])][0].append(impact_ratio(sel / size, ref_sel / ref_n))
                layers = sorted(set(own) | set(ref))
                strata = [(*own.get(k, (0, 0)), *ref.get(k, (0, 0))) for k in layers]
                cond = mantel_haenszel(strata, cfg["z"])[0]
                if not math.isnan(cond):
                    samples[(attribute, row["group"])][1].append(cond)
    for attribute, attribute_rows in rows.items():
        for row in attribute_rows:
            plain, cond = samples.get((attribute, row["group"]), ([], []))
            if plain:
                row["ci"] = [float(np.percentile(plain, 2.5)), float(np.percentile(plain, 97.5))]
            if cond:
                row["conditional_ci"] = [float(np.percentile(cond, 2.5)), float(np.percentile(cond, 97.5))]


def pair_conditional(
    counts: dict[str, dict[Stratum, tuple[int, int]]], focal: str, reference: str, z: float
) -> float:
    own, ref = counts.get(focal, {}), counts.get(reference, {})
    layers = sorted(set(own) | set(ref))
    return mantel_haenszel([(*own.get(k, (0, 0)), *ref.get(k, (0, 0))) for k in layers], z)[0]


def hash_seed(text: str) -> int:
    return random.Random(text).getrandbits(31)


def ranking_audit(
    people: list[Person], paths: dict[int, TestPath], blueprints: Blueprints, config: dict
) -> dict:
    cfg = config["fairness"]
    k = cfg["top_k"]
    facts = matching_eval.build_facts(people, paths, config)
    neutral_facts = {pid: neutral(item) for pid, item in facts.items()}
    by_pid = {p.pid: p for p in people}
    rules = get_rules()
    declared = 100 * rules.weights["fsp"]
    per_need, per_need_remote, per_need_neutral = [], [], []
    deltas_fsp: list[int] = []
    no_fsp_changed = negative = over_declared = pairs = no_fsp_pairs = 0
    lost_slots = no_fsp_neutral_slots = 0
    for need in fairness_needs(config):
        spec = need.spec
        order = matching_eval.rank("match_grouped", spec, people, facts, {})
        order_neutral = matching_eval.rank("match_grouped", spec, people, neutral_facts, {})
        cut = blueprints.cut(spec.grade)
        counts = _top_k_counts(order, k, by_pid, spec.grade, cut, cfg)
        per_need.append(counts)
        per_need_neutral.append(_top_k_counts(order_neutral, k, by_pid, spec.grade, cut, cfg))
        if spec.work_format == "remote":
            per_need_remote.append(counts)
        # Инвариант: score = нейтральная база + вклад ФСП; без ФСП вклад ровно 0
        for pid in order:
            real = evaluate(facts[pid], spec, {})
            base = evaluate(neutral_facts[pid], spec, {})
            delta = real.score - base.score
            pairs += 1
            if delta < 0:
                negative += 1
            if facts[pid].has_fsp:
                deltas_fsp.append(delta)
                # +1 — округление score до целого
                over_declared += delta > declared + 1
            else:
                no_fsp_pairs += 1
                no_fsp_changed += delta != 0
        top_real = set(order[:k])
        for pid in order_neutral[:k]:
            if not by_pid[pid].has_fsp:
                no_fsp_neutral_slots += 1
                lost_slots += pid not in top_real
    vps_violations = sum(
        vps(item.percentile, item.fsp_score, item.fresh, None)
        < vps(item.percentile, 0.0, item.fresh, None) - 1e-9
        or (not item.has_fsp and item.fsp_score != 0.0)
        for item in facts.values()
    )
    rows = {}
    for name, source in (("top_k", per_need), ("top_k_remote", per_need_remote)):
        total = _sum_counts(source)
        rows[name] = {
            a: adverse_impact(total[a], cfg["threshold"], cfg["min_group"], cfg["z"]) for a in ATTRIBUTES
        }
        _bootstrap(source, rows[name], cfg, f"fairness:{config['seed']}:{name}")
    real_fsp, neutral_fsp = _sum_counts(per_need)["fsp"], _sum_counts(per_need_neutral)["fsp"]
    invariant = {
        "pairs": pairs,
        "no_fsp_pairs": no_fsp_pairs,
        "no_fsp_changed": no_fsp_changed,
        "negative": negative,
        "over_declared": over_declared,
        "declared_max": declared,
        "max_delta": max(deltas_fsp, default=0),
        "mean_delta_fsp": float(np.mean(deltas_fsp)) if deltas_fsp else 0.0,
        "vps_violations": int(vps_violations),
        "no_fsp_neutral_slots": no_fsp_neutral_slots,
        "displaced_share": lost_slots / no_fsp_neutral_slots if no_fsp_neutral_slots else 0.0,
        # «нет ФСП» против «есть ФСП» при равной способности: с бонусом и с ФСП, обнулённым у всех
        "no_fsp_conditional": pair_conditional(real_fsp, "no_fsp", "fsp", cfg["z"]),
        "no_fsp_conditional_neutral": pair_conditional(neutral_fsp, "no_fsp", "fsp", cfg["z"]),
    }
    invariant["holds"] = not (no_fsp_changed or negative or over_declared or vps_violations)
    return {
        "top_k": rows["top_k"],
        "top_k_remote": rows["top_k_remote"],
        "needs": len(per_need),
        "remote_needs": len(per_need_remote),
        "fsp_invariant": invariant,
    }


def audit(
    people: list[Person],
    paths: dict[int, TestPath],
    first: dict[int, Attempt],
    blueprints: Blueprints,
    config: dict,
) -> dict:
    cfg = config["fairness"]
    ranking = ranking_audit(people, paths, blueprints, config)
    selections = {
        "test_pass": test_selection(people, first, paths, blueprints, cfg),
        "top_k": ranking["top_k"],
        # Для удалённых потребностей город не важен — таблица проверяет именно это
        "top_k_remote": {"city": ranking["top_k_remote"]["city"]},
    }
    flagged = [
        {"selection": s, "attribute": a, "group": row["group"], "ratio": row["ratio"], "flag": row["flag"]}
        for s, by_attr in selections.items()
        for a, rows in by_attr.items()
        for row in rows
        if row["flag"] in {"below", "below_conditional", "conditional_only"}
    ]
    return {
        "threshold": cfg["threshold"],
        "top_k": cfg["top_k"],
        "min_group": cfg["min_group"],
        "ability_bin": cfg["ability_bin"],
        "needs": ranking["needs"],
        "remote_needs": ranking["remote_needs"],
        "groups": {a: dict(sorted(_group_sizes(people, a).items())) for a in ATTRIBUTES},
        "selections": selections,
        "flagged": flagged,
        "fsp_invariant": ranking["fsp_invariant"],
    }


def _group_sizes(people: list[Person], attribute: str) -> dict[str, int]:
    sizes: dict[str, int] = defaultdict(int)
    for person in people:
        sizes[group_of(person, attribute)] += 1
    return sizes


# ---------- текст отчёта ----------


def _pct(value: float) -> str:
    return "—" if value is None or math.isnan(value) else f"{value * 100:.1f}%".replace(".", ",")


def _num(value: float) -> str:
    return "—" if value is None or math.isnan(value) else f"{value:.2f}".replace(".", ",")


FLAG_TEXT = {
    "reference": "референт",
    "ok": "норма",
    "below": "< 4/5, объясняется способностью",
    "below_conditional": "**< 4/5 и при равной способности**",
    "conditional_only": "**≥ 4/5, но < 4/5 при равной способности**",
    "small": "мало данных",
}


def markdown(f: dict, heading: str = "##") -> list[str]:
    inv = f["fsp_invariant"]
    lines = [
        f"{heading} Справедливость: аудит предвзятости",
        "",
        "Пол, возраст и национальность ITScout не собирает, поэтому их нет и в синтетике — чувствительные "
        "признаки не выдумываются. Проверяются прокси-признаки, которые есть в данных: город (Москва и "
        "Санкт-Петербург против регионов), история ФСП и формат работы. **Отбор** — прохождение теста на "
        f"заявленный грейд и попадание в топ-{f['top_k']} выдачи по умолчанию (группы категорий) по "
        f"{f['needs']} синтетическим потребностям; город потребности — из распределения городов кандидатов. "
        "**Impact ratio** — доля отбора группы к доле самой успешной группы; ниже "
        f"{_num(f['threshold'])} — неблагоприятное влияние по правилу 4/5 (EEOC, NYC Local Law 144). "
        "**При равной способности** — то же отношение по Мантелю–Хензелю в слоях «грейд теста или потребности × бин "
        f"θ_true − порог шириной {_num(f['ability_bin'])}: значение около 1 означает, что различие "
        "объясняется истинной способностью, а не признаком. Скобки — 95% ДИ (для теста — Каца и "
        "Greenland–Robins, для выдачи — bootstrap по потребностям). Группы меньше "
        f"{f['min_group']} не помечаются.",
        "",
    ]
    for selection, by_attr in f["selections"].items():
        title = SELECTIONS[selection].replace("топ-k", f"топ-{f['top_k']}")
        if selection == "top_k_remote":
            title += f" ({f['remote_needs']})"
        lines += [f"**{title}**", ""]
        header = ["Признак", "Группа", "N", "Доля отбора", "Impact ratio", "При равной способности", "Итог"]
        if selection == "test_pass":
            header.insert(4, "Точность категории")
        body = []
        for attribute, rows in by_attr.items():
            for row in rows:
                cells = [
                    ATTRIBUTES[attribute],
                    GROUP_NAMES[row["group"]],
                    str(row["n"]),
                    _pct(row["rate"]),
                    f"{_num(row['ratio'])} [{_num(row['ci'][0])}; {_num(row['ci'][1])}]",
                    f"{_num(row['conditional'])} [{_num(row['conditional_ci'][0])}; "
                    f"{_num(row['conditional_ci'][1])}]",
                    FLAG_TEXT[row["flag"]],
                ]
                if selection == "test_pass":
                    cells.insert(4, _pct(row["category_accuracy"]))
                body.append(cells)
        lines += _table(header, body)
    verdict = "**выполняется**" if inv["holds"] else "**нарушен**"
    lines += [
        f"**Инвариант «ФСП не штрафует»** {verdict}: на {inv['pairs']} парах «потребность — кандидат» "
        f"score кандидата без истории ФСП ({inv['no_fsp_pairs']} пар) совпадает с нейтральной базой — тем же "
        f"кандидатом с обнулённым ФСП — в {inv['no_fsp_pairs'] - inv['no_fsp_changed']} из "
        f"{inv['no_fsp_pairs']}; отрицательных сдвигов {inv['negative']}. История ФСП добавляет в среднем "
        f"{_num(inv['mean_delta_fsp'])} балла, максимум {inv['max_delta']} при заявленном весе "
        f"{_num(inv['declared_max'])} из 100 (превышений {inv['over_declared']}); сила профиля в каталоге "
        f"тоже не снижается (нарушений {inv['vps_violations']}).",
        "",
        f"Заявленный бонус ФСП всё же меняет топ-{f['top_k']}: из {inv['no_fsp_neutral_slots']} мест, которые "
        "кандидаты без ФСП заняли бы при обнулённом ФСП у всех, они теряют "
        f"{_pct(inv['displaced_share'])}. "
        + "Отношение долей «нет ФСП» к «есть ФСП» при равной способности — "
        f"{_num(inv['no_fsp_conditional'])} с бонусом и {_num(inv['no_fsp_conditional_neutral'])}, если "
        "обнулить ФСП у всех: разница — вклад заявленного бонуса; общая разница долей сверх неё "
        "объясняется способностью (ФСП в синтетике коррелирует с θ).",
        "",
    ]
    lines += _conclusions(f)
    return lines


def _conclusions(f: dict) -> list[str]:
    explained = [x for x in f["flagged"] if x["flag"] == "below"]
    unexplained = [x for x in f["flagged"] if x["flag"] in {"below_conditional", "conditional_only"}]
    lines = ["Итог:", ""]
    if not f["flagged"]:
        lines.append(f"- Ни одна группа не опускается ниже {_num(f['threshold'])}.")

    def describe(items: list[dict]) -> str:
        return "; ".join(
            f"{SELECTIONS[x['selection']].replace('топ-k', 'топ-' + str(f['top_k'])).lower()} — "
            f"{GROUP_NAMES[x['group']]} ({_num(x['ratio'])})"
            for x in items
        )

    if explained:
        lines.append(
            f"- Ниже 4/5, но при равной способности различия нет: {describe(explained)}. Группа слабее "
            "в среднем по истинной способности, тест и выдача это верно отражают."
        )
    reasons = {
        "city": "кандидат сам указал город и что не готов к переезду, а офисная или гибридная потребность "
        "задаёт город — такие кандидаты уходят вниз выдачи «вне фильтров», а не исключаются; для удалённых "
        "потребностей см. отдельную таблицу",
        "work_format": "потребность задаёт формат, кандидат сам указал допустимые форматы — несовпадение "
        "уводит вниз выдачи «вне фильтров», а не исключает",
        "fsp": "заявленный бонус ФСП (вес в score — до 10 баллов из 100): при равной способности кандидат "
        "с ФСП стоит выше. Score без ФСП при этом не снижается (инвариант выше выполняется); если доля "
        "заметно ниже 4/5 — повод уменьшить вес `fsp` в `content/matching.yaml`",
    }
    for attribute in ATTRIBUTES:
        items = [x for x in unexplained if x["attribute"] == attribute]
        if items:
            lines.append(
                f"- Ниже 4/5 при равной способности: {describe(items)}. Причина: {reasons[attribute]}."
            )
    lines += [
        "- Аудит синтетический: он проверяет, что формулы не вносят смещения сами, но не заменяет аудит "
        "на реальных данных (§12.4, DIF по Мантелю–Хензелю — после накопления ответов).",
        "",
    ]
    return lines


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return lines + ["| " + " | ".join(row) + " |" for row in rows] + [""]


# ---------- быстрый отдельный прогон ----------


def run(config: dict, size: int | None = None, log=print) -> dict:
    from app.modules.testing.engine.bank import get_bank, get_blueprints
    from validation.engine_sim import Environment, Exposure, run_path
    from validation.population import build_population

    if size is not None:
        config = {**config, "population": {**config["population"], "size": size}}
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
    exposure = Exposure()
    paths = {p.pid: run_path(p, env, exposure, "path-a") for p in people}
    log(f"тесты: {len(people)} кандидатов")
    first = {pid: path.attempts[0] for pid, path in paths.items()}
    return {"seed": config["seed"], "size": len(people), **audit(people, paths, first, blueprints, config)}


def main() -> None:
    from validation.run import load_config

    parser = argparse.ArgumentParser(description="Аудит предвзятости на симуляции")
    parser.add_argument("--size", type=int, help="размер популяции (по умолчанию из config.yaml)")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    config = load_config(size=args.size, seed=args.seed)
    results = run(config)
    text = [
        "# Аудит предвзятости на симуляции",
        "",
        f"Генерируется `make fairness-check` (`validation/fairness.py`): seed {results['seed']}, популяция "
        f"{results['size']}, одна траектория калибровки на кандидата. Тот же раздел с полной популяцией "
        "входит в `report.md` (`make validate`); числа могут немного отличаться — там контроль экспозиции "
        "накапливается по двум траекториям. Методика — `docs/implementation.md` §12.2.",
        "",
        *markdown(results, "##"),
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
    print(f"отчёт: {args.out}")


if __name__ == "__main__":
    main()
