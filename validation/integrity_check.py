"""Проверка сигналов честности (§10.9) на симуляции: ложные срабатывания и мощность детектора.

`make integrity-check` или `cd backend && uv run python ../validation/integrity_check.py`
→ docs/validation/integrity.md. Тот же движок (Planner, EAP) и тот же engine/integrity.py, что в API.

Одна популяция проходит тест на заявленный грейд трижды с разным поведением:
честно, с предзнанием части банка (знает логику решения утёкших шаблонов и отвечает быстро) и
с быстрым угадыванием части заданий. Время ответа — логнормальная модель (van der Linden, 2007).
"""

import argparse
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.modules.testing.engine import integrity  # noqa: E402
from app.modules.testing.engine.bank import get_bank, get_blueprints  # noqa: E402
from app.modules.testing.engine.render import render  # noqa: E402
from app.modules.testing.engine.session import Answered, AttemptConfig, Planner  # noqa: E402
from validation.engine_sim import Environment, attempt_seed, instance_key, p_correct  # noqa: E402
from validation.population import Person, build_population  # noqa: E402
from validation.report import num, pct, table  # noqa: E402
from validation.run import load_config  # noqa: E402

GROUPS = ("honest", "preknowledge", "rapid")
GROUP_NAMES = {
    "honest": "Честные",
    "preknowledge": "Предзнание утёкших шаблонов",
    "rapid": "Быстрое угадывание",
}
REASON_NAMES = {
    integrity.PERSON_FIT: "lz*",
    integrity.RAPID_GUESSING: "быстрые ответы",
    integrity.FAST_CORRECT_HARD: "быстро и верно на трудном",
}
DEFAULT_OUT = ROOT / "docs" / "validation" / "integrity.md"


@dataclass(frozen=True)
class Outcome:
    group: str
    theta: float
    theta_true: float
    result: integrity.IntegrityResult


def leaked(spec: str, template_id: str, share: float, seed: int) -> bool:
    """Утёкшие шаблоны — детерминированная доля банка специализации."""
    return random.Random(f"leak:{seed}:{spec}:{template_id}").random() < share


def response_time(rng: random.Random, limit: float, fraction: float, log_sd: float, speed: float) -> float:
    # ln T ~ N(ln(доля·лимит) − τ, σ²): логнормальная модель скорости (van der Linden, 2007)
    return min(limit, math.exp(rng.gauss(math.log(fraction * limit) - speed, log_sd)))


def simulate(person: Person, group: str, env: Environment, cfg: dict, seed: int) -> Outcome:
    config = AttemptConfig(
        person.spec, person.declared, attempt_seed("integrity", seed, person.pid), env.mode, person.modules
    )
    planner = Planner(config, env.bank, env.blueprints, {})
    rng = random.Random(f"integrity:{seed}:{group}:{person.pid}")
    rt, pk, rapid = cfg["rt"], cfg["preknowledge"], cfg["rapid"]
    speed = rng.gauss(0.0, rt["speed_sd"])
    history: list[Answered] = []
    responses: list[integrity.TimedResponse] = []
    while (next_item := planner.next_item(history)) is not None:
        template = next_item.template
        if template.kind == "open_approach":
            history.append(Answered(template.id, next_item.stage, next_item.scored, None))
            continue
        limit = float(template.time_limit_sec)
        key = instance_key(render(template, next_item.instance_seed))
        p = p_correct(person, template, key, env)
        if group == "preknowledge" and leaked(person.spec, template.id, pk["leaked_share"], seed):
            correct = rng.random() < pk["correct"]
            time_sec = response_time(rng, limit, pk["time_fraction"], pk["log_sd"], speed)
        elif (group == "rapid" and rng.random() < rapid["item_share"]) or rng.random() < rt["honest_skip"]:
            correct = rng.random() < template.guessing
            time_sec = rng.uniform(*rapid["time_sec"])
        else:
            correct = rng.random() < p
            time_sec = response_time(rng, limit, rt["typical_fraction"], rt["log_sd"], speed)
        score = 1.0 if correct else 0.0
        history.append(Answered(template.id, next_item.stage, next_item.scored, score))
        if next_item.scored:
            responses.append(
                integrity.TimedResponse(
                    template.irt.a, template.irt.b, template.guessing, score, time_sec, limit
                )
            )
    theta = planner.summarize(history).theta
    return Outcome(group, theta, person.theta, integrity.evaluate(responses, theta, integrity.get_rules()))


def run(config: dict, size: int | None = None) -> dict:
    cfg = config["integrity"]
    config = {**config, "population": {**config["population"], "size": size or cfg["size"]}}
    blueprints = get_blueprints()
    env = Environment(bank=get_bank(), blueprints=blueprints, instance_sd=config["response"]["instance_sd"])
    topics = {spec: sorted(bp.topics) for spec, bp in blueprints.specializations.items()}
    people = build_population(config, blueprints, topics)
    outcomes = [simulate(person, group, env, cfg, config["seed"]) for group in GROUPS for person in people]
    return summarize(outcomes)


def summarize(outcomes: list[Outcome]) -> dict:
    groups = {}
    for group in GROUPS:
        rows = [o for o in outcomes if o.group == group]
        scored = [o for o in rows if o.result.enough_data]
        n = max(len(scored), 1)
        groups[group] = {
            "attempts": len(rows),
            "enough_data": len(scored),
            "flagged": sum(o.result.flagged for o in scored) / n,
            "by_reason": {
                reason: sum(reason in o.result.reasons for o in scored) / n for reason in integrity.REASONS
            },
            "theta_bias": sum(o.theta - o.theta_true for o in rows) / max(len(rows), 1),
        }
    return {"groups": groups}


