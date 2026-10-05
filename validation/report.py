"""Отчёт валидации: docs/validation/report.md + metrics.json + PNG. Текст и числа генерирует код."""

import json
import math
from pathlib import Path

GRADE_NAMES = {
    "none": "нет категории",
    "intern": "Intern",
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}
RANKER_NAMES = {
    "match_grouped": "ITScout: выдача по категориям (по умолчанию)",
    "match": "ITScout: «общий топ» по score",
    "test_category": "категория по тесту + ключевые слова",
    "declared_grade": "заявленный грейд + ключевые слова",
    "keywords": "только ключевые слова резюме",
}
WHATIF_NAMES = {
    "current": "текущее: θ̂ − SE ≥ cut_G и θ̂ ≥ cut_{G+1} − SE",
    "high_0.5se": "θ̂ ≥ cut_{G+1} − 0,5·SE",
    "high_0se": "θ̂ ≥ cut_{G+1}",
    "high_1.5se": "θ̂ ≥ cut_{G+1} − 1,5·SE",
    "extra_8": "текущее + до 8 доп. заданий у порога (вместо 4)",
    "stage2_13": "текущее + этап 2 из 13 заданий (вместо 9)",
}


def pct(value: float, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def num(value: float, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:.{digits}f}".replace(".", ",").replace("-", "−")


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return lines + [""]


def rounded(value):
    if isinstance(value, float):
        return round(value, 4) if not math.isnan(value) else None
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [rounded(item) for item in value]
    return value


def write_report(results: dict, out: Path) -> Path:
    from validation import plots

    out.mkdir(parents=True, exist_ok=True)
    plots.draw_all(results, out, RANKER_NAMES)
    metrics = {key: value for key, value in results.items() if key != "raw"}
    (out / "metrics.json").write_text(
        json.dumps(rounded(metrics), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    path = out / "report.md"
    path.write_text("\n".join(build_markdown(results)) + "\n", encoding="utf-8", newline="\n")
    return path


def build_markdown(r: dict) -> list[str]:
    cfg = r["config"]
    pop, cat, dec, rep, theta = r["population"], r["category"], r["decision"], r["repeatability"], r["theta"]
    length, leak, cal, disc, match = (
        r["length"],
        r["leak"],
        r["calibration"],
        r["discrimination"],
        r["matching"],
    )
    scen = leak["scenarios"]
    near = cfg["retest"]["near_cut"]
    cuts = r["cuts"]
    lines = [
        "# Валидация тестирования и подбора ITScout",
        "",
        f"> Отчёт сгенерирован командой `make validate` (`validation/run.py`): seed {cfg['seed']}, "
        f"популяция {pop['size']} кандидатов, {pop['attempts']} попыток теста в основном прогоне. "
        "Файл не правится руками — все числа и графики пересчитываются из кода продукта и "
        "`validation/config.yaml`. Процедура описана в `docs/implementation.md` §12, сырые метрики — "
        "в `metrics.json` рядом.",
        "",
        "## Главное",
        "",
    ]
    lines += table(
        ["Свойство (критерий ТЗ)", "Метрика", "Значение"],
        [
            ["Соответствие эталону", "Категория совпала с истинным грейдом", pct(cat["accuracy"])],
            ["", "Ошибка больше чем на один грейд", pct(cat["off_more_than_one"])],
            ["", "Решение «пройден / не пройден» на заявленный грейд", pct(dec["binary_accuracy"])],
            [
                "Согласованность",
                "Повторная калибровка на других заданиях: та же категория",
                f"{pct(rep['category_agreement'])} (взвешенная κ = {num(rep['category_kappa_quadratic'])})",
            ],
            [
                "",
                "Повтор решения «пройден / не пройден»",
                f"{pct(rep['binary_agreement'])}; вдали от порога (>{num(near, 1)}) — "
                f"{pct(rep['binary_agreement_far'])}",
            ],
            [
                "",
                "Повтор трёхуровневого решения (не / пройден / уверенно)",
                pct(rep["three_level_agreement"]),
            ],
            ["", "Корреляция θ̂ двух попыток", num(rep["theta_correlation"])],
            [
                "Точность оценки",
                "RMSE θ̂ / корреляция с истинным θ",
                f"{num(theta['rmse'])} / {num(theta['correlation'])}",
            ],
            [
                "Длина теста",
                "Оценённых заданий в попытке",
                f"{num(length['scored_mean'], 1)} ({length['scored_min']}–{length['scored_max']})",
            ],
            ["Дискриминативность", "Медианная корреляция ответа на шаблон с θ̂", num(disc["median_r"])],
            [
                "Защита от утечки",
                "Общих шаблонов / общих экземпляров у двух попыток",
                f"{pct(leak['random_templates'])} / {pct(leak['random_instances'])}",
            ],
            [
                "",
                f"Слито {pct(leak['share'], 0)} ключей: доля кандидатов ниже {GRADE_NAMES[leak['grade']]}, "
                "прошедших тест",
                f"фиксированный тест {pct(scen['fixed_honest']['pass_rate'], 0)} → "
                f"{pct(scen['fixed_leak']['pass_rate'], 0)}; ITScout {pct(scen['adaptive_honest']['pass_rate'], 0)}"
                f" → {pct(scen['adaptive_leak_instance']['pass_rate'], 0)}",
            ],
            ["Калибровка", "RMSE восстановления b шаблонов", num(cal.get("rmse_b", float("nan")))],
            [
                "Сопоставимость форм",
                "Макс. расхождение среднего θ̂ между стек-модулями",
                num(max(s["spread"] for s in r["forms"]["spread"])),
            ],
            [
                "Категоризация",
                "Специализация по опросу (топ-1 / топ-2)",
                f"{pct(r['survey']['top1'])} / {pct(r['survey']['top2'])}",
            ],
            [
                "Подбор",
                "P@5: выдача ITScout / категория по тесту / заявленный грейд / ключевые слова резюме",
                " / ".join(
                    num(match["summary"][k]["p@5"])
                    for k in ("match_grouped", "test_category", "declared_grade", "keywords")
                ),
            ],
        ],
    )
    lines += _method(r)
    lines += _accuracy(r)
    lines += _repeatability(r)
    lines += _theta(r)
    lines += _discrimination(r)
    lines += _forms(r)
    lines += _leak(r)
    lines += _calibration(r)
    lines += _survey(r)
    lines += _matching(r)
    lines += _weaknesses(r)
    lines += _limitations(r)
    lines += [
        "## Воспроизведение",
        "",
        "```bash",
        "make validate                                   # Linux, WSL, CI",
        "cd backend && uv run python ../validation/run.py # то же без make",
        "cd backend && uv run python ../validation/run.py --size 500 --seed 7 --out /tmp/v  # другой прогон",
        "```",
        "",
        "Пороги грейдов на шкале специализации: "
        + ", ".join(f"{g} {num(c, 1)}" for g, c in cuts.items())
        + " (`backend/content/blueprints.yaml`).",
    ]
    return lines


def _method(r: dict) -> list[str]:
    cfg, pop = r["config"], r["population"]
    p = cfg["population"]
    by_grade = ", ".join(f"{GRADE_NAMES[g]} — {n}" for g, n in pop["by_true_grade"].items())
    by_spec = ", ".join(f"{s} — {n}" for s, n in pop["by_spec"].items())
    return [
        "## 1. Как устроена проверка",
        "",
        "**Тот же движок, что и в продукте.** Тест собирается и оценивается кодом "
        "`backend/app/modules/testing/engine`: двухэтапный MST (`Planner`), рендер параметризованных "
        "экземпляров, контроль экспозиции, EAP-оценка θ и решение о грейде. Ранжирование — чистые функции "
        "`backend/app/modules/matching/scoring.py`, специализация по опросу — "
        "`survey.service.score_specializations`. БД и HTTP не участвуют, поэтому прогон детерминирован по seed.",
        "",
        f"**Популяция (§12.1).** {pop['size']} кандидатов по 5 специализациям ({by_spec}). Истинная способность "
        f"θ_true — смесь нормальных распределений по грейдам (σ = {num(p['theta_sd'])}); истинный грейд — "
        f"старший грейд, чей порог не выше θ_true ({by_grade}). У каждого — профиль по темам (отклонения "
        f"σ = {num(p['topic_sd'])} от θ), истинный стек, резюме с шумом (в {pct(p['resume_padding'], 0)} резюме "
        f"есть лишние навыки, в {pct(p['resume_omission'], 0)} — пропуски), заявленный грейд "
        f"({pct(p['declared_over'], 0)} завышают на один, {pct(p['declared_under'], 0)} занижают), история ФСП "
        f"у {pct(pop['fsp_share'], 0)}, коррелирующая с θ.",
        "",
        "**Модель ответа.** Вероятность верного ответа — 3PL с параметрами шаблона (c = 1/k для выбора одного "
        "варианта) от способности кандидата по теме задания; сложность конкретного экземпляра отклоняется от b "
        f"шаблона на σ_b = {num(cfg['response']['instance_sd'])} (отклонение — свойство содержимого экземпляра). "
        "Движок о профиле по темам и σ_b не знает — это проверка устойчивости к нарушению его модели.",
        "",
        "**Путь кандидата (§6.3).** Тест на заявленный грейд; при провале — тест на грейд ниже; при «пройден "
        "уверенно» — один тест на грейд выше. Итоговая категория сравнивается с истинным грейдом. Для "
        "согласованности каждый кандидат проходит этот путь второй раз с другим seed — другие шаблоны и "
        "экземпляры, как при реальной повторной попытке.",
        "",
    ]


def _accuracy(r: dict) -> list[str]:
    cat, dec = r["category"], r["decision"]
    labels = cat["labels"]
    rows = []
    for label, row in zip(labels, cat["matrix"], strict=True):
        total = sum(row)
        rows.append(
            [
                GRADE_NAMES[label],
                *[str(v) for v in row],
                pct(row[labels.index(label)] / total) if total else "—",
            ]
        )
    lines = [
        "## 2. Соответствие эталону",
        "",
        f"Итоговая категория совпала с истинным грейдом у **{pct(cat['accuracy'])}** кандидатов, "
        f"в пределах одного грейда — у {pct(cat['within_one'])}, ошибка больше чем на грейд — "
        f"{pct(cat['off_more_than_one'])}. Завышение — {pct(cat['over'])}, занижение — {pct(cat['under'])}. "
        + (
            "Ошибки — только соседние грейды: "
            if cat["off_more_than_one"] == 0
            else "Почти все ошибки — соседние грейды: "
        )
        + "это кандидаты, чья способность лежит у порога, где погрешности измерения в ±SE хватает, чтобы "
        "оказаться по другую сторону. Больше всего ошибок у нижних уровней («нет категории» и Intern): "
        "тест на Intern даёт меньше всего информации у своего порога (раздел 5), а кандидаты ниже порога "
        "стажёра почти всегда заявляют Intern.",
        "",
        "![Матрица ошибок](category_confusion.png)",
        "",
    ]
    lines += table(["Истинный \\ по тесту", *[GRADE_NAMES[x] for x in labels], "Верно"], rows)
    lines += table(
        ["Специализация", "Точность категории"],
        [[spec, pct(value)] for spec, value in cat["by_spec"].items()],
    )
    lines += [
        f"**Решение по одному тесту** на заявленный грейд верно в **{pct(dec['binary_accuracy'])}** случаев: "
        f"ложный проход у {pct(dec['false_pass_rate'])} тех, кто ниже порога, ложный провал у "
        f"{pct(dec['false_fail_rate'])} тех, кто выше. По грейду теста: "
        + ", ".join(f"{GRADE_NAMES[g]} — {pct(v)}" for g, v in dec["by_grade"].items())
        + ".",
        "",
    ]
    return lines


def _repeatability(r: dict) -> list[str]:
    rep = r["repeatability"]
    near = r["config"]["retest"]["near_cut"]
    lines = [
        "## 3. Согласованность (повторное прохождение)",
        "",
        "Каждый кандидат дважды проходит калибровку на независимых вариантах теста.",
        "",
    ]
    lines += table(
        ["Что сравниваем", "Совпадение", "Вдали от порога", "У порога"],
        [
            [
                "Пройден / не пройден (тест на заявленный грейд)",
                pct(rep["binary_agreement"]),
                pct(rep["binary_agreement_far"]),
                pct(rep["binary_agreement_near"]),
            ],
            [
                "Не пройден / пройден / пройден уверенно",
                pct(rep["three_level_agreement"]),
                pct(rep["three_level_agreement_far"]),
                pct(rep["three_level_agreement_near"]),
            ],
            ["Итоговая категория", pct(rep["category_agreement"]), pct(rep["category_agreement_far"]), "—"],
        ],
    )
    lines += [
        f"«Вдали от порога» — |θ_true − cut| > {num(near, 1)} (для трёхуровневого решения — от обоих порогов, "
        f"для категории — от всех). Таких кандидатов {pct(rep['far_share'], 0)}. Категория совпадает в пределах "
        f"одного грейда у {pct(rep['category_within_one'])}; взвешенная (квадратичная) κ Коэна = "
        f"**{num(rep['category_kappa_quadratic'])}**, κ бинарного решения = {num(rep['binary_kappa'])}, "
        f"корреляция θ̂ двух попыток = **{num(rep['theta_correlation'])}**.",
        "",
        "![Операционная кривая и повторяемость](decision_curve.png)",
        "",
        f"Расхождения сосредоточены у порога (правый график): при средней SE {num(r['theta']['mean_se'])} кандидат "
        "на расстоянии меньше одной SE от порога честно «монетка» — так ведёт себя любой тест такой длины. "
        "Трёхуровневое решение "
        "повторяется хуже, потому что у него два порога: cut_G и граница «уверенно» около cut_{G+1} − SE, и "
        "кандидат у любого из них может сменить исход. Это слабое место — разбор и варианты улучшения в "
        "разделе 11.",
        "",
    ]
    return lines


def _theta(r: dict) -> list[str]:
    theta, length = r["theta"], r["length"]
    lines = [
        "## 4. Точность оценки способности и длина теста",
        "",
        f"После теста на заявленный грейд RMSE θ̂ = **{num(theta['rmse'])}**, смещение = {num(theta['bias'])}, "
        f"корреляция с θ_true = {num(theta['correlation'])}. У порога заявленного грейда (±{num(r['config']['retest']['near_cut'], 1)})"
        f" RMSE = {num(theta['rmse_near_cut'])}. Средняя SE, которую сообщает движок, — {num(theta['mean_se'])} "
        f"при фактической RMSE {num(theta['rmse'])}"
        + (
            f": SE оптимистична на {pct(theta['rmse'] / theta['mean_se'] - 1, 0)}, потому что модель движка не "
            "знает про профиль по темам и σ_b."
            if theta["rmse"] > theta["mean_se"]
            else ": движок оценивает свою погрешность честно."
        ),
        "",
        "![θ̂ против θ](theta_recovery.png)",
        "",
        "![Точность по уровню](theta_error.png)",
        "",
    ]
    lines += table(
        ["θ_true", "Кандидатов", "Смещение", "RMSE", "Средняя SE"],
        [
            [
                f"{num(row['from'], 1)}…{num(row['to'], 1)}",
                row["n"],
                num(row["bias"]),
                num(row["rmse"]),
                num(row["mean_se"]),
            ]
            for row in theta["by_level"]
        ],
    )
    lines += [
        "На краях шкалы EAP стягивает оценку к априорному среднему (положительное смещение у слабых, "
        "отрицательное у сильных) — это свойство байесовской оценки; на решения о грейде оно почти не "
        "влияет, потому что края далеко от порогов.",
        "",
        f"**Длина теста.** В среднем {num(length['scored_mean'], 1)} оценённых заданий "
        f"({length['scored_min']}–{length['scored_max']}), с пилотными и открытым вопросом — "
        f"{num(length['shown_mean'], 1)} показа. Доп. задания у порога понадобились в "
        f"{pct(length['extra_share'], 0)} попыток. Калибровка требует в среднем "
        f"{num(length['attempts_per_candidate'], 2)} теста на кандидата (распределение: "
        + ", ".join(f"{k} — {v}" for k, v in length["attempts_distribution"].items())
        + ").",
        "",
    ]
    lines += table(
        ["Тест на грейд", "Попыток", "Оценённых заданий", "С доп. заданиями", "Средняя SE"],
        [
            [GRADE_NAMES[g], v["n"], num(v["scored_mean"], 1), pct(v["extra_share"], 0), num(v["mean_se"])]
            for g, v in length["by_grade"].items()
        ],
    )
    return lines


def _discrimination(r: dict) -> list[str]:
    disc = r["discrimination"]
    lines = [
        "## 5. Дискриминативность",
        "",
        f"Точечно-бисериальная корреляция ответа на шаблон с θ̂ попытки: медиана **{num(disc['median_r'])}**, "
        f"доля шаблонов с r < {num(disc['weak_r'], 1)} — {pct(disc['weak_share'])} (по шаблонам с ≥ "
        f"{r['config']['discrimination']['min_responses']} ответами). В адаптивном тесте корреляции занижены "
        "отбором заданий под уровень кандидата, поэтому важна не величина, а отсутствие шаблонов около нуля. "
        "Наименее дискриминативные: "
        + ", ".join(f"`{w['template_id']}` ({num(w['r'])})" for w in disc["weakest"])
        + ".",
        "",
        "![Дискриминативность](discrimination.png)",
        "",
        "По замыслу MST информационная функция теста должна быть максимальна у порога своего грейда — "
        "там, где принимается решение.",
        "",
        "![Информационная функция](test_information.png)",
        "",
    ]
    lines += table(
        ["Тест на грейд", "Порог", "Максимум информации при θ", "I(cut_G)", "SE у порога = 1/√(I+1)"],
        [
            [GRADE_NAMES[g], num(v["cut"], 1), num(v["peak"], 1), num(v["at_cut"], 1), num(v["se_at_cut"])]
            for g, v in disc["tif"].items()
        ],
    )
    shifted = [g for g, v in disc["tif"].items() if abs(v["peak"] - v["cut"]) > 0.5]
    bank = r["bank"]
    if shifted:
        lines += [
            "У тестов на "
            + ", ".join(GRADE_NAMES[g] for g in shifted)
            + " максимум информации смещён от порога больше чем на 0,5 логита: в банке мало шаблонов с "
            "такой сложностью (у заданий с выбором ответа максимум информации и так сдвинут вправо от b на "
            "0,2–0,3 логита из-за угадывания, но смещение здесь больше). Самые лёгкие и самые трудные "
            "активные шаблоны по специализациям: "
            + ", ".join(f"{s} {num(v['b_min'], 1)}…{num(v['b_max'], 1)}" for s, v in bank.items())
            + ". Поэтому у нижних порогов SE больше, а точность категории ниже (раздел 2). См. рекомендации.",
            "",
        ]
    lines += [
        "Распределения θ̂ сильных и слабых кандидатов разделены порогами; пересечение соседних грейдов — "
        "те самые пограничные случаи из разделов 2–3.",
        "",
        "![θ̂ по истинному грейду](theta_by_true_grade.png)",
        "",
    ]
    return lines


def _forms(r: dict) -> list[str]:
    forms = r["forms"]
    sens = r["sensitivity"]
    cfg = r["config"]
    lines = [
        "## 6. Сопоставимость форм",
        "",
        f"Кандидаты с одинаковым θ_true ({', '.join(num(t, 1) for t in cfg['forms']['thetas'])}) проходят тест "
        f"{cfg['forms']['attempts']} раз на каждом стек-модуле специализации: формы различаются и стеком, и "
        "случайным составом и экземплярами. Если формы сопоставимы, среднее θ̂ не зависит от модуля.",
        "",
    ]
    lines += table(
        [
            "Специализация",
            "θ_true",
            "Модулей",
            "Смещение среднего θ̂",
            "Разброс между модулями",
            "SE среднего",
            "p (χ²)",
        ],
        [
            [
                s["spec"],
                num(s["theta"], 1),
                s["modules"],
                num(s["bias"]),
                num(s["spread"]),
                num(s["se_mean"]),
                num(s["p_value"]) if s["modules"] > 1 else "—",
            ]
            for s in forms["spread"]
        ],
    )
    tests = [s for s in forms["spread"] if s["modules"] > 1]
    significant = [s for s in tests if s["p_value"] < 0.05]
    if not significant:
        verdict = "Ни в одной группе различие модулей не значимо (все p ≥ 0,05)."
    elif len(significant) == 1:
        s = significant[0]
        verdict = (
            f"Значимое (p < 0,05) различие только в одной группе из {len(tests)} ({s['spec']}, θ = "
            f"{num(s['theta'], 1)}, разброс {num(s['spread'])}) — при {len(tests)} проверках хотя бы один такой "
            f"случай без реального различия выпадает с вероятностью {pct(1 - 0.95 ** len(tests), 0)}, а величина "
            f"различия в {num(r['theta']['mean_se'] / max(s['spread'], 1e-9), 0)} раз меньше SE отдельного "
            "кандидата."
        )
    else:
        verdict = (
            f"Значимые различия в {len(significant)} группах из {len(tests)}: "
            + ", ".join(f"{s['spec']} (θ = {num(s['theta'], 1)})" for s in significant)
            + " — модули этих специализаций нужно выровнять калибровкой."
        )
    lines += [
        "p — критерий однородности средних по модулям (χ²): малое p означало бы, что одна форма "
        f"систематически строже другой. {verdict} Смещение одного знака у всех модулей — стягивание EAP к "
        "априорному среднему, одинаковое для всех форм.",
        "",
        "**Устойчивость решения к σ_b и к ошибкам экспертных параметров.** Тот же поднабор кандидатов, "
        "разные условия; движок использует экспертные b, а ответы порождаются «истинными» b с ошибкой.",
        "",
    ]
    names = {"instance_sd": "σ_b экземпляров", "bank_b_error": "ошибка экспертных b, σ"}
    lines += table(
        ["Условие", "Значение", "Решение пройден/не пройден", "Точность категории", "RMSE θ̂"],
        [
            [
                names[row["scenario"]],
                num(row["value"]),
                pct(row["binary_accuracy"]),
                pct(row["category_accuracy"]),
                num(row["rmse"]),
            ]
            for row in sens
        ],
    )
    subset = cfg["sensitivity"]["subset"]
    margin = margin_of_error(subset)
    by_sd = [row for row in sens if row["scenario"] == "instance_sd"]
    by_b = [row for row in sens if row["scenario"] == "bank_b_error"]
    sd_range = max(row["category_accuracy"] for row in by_sd) - min(row["category_accuracy"] for row in by_sd)
    base = next((row for row in by_sd if row["value"] == cfg["response"]["instance_sd"]), by_sd[0])
    worst_b = max(by_b, key=lambda row: row["value"]) if by_b else None
    lines += [
        f"Погрешность долей на {subset} кандидатах — около ±{num(margin * 100, 1)} п.п. (95%). Разброс "
        f"точности категории при σ_b от {num(by_sd[0]['value'])} до {num(by_sd[-1]['value'])} — "
        f"{num(sd_range * 100, 1)} п.п."
        + (
            ", то есть в пределах погрешности: параметризация не ломает сопоставимость, её держит общая "
            "шкала шаблона."
            if sd_range <= margin
            else ", что больше погрешности: разброс сложности экземпляров нужно ограничивать в генераторах."
        )
        + (
            f" Ошибка экспертных b с σ = {num(worst_b['value'])} меняет точность категории на "
            f"{num((worst_b['category_accuracy'] - base['category_accuracy']) * 100, 1)} п.п. и RMSE θ̂ на "
            f"{num(worst_b['rmse'] - base['rmse'])} — отсюда требование пилотной калибровки (раздел 8)."
            if worst_b
            else ""
        ),
        "",
    ]
    return lines


def margin_of_error(n: int) -> float:
    """Полуширина 95%-го интервала для доли около 0,5 — консервативная оценка погрешности."""
    return 1.96 * math.sqrt(0.25 / n) if n else float("nan")


def _leak(r: dict) -> list[str]:
    leak = r["leak"]
    scen = leak["scenarios"]
    exp = r["exposure"]
    cfg = r["config"]["leak"]
    lines = [
        "## 7. Устойчивость к утечке",
        "",
        f"**Пересечение попыток.** У двух попыток разных кандидатов одной специализации и грейда в среднем "
        f"{pct(leak['random_templates'])} общих шаблонов, но лишь **{pct(leak['random_instances'])}** общих "
        f"экземпляров (тот же текст, числа и варианты). У повторной попытки того же кандидата — "
        f"{pct(leak['retest_templates'])} и {pct(leak['retest_instances'])}. Ключ из чужой попытки подходит "
        "редко: выучить приходится концепцию шаблона.",
        "",
        f"**Сценарий «слили {pct(leak['share'], 0)} ключей».** {scen['adaptive_honest']['n']} кандидатов с "
        f"истинным уровнем ниже {GRADE_NAMES[leak['grade']]} сдают тест на {GRADE_NAMES[leak['grade']]}. "
        f"Базовая линия — фиксированный тест (одна форма для всех, {', '.join(f'{s}: {n}' for s, n in leak['form_size'].items())} "
        f"заданий), из него слиты {pct(leak['share'], 0)} ответов. В ITScout слиты {pct(leak['share'], 0)} "
        f"шаблонов банка вместе с {cfg['leaked_instances']} экземплярами каждого.",
        "",
    ]
    lines += table(
        ["Сценарий", "Прошли тест", "Завышение θ̂"],
        [
            [
                "Фиксированный тест, честно",
                pct(scen["fixed_honest"]["pass_rate"]),
                num(scen["fixed_honest"]["inflation"]),
            ],
            [
                "Фиксированный тест, утечка",
                pct(scen["fixed_leak"]["pass_rate"]),
                num(scen["fixed_leak"]["inflation"]),
            ],
            [
                "ITScout, честно",
                pct(scen["adaptive_honest"]["pass_rate"]),
                num(scen["adaptive_honest"]["inflation"]),
            ],
            [
                "Адаптивный тест без параметризации (ключ к шаблону)",
                pct(scen["adaptive_leak_template"]["pass_rate"]),
                num(scen["adaptive_leak_template"]["inflation"]),
            ],
            [
                "ITScout: параметризация (ключ к экземпляру)",
                pct(scen["adaptive_leak_instance"]["pass_rate"]),
                num(scen["adaptive_leak_instance"]["inflation"]),
            ],
        ],
    )
    lines += [
        "![Утечка](leak.png)",
        "",
        "Прирост доли «прошедших» от утечки: фиксированный тест — "
        f"{num((scen['fixed_leak']['pass_rate'] - scen['fixed_honest']['pass_rate']) * 100, 0)} п.п., "
        "адаптивный тест из того же банка без параметризации — "
        f"{num((scen['adaptive_leak_template']['pass_rate'] - scen['adaptive_honest']['pass_rate']) * 100, 0)} "
        "п.п., ITScout с параметризацией — "
        f"{num((scen['adaptive_leak_instance']['pass_rate'] - scen['adaptive_honest']['pass_rate']) * 100, 0)} "
        "п.п. Сами по себе банк и адаптивность от утечки ключей не защищают; защищает параметризация"
        + (
            " — но не полностью, потому что у части шаблонов мало различных экземпляров."
            if leak["diversity_high_hit_share"] > 0.05
            else ": слитый ключ подходит лишь к редким совпавшим экземплярам."
        ),
        "",
        f"**Разнообразие экземпляров.** Для каждого шаблона — {cfg['variant_renders']} рендеров и проверка, "
        f"есть ли экземпляр среди {cfg['leaked_instances']} слитых. Медианная вероятность совпадения — "
        f"{pct(leak['diversity_median_hit'])}, средняя — {pct(leak['diversity_mean_hit'])}; у "
        f"{pct(leak['diversity_high_hit_share'])} шаблонов она не ниже 50%. Самые уязвимые (число разных "
        "экземпляров на 200 рендеров):",
        "",
    ]
    lines += table(
        ["Шаблон", "Разных экземпляров", "Совпадение с утечкой"],
        [
            [f"`{row['template_id']}`", row["distinct"], pct(row["hit_rate"], 0)]
            for row in leak["most_leakable"]
        ],
    )
    lines += [
        "**Экспозиция.** Доля попыток специализации, в которых показан шаблон, к концу прогона:",
        "",
    ]
    lines += table(
        [
            "Специализация",
            "Попыток",
            "Активных шаблонов",
            "Использованы",
            "Макс.",
            "90-й перцентиль",
            f"Выше {pct(exp['cap'], 0)}",
        ],
        [
            [
                spec,
                v["attempts"],
                v["templates"],
                pct(v["used_share"], 0),
                pct(v["max"], 0),
                pct(v["p90"], 0),
                pct(v["over_cap_share"], 0),
            ]
            for spec, v in exp["by_spec"].items()
        ],
    )
    lines += [
        "![Экспозиция](exposure.png)",
        "",
        _exposure_note(r),
        "",
    ]
    return lines


def _exposure_note(r: dict) -> str:
    exp, length = r["exposure"], r["length"]
    needed = math.ceil(length["scored_mean"] / exp["cap"])
    smallest = min(v["templates"] for v in exp["by_spec"].values())
    if smallest < needed:
        return (
            f"Банк используется полностью, но порог экспозиции {pct(exp['cap'], 0)} недостижим арифметически: "
            "средняя экспозиция равна длине теста, делённой на число шаблонов специализации. Когда выше порога "
            "оказываются все шаблоны темы, Planner возвращается к полному списку — ограничение перестаёт "
            "действовать, и работает только мягкий вес 1/(1 + 10·доля). См. рекомендации."
        )
    worst = max(exp["by_spec"], key=lambda spec: exp["by_spec"][spec]["over_cap_share"])
    return (
        f"Банк используется полностью, и его размера хватает для порога {pct(exp['cap'], 0)}: нужно не меньше "
        f"{needed} активных шаблонов на специализацию, минимум сейчас — {smallest}. Выше порога остаются отдельные "
        f"шаблоны (больше всего у {worst} — {pct(exp['by_spec'][worst]['over_cap_share'], 0)}): у тем с большой "
        "квотой в blueprint'е шаблонов около порога грейда меньше, чем нужно для равномерной ротации, и Planner "
        "временно берёт их из полного списка темы."
    )


def _calibration(r: dict) -> list[str]:
    cal = r["calibration"]
    if not cal.get("n_templates"):
        return ["## 8. Калибровка", "", "Недостаточно ответов для калибровки при этом размере популяции.", ""]
    lines = [
        "## 8. Калибровка",
        "",
        "Параметры шаблонов восстанавливаются из симулированных ответов так же, как в продукте калибруются "
        "пилотные слоты: параметры остальных заданий попытки считаются известными, по ним строится "
        "апостериорное распределение θ, а a и b шаблона находятся максимизацией маргинального правдоподобия "
        "(fixed-parameter calibration, MML; реализация на numpy/scipy вместо пакета `girth` — меньше "
        "зависимостей, тот же метод).",
        "",
        f"По {cal['n_templates']} шаблонам (медиана {num(cal['median_responses'], 0)} ответов): "
        f"RMSE b = **{num(cal['rmse_b'])}** (смещение {num(cal['bias_b'])}, корреляция {num(cal['corr_b'])}), "
        f"RMSE a = {num(cal['rmse_a'])} (смещение {num(cal['bias_a'])}, корреляция {num(cal['corr_a'])}). "
        f"Экспертные a в банке лежат в узком диапазоне ({num(min(row['a'] for row in cal['rows']), 1)}–"
        f"{num(max(row['a'] for row in cal['rows']), 1)}), поэтому корреляция a малоинформативна; "
        "отрицательное смещение a — следствие σ_b и профиля по темам, которые «размывают» кривую ответа.",
        "",
    ]
    lines += table(
        ["Ответов на шаблон", "Шаблонов", "RMSE b", "RMSE a"],
        [
            [
                f"{g['from']}–{g['to'] if g['to'] < 10**8 else '∞'}",
                g["templates"],
                num(g["rmse_b"]),
                num(g["rmse_a"]),
            ]
            for g in cal["by_responses"]
        ],
    )
    lines += [
        "![Калибровка](calibration.png)",
        "",
    ]
    rich = cal["by_responses"][-1]
    small_error = min(
        (row for row in r["sensitivity"] if row["scenario"] == "bank_b_error"),
        key=lambda row: row["value"],
        default=None,
    )
    if small_error:
        lines += [
            f"Вывод для продукта: при {rich['from']}+ ответах на шаблон RMSE b = {num(rich['rmse_b'])}; в разделе 6 "
            f"ошибка b с σ = {num(small_error['value'])} даёт точность категории "
            f"{pct(small_error['category_accuracy'])}. Порядка 400 ответов — разумный порог перевода шаблона "
            "из `pilot` в `active`.",
            "",
        ]
    return lines


def _survey(r: dict) -> list[str]:
    survey = r["survey"]
    return [
        "## 9. Категоризация (специализация по опросу)",
        "",
        f"Синтетические ответы на опрос (типичный вид работы специализации; у "
        f"{pct(r['config']['survey']['atypical'], 0)} — нетипичный, у части — второй вид работы, другой язык, "
        f"заявленный стек из резюме) → продуктовый расчёт специализации. Топ-1 совпадает с истиной у "
        f"**{pct(survey['top1'])}**, истинная специализация в топ-2 (кандидат выбирает из двух) — у "
        f"{pct(survey['top2'])}. По специализациям: "
        + ", ".join(f"{s} — {pct(v)}" for s, v in survey["by_spec"].items())
        + ".",
        "",
        "Это верхняя оценка: ответы порождены той же логикой, что веса опроса. Разбор резюме (precision и "
        "recall полей на синтетических и реальных резюме) в этот прогон не входит — см. ограничения.",
        "",
    ]


def _matching(r: dict) -> list[str]:
    match = r["matching"]
    cfg = r["config"]["matching"]
    summary = match["summary"]
    lines = [
        "## 10. Подбор",
        "",
        f"{cfg['needs']} синтетических потребностей (по {cfg['needs'] // 5} на специализацию, грейды Junior–Senior, 3–4 "
        "обязательных и 1–2 желательных навыка, вилка, формат, город). Пул — вся популяция; у "
        f"{match['with_category']} кандидатов есть категория по тесту. **Истинная релевантность** 0–3 строится "
        "только из истинных специализации, грейда и стека: 3 — та же специализация и грейд, 2 — соседний "
        "грейд или смежная специализация, 1 — и то и другое; минус 1, если истинный стек покрывает меньше "
        f"половины обязательных навыков. P@k считает релевантными только точные совпадения (3), nDCG@10 "
        "учитывает всю шкалу. «Перерост» — доля в топ-10 кандидатов с истинным грейдом выше нужного. "
        f"Погрешность P@5 выдачи по категориям — ±{num(_p5_margin(match), 2)} (95%, по разбросу между "
        "потребностями): различия меньше этой величины не стоит интерпретировать.",
        "",
    ]
    metrics = match["metrics"]
    lines += table(
        [
            "Способ ранжирования",
            *[
                m.replace("p@", "P@").replace("ndcg@", "nDCG@").replace("overqualified@", "перерост@")
                for m in metrics
            ],
        ],
        [
            [RANKER_NAMES.get(k, k), *[pct(v[m], 0) if m.startswith("over") else num(v[m]) for m in metrics]]
            for k, v in summary.items()
        ],
    )
    grouped, top, by_test = summary["match_grouped"], summary["match"], summary["test_category"]
    declared, keywords = summary["declared_grade"], summary["keywords"]
    weights = match["rules"]
    penalty = weights["category_weight"] * (1 - weights["adjacent_grade_fit"])
    lines += [
        "![Подбор](matching.png)",
        "",
        "Выдача ITScout по умолчанию группирует кандидатов по категориям (сначала точная категория, затем "
        "соседний грейд и смежные специализации; внутри группы — по score), переключатель «общий топ» "
        "сортирует всех по score. Что показывает сравнение:",
        "",
        f"1. **Тест как фильтр точнее резюме.** Категория по тесту + ключевые слова: P@5 {num(by_test['p@5'])}, "
        f"nDCG@10 {num(by_test['ndcg@10'])}; заявленный грейд + те же ключевые слова: {num(declared['p@5'])} и "
        f"{num(declared['ndcg@10'])}; одни ключевые слова: {num(keywords['p@5'])} и {num(keywords['ndcg@10'])}. "
        "Сравнение щадящее для заявленного грейда: в симуляции он ошибается не больше чем на один (70% "
        "точны), а специализация известна точно.",
        f"2. **Выдача ITScout** (P@5 {num(grouped['p@5'])}, nDCG@10 {num(grouped['ndcg@10'])}) намного лучше "
        "ключевых слов"
        + (
            ", но уступает варианту «категория по тесту + ключевые слова». "
            if by_test["ndcg@10"] > grouped["ndcg@10"]
            else ". "
        )
        + "Внутри категории score упорядочивает по силе подтверждённого профиля (θ̂, ФСП, свежесть) и по "
        "проверенным навыкам — так задумано продуктом (§1), но синтетическая истина знает только "
        "специализацию, грейд и стек и за силу профиля не поощряет. Правильность порядка внутри категории "
        "проверяет только экспертная разметка (§12.2), её нет в автоматическом прогоне.",
        (
            f"3. **«Общий топ»** хуже группировки (P@5 {num(top['p@5'])}, перерост "
            f"{pct(top['overqualified@10'], 0)}): соседний грейд теряет на категории лишь "
            f"{num(penalty * 100, 0)} из 100 баллов score ({num(weights['category_weight'])} × "
            f"(1 − {num(weights['adjacent_grade_fit'], 1)})), и сильный кандидат соседнего грейда обгоняет "
            "точного. Поэтому группировка по категориям — правильный режим по умолчанию."
            if grouped["p@5"] - top["p@5"] > _p5_margin(match)
            else f"3. **«Общий топ»** не уступает группировке (P@5 {num(top['p@5'])} против "
            f"{num(grouped['p@5'])}, перерост {pct(top['overqualified@10'], 0)}): соседний грейд теряет на "
            f"категории {num(penalty * 100, 0)} из 100 баллов score, а кандидат, по тесту переросший нужный "
            "грейд, получает штраф в силе профиля. Группировка остаётся режимом по умолчанию — она нагляднее."
        ),
        "",
    ]
    return lines


def _p5_margin(match: dict) -> float:
    values = [row["match_grouped_p@5"] for row in match["needs"]]
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    sd = math.sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))
    return 1.96 * sd / math.sqrt(len(values))


def _weaknesses(r: dict) -> list[str]:
    rep, whatif, exp, leak, match = r["repeatability"], r["whatif"], r["exposure"], r["leak"], r["matching"]
    length = r["length"]
    cap = exp["cap"]
    needed = math.ceil(length["scored_mean"] / cap)
    worst_spec = min(exp["by_spec"], key=lambda s: exp["by_spec"][s]["templates"])
    lines = [
        "## 11. Слабые места и рекомендации",
        "",
        "Пороги, blueprint'ы, веса и движок по результатам прогона **автоматически не меняются** — ниже "
        "то, что рекомендуется, с цифрами из симуляции.",
        "",
        f"### 11.1. Трёхуровневое решение повторяется в {pct(rep['three_level_agreement'], 0)} случаев",
        "",
        "Решение «пройден уверенно» — это не категория, а предложение сразу сдать тест на грейд выше. Его "
        "ошибка стоит кандидату одного лишнего (или недостающего) теста, а итоговая категория определяется "
        f"следующим тестом: она повторяется в {pct(rep['category_agreement'])} случаев и в пределах грейда в "
        f"{pct(rep['category_within_one'])}. Альтернативы проверены на {r['config']['whatif']['subset']} "
        "кандидатах (каждый дважды проходит калибровку, движок не менялся — правило и длина подставлены "
        "в симуляции):",
        "",
    ]
    lines += table(
        [
            "Правило / длина",
            "Точность категории",
            "Повтор категории",
            "Повтор 3-уровн.",
            "«Уверенно» выдано",
            "Точность «уверенно»",
            "Полнота «уверенно»",
            "Занижено",
            "Тестов на кандидата",
            "Заданий в тесте",
        ],
        [
            [
                WHATIF_NAMES.get(w["rule"], w["rule"]),
                pct(w["category_accuracy"]),
                pct(w["category_agreement"]),
                pct(w["three_level_agreement"]),
                pct(w["confident_share"], 0),
                pct(w["confident_precision"], 0),
                pct(w["confident_recall"], 0),
                pct(w["under_assigned"]),
                num(w["tests_per_candidate"], 2),
                num(w["scored_mean"], 1),
            ]
            for w in whatif
        ],
    )
    current = next((w for w in whatif if w["rule"] == "current"), whatif[0])
    stricter = next((w for w in whatif if w["rule"] == "high_0se"), None)
    longer = [w for w in whatif if w["rule"] in {"extra_8", "stage2_13"}]
    margin = margin_of_error(r["config"]["whatif"]["subset"])
    lines += [
        "«Точность / полнота «уверенно»» — среди тестов на грейды ниже Senior доля «уверенно» у тех, чей "
        "истинный уровень действительно не ниже следующего грейда, и доля таких кандидатов, получивших "
        f"«уверенно». Текущее правило настроено на полноту ({pct(current['confident_recall'], 0)} при точности "
        f"{pct(current['confident_precision'], 0)}): почти никого, кто перерос заявленный грейд, не оставляют "
        "без предложения теста выше — ценой лишних тестов. Погрешность долей в таблице — до "
        f"±{num(margin * 100, 1)} п.п. (95%); варианты считаются на одних и тех же seed, поэтому разности "
        "между строками точнее, но различия в 1–2 п.п. всё равно не стоит интерпретировать.",
        "",
    ]
    rec = [
        "**Рекомендации.**",
        "",
        "1. Оценивать надёжность по итоговой категории (κ и совпадение категории), а трёхуровневое решение "
        "показывать кандидату как «можно попробовать грейд выше», а не как результат.",
    ]
    if stricter:
        rec.append(
            f"2. Если важнее меньше лишних тестов — правило θ̂ ≥ cut_{{G+1}}: повтор 3-уровневого решения "
            f"{pct(current['three_level_agreement'])} → {pct(stricter['three_level_agreement'])}, тестов на кандидата "
            f"{num(current['tests_per_candidate'], 2)} → {num(stricter['tests_per_candidate'], 2)}, но занижение "
            f"категории {pct(current['under_assigned'])} → {pct(stricter['under_assigned'])}. При текущем приоритете "
            "(не занижать сильных) правило стоит оставить."
        )
    if longer:
        best_long = max(longer, key=lambda w: w["category_agreement"])
        gain = best_long["category_agreement"] - current["category_agreement"]
        rec.append(
            f"3. Повторяемость растёт только от точности у порогов: вариант «{WHATIF_NAMES[best_long['rule']]}» "
            f"даёт повтор категории {pct(current['category_agreement'])} → {pct(best_long['category_agreement'])} и "
            f"3-уровневого решения {pct(current['three_level_agreement'])} → {pct(best_long['three_level_agreement'])} "
            f"ценой {num(best_long['scored_mean'] - current['scored_mean'], 1)} задания в среднем"
            + (
                " — выигрыш на уровне погрешности, удлинять тест целиком невыгодно. "
                if gain < margin
                else ". "
            )
            + "Точечнее — добавлять задания у cut_{G+1}, когда |θ̂ − cut_{G+1}| < SE (сейчас доп. задания "
            "даются только у cut_G); это изменение движка, его нужно проверить этим же прогоном."
        )
    lines += rec + [""]
    smallest = min(v["templates"] for v in exp["by_spec"].values())
    if smallest < needed:
        lines += [
            f"### 11.2. Порог экспозиции {pct(cap, 0)} недостижим при текущем банке",
            "",
            f"При {num(length['scored_mean'], 1)} оценённых заданиях на попытку порог {pct(cap, 0)} требует не "
            f"меньше **{needed} активных шаблонов** на специализацию; сейчас их "
            + ", ".join(f"{s} — {v['templates']}" for s, v in exp["by_spec"].items())
            + f". Минимальный банк у {worst_spec}. Рекомендация: довести банк до ≥ {needed} активных шаблонов "
            "на специализацию (цель «≥ 3× длины теста» из §10.6 недостаточна для порога 25%) или задать порог "
            "относительно размера банка: cap = max(0,25; 1,5 × длина / число шаблонов темы).",
            "",
        ]
    else:
        worst = max(exp["by_spec"], key=lambda spec: exp["by_spec"][spec]["over_cap_share"])
        lines += [
            "### 11.2. Экспозиция: размер банка достаточен, остаются отдельные темы",
            "",
            f"Порог {pct(cap, 0)} при {num(length['scored_mean'], 1)} оценённых заданиях требует ≥ {needed} "
            "активных шаблонов на специализацию; сейчас "
            + ", ".join(f"{s} — {v['templates']}" for s, v in exp["by_spec"].items())
            + f". Выше порога — до {pct(exp['by_spec'][worst]['over_cap_share'], 0)} шаблонов ({worst}). "
            "Рекомендация: пополнять в первую очередь темы с самой большой квотой blueprint'а шаблонами со "
            "сложностью около порогов Junior и Middle, где отбор идёт чаще всего.",
            "",
        ]
    high_hit = leak["diversity_high_hit_share"]
    lines += [
        "### 11.3. Разнообразие экземпляров",
        "",
        f"У {pct(high_hit, 0)} шаблонов слитые {r['config']['leak']['leaked_instances']} экземпляров покрывают "
        "половину и больше будущих экземпляров; медианная вероятность совпадения — "
        f"{pct(leak['diversity_median_hit'])}. "
        + (
            "Нужно расширить параметры (пулы имён, чисел, вариантов-дистракторов) в первую очередь у шаблонов "
            "из таблицы раздела 7."
            if high_hit > 0.05
            else "Параметризация достаточна; новые шаблоны стоит проверять тем же порогом (≥ 60 разных "
            "экземпляров на 200 рендеров), шаблоны из таблицы раздела 7 — первые кандидаты на расширение."
        ),
        "",
    ]
    summary = match["summary"]
    grouped, top = summary["match_grouped"], summary["match"]
    adjacent = match["rules"]["adjacent_grade_fit"]
    by_test = summary["test_category"]
    lines += [
        "### 11.4. Подбор: порядок внутри категории",
        "",
        f"Выдача ITScout: P@5 {num(grouped['p@5'])} по категориям и {num(top['p@5'])} в «общем топе», "
        f"перерост в топ-10 — {pct(grouped['overqualified@10'], 0)} и {pct(top['overqualified@10'], 0)} "
        f"(штраф соседнего грейда `category_fit.adjacent_grade` — {num(adjacent, 2)}). Вариант «категория по "
        f"тесту + ключевые слова» даёт {num(by_test['p@5'])}: синтетическая истина считает релевантным только "
        "нужный грейд и стек, а score учитывает ещё ФСП, свежесть и условия. Какой порядок внутри категории "
        "полезнее работодателю, проверяет экспертная разметка пар «потребность — кандидат» (§12.2) — до неё "
        "веса дальше не меняются.",
        "",
    ]
    tif, bank, cuts = r["discrimination"]["tif"], r["bank"], r["cuts"]
    shifted = [g for g, v in tif.items() if abs(v["peak"] - v["cut"]) > 0.5]
    if shifted:
        few_easy = min(v["below_junior_cut"] for v in bank.values()) < 15
        lines += [
            "### 11.5. Информация теста у нижних порогов",
            "",
            "Максимум информации теста смещён от порога у "
            + ", ".join(
                f"{GRADE_NAMES[g]} (порог {num(tif[g]['cut'], 1)}, максимум {num(tif[g]['peak'], 1)})"
                for g in shifted
            )
            + ". Активных шаблонов легче порога Junior "
            f"({num(cuts['junior'], 1)}): "
            + ", ".join(f"{s} — {v['below_junior_cut']}" for s, v in bank.items())
            + f"; труднее порога Senior ({num(cuts['senior'], 1)}): "
            + ", ".join(f"{s} — {v['above_senior_cut']}" for s, v in bank.items())
            + ". "
            + (
                "Рекомендация: в каждую специализацию добавить 8–10 шаблонов с b от −2,2 до −1,0 (решения "
                "Intern/Junior) и 4–6 с b выше 1,4, затем повторить `make validate`."
                if few_easy
                else "Лёгких шаблонов уже достаточно; оставшееся смещение — от угадывания в заданиях с выбором "
                "(у 3PL максимум информации правее b) и от того, что самые лёгкие шаблоны лежат около −1,8. "
                "Рекомендация: для теста на Intern добавить задания с открытым числовым ответом (без угадывания) "
                "и b от −2,4 до −1,8."
            ),
            "",
        ]
    return lines


def _limitations(r: dict) -> list[str]:
    return [
        "## 12. Ограничения",
        "",
        "- **Симуляция проверяет механику при заданной модели ответов.** Ответы порождены 3PL с параметрами "
        "банка (плюс σ_b и профиль по темам), поэтому цифры — оценка сверху для реальных людей. Реальную "
        "калибровку параметров дают только пилотные данные: пилотные слоты в каждой попытке (неоцениваемые) "
        "и периодическая перекалибровка тем же методом, что в разделе 8; шаблон становится `active`, когда "
        "набрал ~400 ответов.",
        "- **Пороги грейдов** — стартовые экспертные значения; окончательные задаются процедурой modified "
        "Angoff (§10.4). Симуляция проверяет точность решения относительно порогов, а не сами пороги.",
        "- **Синтетические опрос, резюме, ФСП и свежесть.** Результаты разделов 9–10 показывают, что механика "
        "работает как задумано, но не заменяют проверку на живых данных. Precision и recall разбора резюме "
        "(30 синтетических и 5–10 реальных резюме) не измерены — нужен готовый разбор резюме (T15).",
        "- **Экспертная оценка подбора** (разметка 100 пар «потребность — кандидат» ИТ-специалистами, "
        "корреляция Спирмена и P@5) требует людей и в автоматический прогон не входит; функции метрик "
        "(`validation/stats.py`) для неё готовы.",
        "- **Открытый вопрос о подходе** не входит в θ̂ и не моделируется; лимиты времени, person-fit и "
        "поведенческие сигналы (уход со вкладки) в симуляции не участвуют.",
        "- **Сценарий утечки** предполагает, что слитые экземпляры — случайные; целенаправленный сбор "
        "экземпляров одного шаблона (много попыток одного человека) ограничивают интервалы между попытками (§6.3).",
        "",
    ]
