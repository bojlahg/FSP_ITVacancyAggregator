"""Прохождение теста продуктовым движком без БД: тот же Planner, рендер и EAP, что и в API (§12.1).

Повторяет подход backend/seed/generate.py (Seeder.simulate): ответ — бросок по 3PL от θ кандидата.
"""

import hashlib
import random
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from app.modules.testing.engine.bank import Bank, Blueprints
from app.modules.testing.engine.irt import probability
from app.modules.testing.engine.model import Instance, Template
from app.modules.testing.engine.render import render
from app.modules.testing.engine.session import STAGE_EXTRA, Answered, AttemptConfig, Planner, Summary
from validation.population import Person

Known = Callable[[str, str], bool]


@dataclass(frozen=True)
class Item:
    template_id: str
    stage: int
    scored: bool
    score: float | None
    key: str


@dataclass
class Attempt:
    spec: str
    grade: str
    seed: int
    summary: Summary
    items: list[Item]

    @property
    def theta(self) -> float:
        return self.summary.theta

    @property
    def se(self) -> float:
        return self.summary.se

    @property
    def decision(self) -> str:
        return self.summary.result

    @property
    def scored_items(self) -> list[Item]:
        return [item for item in self.items if item.scored and item.score is not None]

    @property
    def extra_items(self) -> int:
        return sum(1 for item in self.items if item.stage == STAGE_EXTRA)


@dataclass
class Path:
    """Калибровка по §6.3: тест на заявленный грейд → вниз при провале → вверх при уверенном проходе."""

    attempts: list[Attempt]
    category: str | None


@dataclass
class Environment:
    bank: Bank
    blueprints: Blueprints
    instance_sd: float
    mode: str = "full"
    upgrade_accept: float = 1.0
    b_error: dict[str, float] = field(default_factory=dict)
    planner_cls: type[Planner] = Planner


class Exposure:
    """Доля попыток специализации, в которых показан шаблон — вход контроля экспозиции Planner'а."""

    def __init__(self) -> None:
        self.counts: dict[str, Counter] = defaultdict(Counter)
        self.attempts: Counter = Counter()

    def rates(self, spec: str) -> dict[str, float]:
        total = max(self.attempts[spec], 1)
        return {template_id: count / total for template_id, count in self.counts[spec].items()}

    def record(self, attempt: Attempt) -> None:
        self.attempts[attempt.spec] += 1
        self.counts[attempt.spec].update({item.template_id for item in attempt.items})


def instance_key(instance: Instance) -> str:
    """Содержимое экземпляра без учёта порядка вариантов: совпадение ключа = ответ из утечки подходит."""
    options = "|".join(sorted(option.text for option in instance.options))
    raw = "\x1f".join([instance.template_id, instance.stem, instance.code or "", options])
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=10).hexdigest()


def instance_shift(template_id: str, key: str) -> float:
    """Стандартизованное отклонение сложности экземпляра: свойство содержимого, а не попытки."""
    return random.Random(f"instance:{template_id}:{key}").gauss(0.0, 1.0)


def p_correct(person: Person, template: Template, key: str, env: Environment) -> float:
    theta = person.theta + person.topic_shift.get(template.topic, 0.0)
    b = (
        template.irt.b
        + env.b_error.get(template.id, 0.0)
        + env.instance_sd * instance_shift(template.id, key)
    )
    return float(probability(theta, template.irt.a, b, template.guessing))


def run_attempt(
    person: Person,
    grade: str,
    seed: int,
    env: Environment,
    rates: dict[str, float],
    known: Known | None = None,
) -> Attempt:
    config = AttemptConfig(person.spec, grade, seed, env.mode, person.modules)
    planner = env.planner_cls(config, env.bank, env.blueprints, rates)
    rng = random.Random(f"answers:{seed}")
    history: list[Answered] = []
    items: list[Item] = []
    while (next_item := planner.next_item(history)) is not None:
        template = next_item.template
        if template.kind == "open_approach":
            score, key = None, ""
        else:
            key = instance_key(render(template, next_item.instance_seed))
            leaked = known is not None and known(template.id, key)
            score = 1.0 if leaked or rng.random() < p_correct(person, template, key, env) else 0.0
        history.append(Answered(template.id, next_item.stage, next_item.scored, score))
        items.append(Item(template.id, next_item.stage, next_item.scored, score, key))
    return Attempt(person.spec, grade, seed, planner.summarize(history), items)


def attempt_seed(*parts: object) -> int:
    return random.Random(":".join(str(part) for part in parts)).getrandbits(31)


def run_path(
    person: Person, env: Environment, exposure: Exposure | None, label: str, frozen: Exposure | None = None
) -> Path:
    """exposure — накапливаемая статистика показов; frozen — неизменяемая (для сценариев «что если»)."""
    blueprints = env.blueprints
    source = exposure or frozen
    attempts: list[Attempt] = []
    grade: str | None = person.declared
    tried: set[str] = set()
    category: str | None = None

    def take(target: str) -> Attempt:
        rates = source.rates(person.spec) if source else {}
        attempt = run_attempt(person, target, attempt_seed(label, person.pid, len(attempts)), env, rates)
        if exposure is not None:
            exposure.record(attempt)
        attempts.append(attempt)
        return attempt

    while grade and grade not in tried:
        tried.add(grade)
        attempt = take(grade)
        if attempt.decision != "fail":
            category = grade
            break
        grade = blueprints.previous_grade(grade)

    accept = random.Random(f"upgrade:{label}:{person.pid}").random() < env.upgrade_accept
    if category and attempts[-1].decision == "confident_pass" and accept:
        higher = blueprints.next_grade(category)
        if higher and take(higher).decision != "fail":
            category = higher
    return Path(attempts, category)


def planner_with_rule(low_k: float, high_k: float) -> type[Planner]:
    """Planner с другим правилом «пройден уверенно»: θ̂ − low_k·SE ≥ cut_G и θ̂ ≥ cut_{G+1} − high_k·SE."""

    class WhatIfPlanner(Planner):
        def decide(self, theta: float, se: float) -> str:
            grade = self.config.grade_target
            cut = self.cut(grade)
            if theta < cut:
                return "fail"
            higher = self.blueprints.next_grade(grade)
            if theta - low_k * se >= cut and (higher is None or theta >= self.cut(higher) - high_k * se):
                return "confident_pass"
            return "pass"

    return WhatIfPlanner
