"""Двухэтапный адаптивный тест (MST, §10.3): выбор следующего задания, оценка и решение о грейде.

Функции чистые: состояние попытки — это история ответов; одинаковые входы дают одинаковый выбор.
"""

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.modules.testing.engine.bank import GRADE_ORDER, Bank, Blueprints
from app.modules.testing.engine.irt import ItemResponse, eap
from app.modules.testing.engine.model import Template

STAGE_PILOT = 0
STAGE_ONE = 1
STAGE_TWO = 2
STAGE_EXTRA = 3
STAGE_OPEN = 4


@dataclass(frozen=True)
class AttemptConfig:
    specialization: str
    grade_target: str
    seed: int
    mode: str = "full"
    stack_modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Answered:
    template_id: str
    stage: int
    scored: bool
    score: float | None


@dataclass(frozen=True)
class NextItem:
    template: Template
    stage: int
    scored: bool
    instance_seed: int


@dataclass
class Summary:
    theta: float
    se: float
    result: str
    topic_scores: dict[str, dict] = field(default_factory=dict)
    skill_scores: dict[str, dict] = field(default_factory=dict)
    verified_skills: list[str] = field(default_factory=list)


def split_quotas(topics: dict[str, int], total: int) -> dict[str, int]:
    """Пропорциональное деление квот тем на этап методом наибольшего остатка (детерминированно)."""
    weight = sum(topics.values())
    raw = {topic: count * total / weight for topic, count in topics.items()}
    quotas = {topic: math.floor(value) for topic, value in raw.items()}
    remainder = total - sum(quotas.values())
    for topic in sorted(raw, key=lambda t: (raw[t] - quotas[t], topics[t], t), reverse=True)[:remainder]:
        quotas[topic] += 1
    return quotas


