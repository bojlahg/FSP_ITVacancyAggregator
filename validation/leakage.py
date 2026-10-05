"""Устойчивость к утечке (§10.6, §12.2): пересечение попыток, разнообразие экземпляров, «слили 30%»."""

import random
from collections import defaultdict

from app.modules.testing.engine.irt import ItemResponse, eap
from app.modules.testing.engine.render import render
from validation.engine_sim import (
    Attempt,
    Environment,
    Exposure,
    attempt_seed,
    instance_key,
    p_correct,
    run_attempt,
)
from validation.population import Person


def overlap(first: Attempt, second: Attempt) -> tuple[float, float]:
    """Доля оценённых шаблонов и экземпляров первой попытки, встретившихся во второй."""
    one, two = first.scored_items, second.scored_items
    if not one:
        return 0.0, 0.0
    templates = {item.template_id for item in two}
    instances = {(item.template_id, item.key) for item in two}
    return (
        sum(item.template_id in templates for item in one) / len(one),
        sum((item.template_id, item.key) in instances for item in one) / len(one),
    )


def random_pairs(attempts: list[Attempt], samples: int, seed: int) -> list[tuple[Attempt, Attempt]]:
    """Пары попыток разных кандидатов одной специализации и грейда — «попытка знакомого»."""
    groups: dict[tuple[str, str], list[Attempt]] = defaultdict(list)
    for attempt in attempts:
        groups[(attempt.spec, attempt.grade)].append(attempt)
    keys = sorted(key for key, group in groups.items() if len(group) >= 2)
    rng = random.Random(f"pairs:{seed}")
    pairs = []
    for _ in range(samples if keys else 0):
        group = groups[rng.choice(keys)]
        pairs.append(tuple(rng.sample(group, 2)))
    return pairs


def variant_diversity(env: Environment, renders: int, leaked: int) -> list[dict]:
    """Сколько разных экземпляров даёт шаблон и с какой вероятностью новый экземпляр есть в утечке."""
    rows = []
    for template in sorted(env.bank.templates.values(), key=lambda t: t.id):
        if template.kind == "open_approach" or template.status != "active":
            continue
        fresh = [instance_key(render(template, seed)) for seed in range(renders)]
        dump = {instance_key(render(template, renders + seed)) for seed in range(leaked)}
        rows.append(
            {
                "template_id": template.id,
                "distinct": len(set(fresh)),
                "hit_rate": sum(key in dump for key in fresh) / renders,
            }
        )
    return rows


def _fixed_form(spec: str, grade: str, env: Environment, seed: int) -> list[tuple[str, str]]:
    """Базовая линия — фиксированный тест: одна форма (шаблоны и экземпляры) для всех кандидатов.

    Форма — оценённые задания попытки движка для кандидата ровно на пороге грейда.
    """
    anchor = Person(
        pid=-1, spec=spec, module="", theta=env.blueprints.cut(grade), true_grade=grade, declared=grade
    )
    modules = {t.stack_module for t in env.bank.for_spec(spec) if t.stack_module and t.status == "active"}
    anchor.module = sorted(modules)[0] if modules else ""
    attempt = run_attempt(anchor, grade, attempt_seed("fixed", spec, seed), env, {})
    return [(item.template_id, item.key) for item in attempt.scored_items]


def scenario(
    people: list[Person],
    env: Environment,
    exposure: Exposure,
    config: dict,
) -> dict:
    """Кандидаты ниже целевого грейда сдают тест на него честно и со слитыми 30% ключей."""
    cfg = config["leak"]
    blueprints = env.blueprints
    grade = cfg["target_grade"]
    cut = blueprints.cut(grade)
    lower = blueprints.cut(blueprints.previous_grade(grade))
    pool = [p for p in people if lower <= p.theta < cut]
    rng = random.Random(f"leak:{config['seed']}")
    cheaters = rng.sample(pool, min(cfg["cheaters"], len(pool)))

    leaked_templates: dict[str, set[str]] = {}
    leaked_instances: dict[str, set[str]] = {}
    forms: dict[str, list[tuple[str, str]]] = {}
    form_leaks: dict[str, set[tuple[str, str]]] = {}
    for spec in sorted({p.spec for p in cheaters}):
        active = sorted(
            t.id for t in env.bank.for_spec(spec) if t.status == "active" and t.kind != "open_approach"
        )
        chosen = set(rng.sample(active, round(len(active) * cfg["share"])))
        leaked_templates[spec] = chosen
        for template_id in chosen:
            template = env.bank.templates[template_id]
            leaked_instances[template_id] = {
                instance_key(render(template, 10_000_000 + seed)) for seed in range(cfg["leaked_instances"])
            }
        forms[spec] = _fixed_form(spec, grade, env, config["seed"])
        form_leaks[spec] = set(rng.sample(forms[spec], round(len(forms[spec]) * cfg["share"])))

    results: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for person in cheaters:
        rates = exposure.rates(person.spec)
        seed = attempt_seed("leak", person.pid)
        by_template = leaked_templates[person.spec]

        def template_known(template_id: str, key: str, chosen: set[str] = by_template) -> bool:
            return template_id in chosen

        def instance_known(template_id: str, key: str) -> bool:
            return key in leaked_instances.get(template_id, ())

        for name, known in (
            ("adaptive_honest", None),
            ("adaptive_leak_template", template_known),
            ("adaptive_leak_instance", instance_known),
        ):
            attempt = run_attempt(person, grade, seed, env, rates, known)
            results[name].append((attempt.theta, person.theta))
        for name, leaks in (("fixed_honest", set()), ("fixed_leak", form_leaks[person.spec])):
            theta_hat = _fixed_attempt(person, forms[person.spec], leaks, env, seed)
            results[name].append((theta_hat, person.theta))

    summary = {}
    for name, pairs in results.items():
        summary[name] = {
            "n": len(pairs),
            "pass_rate": sum(theta_hat >= cut for theta_hat, _ in pairs) / len(pairs),
            "inflation": sum(theta_hat - theta for theta_hat, theta in pairs) / len(pairs),
        }
    return {
        "grade": grade,
        "share": cfg["share"],
        "leaked_instances": cfg["leaked_instances"],
        "scenarios": summary,
        "form_size": {spec: len(form) for spec, form in forms.items()},
    }


def _fixed_attempt(
    person: Person, form: list[tuple[str, str]], leaks: set[tuple[str, str]], env: Environment, seed: int
) -> float:
    rng = random.Random(f"fixed-answers:{seed}")
    responses = []
    for template_id, key in form:
        template = env.bank.templates[template_id]
        correct = (template_id, key) in leaks or rng.random() < p_correct(person, template, key, env)
        responses.append(ItemResponse(template.irt.a, template.irt.b, template.guessing, float(correct)))
    return eap(responses)[0]