def margin(share: float, n: int) -> float:
    """Полуширина 95%-го интервала доли (нормальное приближение)."""
    return 1.96 * math.sqrt(share * (1 - share) / n) if n else float("nan")


def build_markdown(results: dict, config: dict) -> list[str]:
    cfg = config["integrity"]
    rules = integrity.get_rules()
    groups = results["groups"]
    honest = groups["honest"]
    rows = [
        [
            GROUP_NAMES[group],
            str(g["enough_data"]),
            f"**{pct(g['flagged'])}** ± {pct(margin(g['flagged'], g['enough_data']))}",
            *[pct(g["by_reason"][reason]) for reason in integrity.REASONS],
            num(g["theta_bias"]),
        ]
        for group, g in groups.items()
    ]
    return [
        "# Сигналы честности: проверка на симуляции",
        "",
        "Генерируется `make integrity-check` (`validation/integrity_check.py`), seed "
        f"{config['seed']}. Устройство сигналов — `docs/implementation.md` §10.9, пороги — "
        "`backend/content/integrity.yaml`. Сигналы — пометка для работодателя «стоит перепроверить», "
        "в грейд, категорию и score не входят.",
        "",
        "## Результат",
        "",
        *table(
            ["Группа", "Попыток", "Помечено", *[REASON_NAMES[r] for r in integrity.REASONS], "Сдвиг θ̂"],
            rows,
        ),
        f"- **Ложные срабатывания** на честных кандидатах: {pct(honest['flagged'])} "
        f"(lz* — {pct(honest['by_reason'][integrity.PERSON_FIT])} при номинальных 5% для порога "
        f"{num(rules.person_fit.threshold, 3)}).",
        f"- **Предзнание** {pct(cfg['preknowledge']['leaked_share'], 0)} шаблонов: помечено "
        f"{pct(groups['preknowledge']['flagged'])}, θ̂ завышена в среднем на "
        f"{num(groups['preknowledge']['theta_bias'] - honest['theta_bias'])} логита "
        "относительно честного прохождения. Ловит его в основном сигнал быстрых ответов: "
        "на утёкшем шаблоне ответ даётся быстрее порога NT10.",
        f"- **Быстрое угадывание** {pct(cfg['rapid']['item_share'], 0)} заданий: помечено "
        f"{pct(groups['rapid']['flagged'])}.",
        "- «±» — 95% погрешность доли. Попытки с числом оценённых заданий меньше "
        f"{rules.min_items} получают «недостаточно данных» и в доли не входят.",
        "",
        "## Модель симуляции",
        "",
        f"- Популяция — та же, что в основной валидации (§12.1), {groups['honest']['attempts']} кандидатов; "
        "каждый проходит тест на заявленный грейд трижды — по разу в каждой группе.",
        "- Честный ответ — 3PL от θ_true; время — логнормальное: медиана "
        f"{pct(cfg['rt']['typical_fraction'], 0)} "
        f"лимита задания, σ ln T = {num(cfg['rt']['log_sd'])}, индивидуальная скорость τ ~ N(0, "
        f"{num(cfg['rt']['speed_sd'])}²). С вероятностью {pct(cfg['rt']['honest_skip'], 0)} честный кандидат "
        "пропускает задание быстрым угадыванием.",
        f"- Предзнание: кандидат знает логику решения утёкших шаблонов (параметризация меняет числа, "
        f"поэтому утекает только логика) — верно с вероятностью {pct(cfg['preknowledge']['correct'], 0)}, "
        f"медиана времени {pct(cfg['preknowledge']['time_fraction'], 0)} лимита.",
        f"- Быстрое угадывание: {pct(cfg['rapid']['item_share'], 0)} заданий — ответ за "
        f"{cfg['rapid']['time_sec'][0]}–{cfg['rapid']['time_sec'][1]} с, "
        "верно с вероятностью угадывания c.",
        "",
        "## Ограничения",
        "",
        "- Нормы времени выдуманы: реальных времён ответа ещё нет. Порог NT10 считается от лимита задания; "
        "после запуска его стоит пересчитать по фактическому типичному времени шаблона.",
        "- Доли ложных срабатываний зависят от модели времени; на реальных данных их нужно пересчитать "
        "до того, как показывать сигналы в продукте как значимые.",
        "- lz* на адаптивном тесте маломощен: задания подобраны около θ̂, поэтому основной вклад в "
        "обнаружение дают сигналы по времени.",
        "- «Быстро и верно на трудном» почти не срабатывает: предзнание само завышает θ̂, а адаптивный "
        "тест подбирает задания около θ̂, и трудных относительно θ̂ заданий остаётся мало. Сильнее был бы "
        "детектор Sinharay (2020), сравнивающий скорость на утёкших и прочих шаблонах, — для него нужен "
        "список скомпрометированных шаблонов (высокая экспозиция или подтверждённая утечка).",
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка сигналов честности на симуляции")
    parser.add_argument(
        "--size", type=int, help="размер популяции (по умолчанию integrity.size из config.yaml)"
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    config = load_config(seed=args.seed)
    results = run(config, args.size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(build_markdown(results, config)), encoding="utf-8")
    print(f"отчёт: {args.out}")


if __name__ == "__main__":
    main()
