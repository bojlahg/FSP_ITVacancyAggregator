"""Графики отчёта валидации (matplotlib, PNG). Цвета — брендбук ФСП (AGENTS.md)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

PRIMARY = "#402FFF"
ACCENT = "#EC1D35"
DARK = "#1B1C21"
GREY = "#8C8D91"
LIGHT = "#C8C9CA"
SURFACE = "#FFFFFF"
# Порядковая шкала грейдов: от светлого к насыщенному основному цвету
GRADE_COLORS = ["#A9A2FF", "#7D71FF", "#5A4BFF", "#2A1BC2"]
SEQUENTIAL = LinearSegmentedColormap.from_list("brand", ["#F3F2FF", PRIMARY])

GRADE_NAMES = {"none": "Нет", "intern": "Intern", "junior": "Junior", "middle": "Middle", "senior": "Senior"}


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 110,
            "font.size": 9.5,
            "axes.edgecolor": LIGHT,
            "axes.labelcolor": DARK,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "axes.titlecolor": DARK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#EDEDED",
            "grid.linewidth": 0.8,
            "xtick.color": GREY,
            "ytick.color": GREY,
            "legend.frameon": False,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
        }
    )


def _save(fig, out: Path, name: str) -> str:
    fig.tight_layout()
    fig.savefig(out / name, metadata={"Software": None})
    plt.close(fig)
    return name


def _cut_lines(ax, cuts: dict[str, float], vertical: bool = True, label_at: float = 1.0) -> None:
    for grade, cut in cuts.items():
        if vertical:
            ax.axvline(cut, color=ACCENT, linewidth=0.8, linestyle="--", alpha=0.7)
            ax.annotate(
                f"cut {grade}",
                (cut, label_at),
                xycoords=("data", "axes fraction"),
                fontsize=7.5,
                color=ACCENT,
                rotation=90,
                ha="right",
                va="top" if label_at > 0.5 else "bottom",
            )
        else:
            ax.axhline(cut, color=ACCENT, linewidth=0.8, linestyle="--", alpha=0.7)


def theta_recovery(raw: dict, cuts: dict, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(6.2, 5.0))
    ax.scatter(raw["theta_true"], raw["theta_hat"], s=6, color=PRIMARY, alpha=0.35, linewidths=0)
    ax.plot([-3.2, 3.2], [-3.2, 3.2], color=DARK, linewidth=1)
    _cut_lines(ax, cuts)
    ax.set_xlim(-3.2, 3.2)
    ax.set_ylim(-3.2, 3.2)
    ax.set_xlabel("Истинная способность θ")
    ax.set_ylabel("Оценка θ̂ (EAP) после теста на заявленный грейд")
    ax.set_title("Восстановление способности")
    return _save(fig, out, "theta_recovery.png")


def theta_error(rows: list[dict], cuts: dict, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    centers = [(r["from"] + r["to"]) / 2 for r in rows]
    ax.plot(
        centers, [r["rmse"] for r in rows], color=PRIMARY, linewidth=2, marker="o", markersize=5, label="RMSE"
    )
    ax.plot(
        centers,
        [r["mean_se"] for r in rows],
        color=GREY,
        linewidth=2,
        marker="s",
        markersize=5,
        label="средняя SE (как оценивает себя движок)",
    )
    ax.plot(
        centers,
        [r["bias"] for r in rows],
        color=DARK,
        linewidth=2,
        marker="^",
        markersize=5,
        label="смещение θ̂ − θ",
    )
    ax.axhline(0, color=LIGHT, linewidth=1)
    _cut_lines(ax, cuts)
    ax.set_xlabel("Истинная способность θ (интервалы по 0,5)")
    ax.set_ylabel("Логиты")
    ax.set_title("Точность θ̂ в зависимости от уровня")
    ax.legend(loc="lower left")
    return _save(fig, out, "theta_error.png")


def confusion(category: dict, out: Path) -> str:
    matrix = np.array(category["matrix"], dtype=float)
    labels = [GRADE_NAMES[label] for label in category["labels"]]
    shares = matrix / np.maximum(matrix.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    ax.imshow(shares, cmap=SEQUENTIAL, vmin=0, vmax=1)
    ax.grid(False)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if matrix[i, j]:
                color = SURFACE if shares[i, j] > 0.55 else DARK
                ax.text(
                    j,
                    i,
                    f"{int(matrix[i, j])}\n{shares[i, j]:.0%}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=color,
                )
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Категория по тесту")
    ax.set_ylabel("Истинный грейд")
    ax.set_title("Матрица ошибок категории")
    return _save(fig, out, "category_confusion.png")


def decision_curve(raw: dict, out: Path) -> str:
    distance = np.array(raw["distance"])
    passed = np.array(raw["passed"], dtype=float)
    agree = (np.array(raw["passed"]) == np.array(raw["passed_retest"])).astype(float)
    edges = np.arange(-2.0, 2.01, 0.25)
    centers, pass_rate, agreement = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (distance >= lo) & (distance < hi)
        # Узкие интервалы с малым числом кандидатов дают шумные точки — не показываем
        if mask.sum() >= 40:
            centers.append((lo + hi) / 2)
            pass_rate.append(passed[mask].mean())
            agreement.append(agree[mask].mean())
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8))
    axes[0].plot(centers, pass_rate, color=PRIMARY, linewidth=2, marker="o", markersize=5)
    axes[0].axvline(0, color=ACCENT, linestyle="--", linewidth=0.8)
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[0].set_xlabel("θ_true − порог заявленного грейда")
    axes[0].set_ylabel("Доля «пройден»")
    axes[0].set_title("Решение о грейде: операционная кривая")
    axes[1].plot(centers, agreement, color=PRIMARY, linewidth=2, marker="o", markersize=5)
    axes[1].axvline(0, color=ACCENT, linestyle="--", linewidth=0.8)
    axes[1].set_ylim(0.0, 1.02)
    axes[1].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[1].set_xlabel("θ_true − порог заявленного грейда")
    axes[1].set_ylabel("Совпадение пройден/не пройден")
    axes[1].set_title("Повторное прохождение (другие задания)")
    return _save(fig, out, "decision_curve.png")


def test_information(discrimination: dict, cuts: dict, out: Path) -> str:
    grid = np.array(discrimination["grid"])
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    for color, (grade, item) in zip(GRADE_COLORS, discrimination["tif"].items(), strict=False):
        ax.plot(
            grid, np.array(item["curve"]), color=color, linewidth=2, label=f"тест на {GRADE_NAMES[grade]}"
        )
    _cut_lines(ax, cuts, label_at=0.02)
    ax.set_xlim(-3.5, 3.5)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlabel("θ")
    ax.set_ylabel("Информация теста I(θ)")
    ax.set_title("Информационная функция теста по целевому грейду")
    return _save(fig, out, "test_information.png")


def theta_by_grade(raw: dict, cuts: dict, out: Path) -> str:
    groups = ["none", "intern", "junior", "middle", "senior"]
    data = [
        [h for h, g in zip(raw["theta_hat"], raw["true_grade"], strict=True) if g == grade]
        for grade in groups
    ]
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    parts = ax.boxplot(data, patch_artist=True, widths=0.55, showfliers=False)
    for patch in parts["boxes"]:
        patch.set(facecolor="#E6E3FF", edgecolor=PRIMARY)
    for key in ("medians",):
        for line in parts[key]:
            line.set(color=PRIMARY, linewidth=2)
    for key in ("whiskers", "caps"):
        for line in parts[key]:
            line.set(color=GREY)
    _cut_lines(ax, cuts, vertical=False)
    ax.set_xticks(range(1, len(groups) + 1), [GRADE_NAMES[g] for g in groups])
    ax.set_xlabel("Истинный грейд")
    ax.set_ylabel("θ̂")
    ax.set_title("Оценки сильных и слабых кандидатов (пунктир — пороги)")
    return _save(fig, out, "theta_by_true_grade.png")


def discrimination_hist(discrimination: dict, out: Path) -> str:
    values = [row["r"] for row in discrimination["templates"] if row["r"] == row["r"]]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    ax.hist(values, bins=np.arange(-0.1, 0.81, 0.05), color=PRIMARY, edgecolor=SURFACE, linewidth=2)
    ax.axvline(discrimination["weak_r"], color=ACCENT, linestyle="--", linewidth=1)
    ax.set_xlabel("Точечно-бисериальная корреляция ответа с θ̂")
    ax.set_ylabel("Шаблонов")
    ax.set_title("Дискриминативность шаблонов")
    return _save(fig, out, "discrimination.png")


def exposure(exposure: dict, out: Path) -> str:
    specs = list(exposure["by_spec"])
    fig, axes = plt.subplots(1, len(specs), figsize=(11, 3.2), sharey=True)
    for ax, spec in zip(np.atleast_1d(axes), specs, strict=True):
        values = exposure["by_spec"][spec]["sorted"]
        ax.bar(range(len(values)), values, color=PRIMARY, width=0.85)
        ax.axhline(exposure["cap"], color=ACCENT, linestyle="--", linewidth=1)
        ax.set_title(spec)
        ax.set_xlabel("шаблоны")
        ax.grid(axis="x", visible=False)
    np.atleast_1d(axes)[0].set_ylabel("Доля попыток с шаблоном")
    np.atleast_1d(axes)[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    fig.suptitle("Экспозиция шаблонов (пунктир — порог исключения 25%)", fontsize=10.5, fontweight="bold")
    return _save(fig, out, "exposure.png")


def leak(leak: dict, out: Path) -> str:
    scenarios = leak["scenarios"]
    groups = [
        ("Фиксированный\nтест", "fixed_honest", "fixed_leak"),
        ("Адаптивный, ключ\nподходит к шаблону", "adaptive_honest", "adaptive_leak_template"),
        ("ITScout: ключ\nк экземпляру", "adaptive_honest", "adaptive_leak_instance"),
    ]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    honest = [scenarios[h]["pass_rate"] for _, h, _ in groups]
    leaked = [scenarios[k]["pass_rate"] for _, _, k in groups]
    ax.bar(x - 0.2, honest, width=0.38, color=LIGHT, label="честно")
    ax.bar(x + 0.2, leaked, width=0.38, color=ACCENT, label=f"слито {leak['share']:.0%} ключей")
    for xi, value in zip(x - 0.2, honest, strict=True):
        ax.text(xi, value + 0.01, f"{value:.0%}", ha="center", fontsize=8, color=DARK)
    for xi, value in zip(x + 0.2, leaked, strict=True):
        ax.text(xi, value + 0.01, f"{value:.0%}", ha="center", fontsize=8, color=DARK)
    ax.set_xticks(x, [name for name, _, _ in groups])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylabel(f"Прошли тест на {GRADE_NAMES[leak['grade']]}")
    ax.set_title(f"Кандидаты ниже {GRADE_NAMES[leak['grade']]}: эффект утечки ключей")
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)
    return _save(fig, out, "leak.png")


def calibration(calibration: dict, out: Path) -> str:
    rows = calibration["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0))
    for ax, param, title in ((axes[0], "b", "Сложность b"), (axes[1], "a", "Дискриминация a")):
        true = [r[param] for r in rows]
        est = [r[f"{param}_hat"] for r in rows]
        ax.scatter(true, est, s=10, color=PRIMARY, alpha=0.6, linewidths=0)
        lo, hi = min(true + est), max(true + est)
        ax.plot([lo, hi], [lo, hi], color=DARK, linewidth=1)
        ax.set_xlabel(f"{param} в банке (истина симуляции)")
        ax.set_ylabel(f"{param} восстановленный")
        ax.set_title(title)
    return _save(fig, out, "calibration.png")


def matching(matching: dict, names: dict[str, str], out: Path) -> str:
    rankers = list(matching["summary"])
    metrics = [m for m in matching["metrics"] if m != "overqualified@10"]
    colors = {
        "match_grouped": PRIMARY,
        "match": "#A9A2FF",
        "test_category": DARK,
        "declared_grade": GREY,
        "keywords": LIGHT,
    }
    width = 0.8 / len(rankers)
    x = np.arange(len(metrics))
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    for index, ranker in enumerate(rankers):
        values = [matching["summary"][ranker][m] for m in metrics]
        ax.bar(
            x + (index - (len(rankers) - 1) / 2) * width,
            values,
            width=width * 0.92,
            color=colors.get(ranker, GREY),
            label=names.get(ranker, ranker),
        )
    ax.set_xticks(x, [m.replace("p@", "P@").replace("ndcg@", "nDCG@") for m in metrics])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Среднее по потребностям")
    ax.set_title("Качество подбора: способы ранжирования")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, fontsize=8)
    ax.grid(axis="x", visible=False)
    return _save(fig, out, "matching.png")


def draw_all(results: dict, out: Path, ranker_names: dict[str, str]) -> list[str]:
    _style()
    cuts = results["cuts"]
    raw = results["raw"]
    return [
        theta_recovery(raw, cuts, out),
        theta_error(results["theta"]["by_level"], cuts, out),
        confusion(results["category"], out),
        decision_curve(raw, out),
        test_information(results["discrimination"], cuts, out),
        theta_by_grade(raw, cuts, out),
        discrimination_hist(results["discrimination"], out),
        exposure(results["exposure"], out),
        leak(results["leak"], out),
        calibration(results["calibration"], out),
        matching(results["matching"], ranker_names, out),
    ]