class Planner:
    def __init__(self, config: AttemptConfig, bank: Bank, blueprints: Blueprints, exposure: dict[str, float]):
        self.config = config
        self.blueprints = blueprints
        self.mode = blueprints.modes[config.mode]
        self.exposure = exposure
        self.pool = [
            t
            for t in bank.for_spec(config.specialization)
            if t.stack_module is None or t.stack_module in config.stack_modules
        ]
        self.templates = {t.id: t for t in bank.for_spec(config.specialization)}
        self.topics = self._available_topics()
        total = self.mode.stage1_items + self.mode.stage2_items
        self.stage_quotas = {
            STAGE_ONE: split_quotas(split_quotas(self.topics, total), self.mode.stage1_items),
        }
        full = split_quotas(self.topics, total)
        self.stage_quotas[STAGE_TWO] = {
            topic: full[topic] - self.stage_quotas[STAGE_ONE].get(topic, 0) for topic in full
        }
        rng = random.Random(f"pilot:{config.seed}")
        main_positions = range(1, max(2, total))
        self.pilot_positions = set(
            rng.sample(main_positions, min(self.mode.pilot_slots, len(main_positions)))
        )

    def _available_topics(self) -> dict[str, int]:
        """Квоты тем; если для темы нет шаблонов (например, стек без модулей) — её квота уходит другим."""
        topics = dict(self.blueprints.specializations[self.config.specialization].topics)
        scorable = {t.topic for t in self.pool if t.status == "active" and t.kind != "open_approach"}
        missing = {topic: count for topic, count in topics.items() if topic not in scorable}
        for topic in missing:
            topics.pop(topic)
        if not topics:
            raise ValueError(f"нет активных шаблонов для {self.config.specialization}")
        for _ in range(sum(missing.values())):
            topics[max(topics, key=lambda t: (topics[t], t))] += 1
        return topics

    def cut(self, grade: str) -> float:
        return self.blueprints.cut(grade)

    def estimate(self, history: list[Answered], stages: set[int] | None = None) -> tuple[float, float]:
        responses = []
        for answer in history:
            if not answer.scored or answer.score is None or (stages and answer.stage not in stages):
                continue
            template = self.templates[answer.template_id]
            responses.append(ItemResponse(template.irt.a, template.irt.b, template.guessing, answer.score))
        return eap(responses)

    def stage_two_target(self, history: list[Answered]) -> float:
        grade = self.config.grade_target
        theta, _ = self.estimate(history, {STAGE_ONE})
        split = self.blueprints.scale.stage_split
        if theta >= self.cut(grade) + split:
            higher = self.blueprints.next_grade(grade)
            return self.cut(higher) if higher else self.cut(grade) + 1.0
        if theta < self.cut(grade) - split:
            lower = self.blueprints.previous_grade(grade)
            return (self.cut(lower) + self.cut(grade)) / 2 if lower else self.cut(grade) - 1.0
        return self.cut(grade)

    def next_item(self, history: list[Answered]) -> NextItem | None:
        position = len(history)
        used = {answer.template_id for answer in history}
        rng = random.Random(f"next:{self.config.seed}:{position}")
        instance_seed = rng.getrandbits(31)
        counts = Counter(answer.stage for answer in history if answer.scored)

        if position in self.pilot_positions:
            pilots = [
                t for t in self.pool if t.status == "pilot" and t.id not in used and t.kind != "open_approach"
            ]
            if pilots:
                return NextItem(
                    rng.choice(sorted(pilots, key=lambda t: t.id)), STAGE_PILOT, False, instance_seed
                )

        last_topic = self.templates[history[-1].template_id].topic if history else None
        grade = self.config.grade_target
        for stage, size in ((STAGE_ONE, self.mode.stage1_items), (STAGE_TWO, self.mode.stage2_items)):
            if counts[stage] < size:
                target = self.cut(grade) if stage == STAGE_ONE else self.stage_two_target(history)
                done = Counter(
                    self.templates[a.template_id].topic for a in history if a.scored and a.stage == stage
                )
                deficit = {t: q - done[t] for t, q in self.stage_quotas[stage].items() if q - done[t] > 0}
                template = self._pick(deficit, target, used, last_topic, rng)
                # Шаблоны темы кончились — добираем из любой темы, чтобы длина теста не страдала
                template = template or self._pick(
                    dict.fromkeys(self.topics, 1), target, used, last_topic, rng
                )
                if template:
                    return NextItem(template, stage, True, instance_seed)

        theta, se = self.estimate(history)
        if counts[STAGE_EXTRA] < self.mode.extra_items_max and abs(theta - self.cut(grade)) < se:
            asked = Counter(self.templates[a.template_id].topic for a in history if a.scored)
            fewest = {topic: 1 + max(asked.values(), default=0) - asked[topic] for topic in self.topics}
            template = self._pick(fewest, self.cut(grade), used, last_topic, rng)
            if template:
                return NextItem(template, STAGE_EXTRA, True, instance_seed)

        open_from = GRADE_ORDER.index(self.blueprints.open_approach_from_grade)
        if GRADE_ORDER.index(grade) >= open_from and not any(a.stage == STAGE_OPEN for a in history):
            open_items = [
                t
                for t in self.pool
                if t.kind == "open_approach" and t.status == "active" and t.id not in used
            ]
            if open_items:
                ranked = sorted(open_items, key=lambda t: (abs(t.irt.b - self.cut(grade)), t.id))[:3]
                return NextItem(rng.choice(ranked), STAGE_OPEN, False, instance_seed)
        return None

    def _pick(
        self,
        deficit: dict[str, int],
        target: float,
        used: set[str],
        last_topic: str | None,
        rng: random.Random,
    ) -> Template | None:
        if not deficit:
            return None
        topics = sorted(deficit, key=lambda t: (-deficit[t], t))
        if len(topics) > 1 and topics[0] == last_topic:
            topics = topics[1:] + topics[:1]  # темы не повторяются подряд, если есть выбор
        for topic in topics:
            candidates = [
                t
                for t in self.pool
                if t.topic == topic
                and t.status == "active"
                and t.kind != "open_approach"
                and t.id not in used
            ]
            if not candidates:
                continue
            capped = [
                t
                for t in candidates
                if self.exposure.get(t.id, 0.0) <= self.blueprints.selection.exposure_cap
            ]
            candidates = sorted(capped or candidates, key=lambda t: t.id)
            window = self.blueprints.selection.window
            near = [t for t in candidates if abs(t.irt.b - target) <= window]
            while not near:
                window += 0.4
                near = [t for t in candidates if abs(t.irt.b - target) <= window]
            # Ближе к цели и реже показанные — вероятнее (контроль экспозиции §10.3)
            weights = [
                math.exp(-(((t.irt.b - target) / window) ** 2)) / (1.0 + 10.0 * self.exposure.get(t.id, 0.0))
                for t in near
            ]
            return rng.choices(near, weights=weights, k=1)[0]
        return None

    def decide(self, theta: float, se: float) -> str:
        """§10.4: не пройден / пройден / уверенно (тогда предлагается грейд выше)."""
        grade = self.config.grade_target
        cut = self.cut(grade)
        if theta < cut:
            return "fail"
        higher = self.blueprints.next_grade(grade)
        if theta - se >= cut and (higher is None or theta >= self.cut(higher) - se):
            return "confident_pass"
        return "pass"

    def summarize(self, history: list[Answered]) -> Summary:
        theta, se = self.estimate(history)
        topics: dict[str, list[float]] = defaultdict(list)
        skills: dict[str, list[float]] = defaultdict(list)
        for answer in history:
            if not answer.scored or answer.score is None:
                continue
            template = self.templates[answer.template_id]
            topics[template.topic].append(answer.score)
            for skill in template.skills:
                skills[skill].append(answer.score)
        rule = self.blueprints.verify_skill
        verified = sorted(
            skill
            for skill, scores in skills.items()
            if len(scores) >= rule.min_items and sum(scores) / len(scores) >= rule.min_share
        )
        return Summary(
            theta=theta,
            se=se,
            result=self.decide(theta, se),
            topic_scores={t: {"score": sum(s) / len(s), "items": len(s)} for t, s in topics.items()},
            skill_scores={k: {"correct": sum(s), "items": len(s)} for k, s in skills.items()},
            verified_skills=verified,
        )
