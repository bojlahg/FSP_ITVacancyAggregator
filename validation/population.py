"""Симулированная популяция кандидатов (§12.1): истинные θ, стек, заявленный грейд, ФСП и условия."""

import math
import random
from dataclasses import dataclass, field

from app.modules.testing.engine.bank import GRADE_ORDER, Blueprints
from seed import data


@dataclass
class Person:
    pid: int
    spec: str
    module: str
    theta: float
    true_grade: str | None
    declared: str
    topic_shift: dict[str, float] = field(default_factory=dict)
    true_stack: tuple[str, ...] = ()
    resume_stack: tuple[str, ...] = ()
    has_fsp: bool = False
    fsp_score: float = 0.0
    fresh_days: int = 0
    salary_min: int = 0
    work_formats: tuple[str, ...] = ()
    city: str = ""
    relocation: bool = False

    @property
    def modules(self) -> tuple[str, ...]:
        return (self.module,) if self.module else ()


def true_grade(theta: float, blueprints: Blueprints) -> str | None:
    """Истинный грейд — старший, чей порог не выше θ_true; ниже порога стажёра — без категории."""
    grade = None
    for name in GRADE_ORDER:
        if theta >= blueprints.cut(name):
            grade = name
    return grade


def _weighted(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def _declared(rng: random.Random, grade: str | None, cfg: dict) -> str:
    base = GRADE_ORDER.index(grade) if grade else 0
    roll = rng.random()
    shift = (
        1 if roll < cfg["declared_over"] else -1 if roll < cfg["declared_over"] + cfg["declared_under"] else 0
    )
    return GRADE_ORDER[max(0, min(len(GRADE_ORDER) - 1, base + shift))]


def _stacks(rng: random.Random, spec: str, module: str, cfg: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pool = data.SPEC_STACKS[spec][module]
    low, high = cfg["stack_size"]
    true = rng.sample(pool, k=min(len(pool), rng.randint(low, high)))
    resume = list(true)
    if rng.random() < cfg["resume_padding"]:
        others = sorted({s for m in data.SPEC_STACKS[spec].values() for s in m} - set(true))
        resume += rng.sample(others, k=min(len(others), rng.randint(1, 2)))
    if len(true) > 1 and rng.random() < cfg["resume_omission"]:
        resume.remove(rng.choice(true))
    return tuple(true), tuple(resume)


def build_population(config: dict, blueprints: Blueprints, topics: dict[str, list[str]]) -> list[Person]:
    """topics: специализация → темы blueprint'а (для индивидуальных профилей по темам)."""
    cfg = config["population"]
    rng = random.Random(f"population:{config['seed']}")
    people: list[Person] = []
    for pid in range(cfg["size"]):
        spec = _weighted(rng, cfg["spec_share"])
        component = _weighted(rng, cfg["grade_share"])
        theta = rng.gauss(cfg["theta_mean"][component], cfg["theta_sd"])
        grade = true_grade(theta, blueprints)
        module = rng.choice(sorted(data.SPEC_STACKS[spec]))
        true_stack, resume_stack = _stacks(rng, spec, module, cfg)
        # Отклонения по темам центрированы: профиль меняет форму, но не средний уровень
        shifts = {topic: rng.gauss(0.0, cfg["topic_sd"]) for topic in topics[spec]}
        mean_shift = sum(shifts.values()) / len(shifts)
        salary_grade = grade or "intern"
        s_low, s_high = data.SALARY[salary_grade]
        salary = int(round(rng.uniform(s_low, s_high) * data.SPEC_SALARY_FACTOR[spec], -1)) * 1000
        people.append(
            Person(
                pid=pid,
                spec=spec,
                module=module,
                theta=theta,
                true_grade=grade,
                declared=_declared(rng, grade, cfg),
                topic_shift={topic: value - mean_shift for topic, value in shifts.items()},
                true_stack=true_stack,
                resume_stack=resume_stack,
                fresh_days=rng.randint(*cfg["fresh_days"]),
                salary_min=salary,
                work_formats=tuple(rng.choice(cfg["work_formats"])),
                city=rng.choices([c for c, _ in data.CITIES], weights=[w for _, w in data.CITIES], k=1)[0],
                relocation=rng.random() < cfg["relocation"],
            )
        )
    _assign_fsp(people, cfg["fsp"], rng)
    return people


def _assign_fsp(people: list[Person], cfg: dict, rng: random.Random) -> None:
    """ФСП коррелирует с θ: латентная склонность = θ·w + шум, история есть у верхних share%."""
    if not people:
        return
    latent = [(p.theta * cfg["theta_weight"] + rng.gauss(0.0, 1.0), p.pid) for p in people]
    count = round(len(people) * cfg["share"])
    chosen = {pid for _, pid in sorted(latent, reverse=True)[:count]}
    for person in people:
        if person.pid in chosen:
            score = cfg["score_base"] + cfg["score_slope"] * person.theta + rng.gauss(0.0, cfg["score_sd"])
            person.has_fsp = True
            person.fsp_score = round(min(1.0, max(0.05, score)), 3)


def freshness(days: int, half_life: float) -> float:
    return math.pow(0.5, days / half_life)
