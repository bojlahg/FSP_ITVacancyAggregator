"""Генератор демо-данных (§17): кандидаты проходят тест через настоящий движок — категории получаются механикой.

Запуск: `python -m seed.generate` (в контейнере backend) или POST /api/v1/admin/reseed. Детерминирован по SEED.
"""

import asyncio
import json
import math
import random
import secrets
import sys
import zlib
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TeamAccount, get_settings
from app.core.db import SessionFactory
from app.core.enums import (
    ApplicationStatus,
    AssignmentStatus,
    AttemptPurpose,
    AttemptResult,
    AttemptStatus,
    ChallengeAttemptStatus,
    ChallengeStatus,
    ConsentKind,
    DeclineReason,
    FspLinkMethod,
    Grade,
    GradedBy,
    InvitationStatus,
    NeedStatus,
    Role,
    SearchStatus,
    SkillSource,
    TaskKind,
    TemplateStatus,
    UnlockSource,
    WorkFormat,
)
from app.core.security import hash_password
from app.models import (
    Application,
    Base,
    Candidate,
    CandidateCategory,
    CandidateSkill,
    Consent,
    ContactUnlock,
    Employer,
    EmployerTask,
    HiringNeed,
    Invitation,
    NeedShortlist,
    SurveyResponse,
    TaskAssignment,
    TemplateStat,
    TestAttempt,
    TestAttemptItem,
    User,
)
from app.modules.categories import service as categories_service
from app.modules.challenges import service as challenges_service
from app.modules.challenges.models import Challenge, ChallengeAttempt
from app.modules.challenges.schemas import ChallengeQuestion
from app.modules.fsp import service as fsp_service
from app.modules.fsp.evidence import RankRecord, ResultRecord
from app.modules.matching import service as matching_service
from app.modules.tasks.service import pool_key
from app.modules.testing.engine.bank import GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.irt import probability
from app.modules.testing.engine.render import render
from app.modules.testing.engine.scoring import score
from app.modules.testing.engine.session import Answered, AttemptConfig, Planner
from seed import data

SEED = 2026
INSTANCE_NOISE = 0.15  # разброс сложности экземпляра вокруг b шаблона (§12.1)
THETA_BY_GRADE = {"below": -2.4, "intern": -1.3, "junior": -0.3, "middle": 0.7, "senior": 1.75}
GRADE_SHARE = [("below", 5), ("intern", 10), ("junior", 30), ("middle", 33), ("senior", 22)]
DEMO_DOMAIN = "demo.itscout.ru"
TEAM_INDEX = 9000  # индексы кандидатов команды — вне диапазона демо-кандидатов
FREE_FSP_ID = "FSP-2026-7781"  # участник реестра без профиля на платформе — для живой демонстрации привязки
DEMO_TASK_TEMPLATE = "be.db.composite_index"
DEMO_CHALLENGE_QUESTIONS = [
    {
        "kind": "single_choice",
        "text": "Клиент повторил POST /payments с тем же Idempotency-Key после таймаута. Что должен вернуть сервис?",
        "options": [
            {"text": "Тот же ответ, что и на первый запрос, без повторного списания", "correct": True},
            {"text": "Новый платёж с новым id"},
            {"text": "500 — повторы запрещены"},
            {"text": "409 Conflict в любом случае"},
        ],
    },
    {
        "kind": "multi_choice",
        "text": "Что защищает от двойного списания при повторе запроса?",
        "options": [
            {"text": "Уникальный индекс по ключу идемпотентности", "correct": True},
            {"text": "Сохранение результата первого запроса и возврат его при повторе", "correct": True},
            {"text": "Увеличение таймаута на клиенте"},
            {"text": "Подробное логирование запросов"},
        ],
    },
    {
        "kind": "numeric",
        "text": (
            "Сервис обрабатывает 200 запросов в секунду, среднее время ответа — 50 мс. Сколько запросов "
            "в среднем находится в обработке одновременно?"
        ),
        "number": 10,
    },
    {
        "kind": "single_choice",
        "text": "Какой уровень изоляции транзакций в PostgreSQL используется по умолчанию?",
        "options": [
            {"text": "Read committed", "correct": True},
            {"text": "Repeatable read"},
            {"text": "Serializable"},
            {"text": "Read uncommitted"},
        ],
    },
    {
        "kind": "open_approach",
        "text": "Партнёр временно недоступен. Как бы вы организовали повторную доставку webhook-уведомлений?",
        "rubric": [
            "Очередь и повторы с экспоненциальной задержкой",
            "Идемпотентность на стороне получателя",
            "Ограничение попыток и очередь недоставленных",
        ],
    },
]
DEMO_CHALLENGE_OPEN_ANSWERS = [
    "Кладу событие в очередь, повторяю с экспоненциальной задержкой и джиттером, после N попыток — в DLQ "
    "с алертом. В событии id, чтобы партнёр дедуплицировал повторы.",
    "Outbox-таблица в той же транзакции, воркер шлёт и ретраит с backoff. Партнёр обрабатывает по event_id "
    "идемпотентно, после суток недоставки — ручной разбор.",
    "Повторять каждые пять минут, пока не получится.",
]
DEMO_APPROACH_RUBRIC = [
    "Клиент передаёт ключ идемпотентности",
    "Результат первой операции сохраняется вместе с ключом",
    "Уникальное ограничение в БД защищает от гонки",
    "Повтор с тем же ключом возвращает сохранённый ответ",
]
DEMO_APPROACH_ANSWERS = [
    (
        "Клиент шлёт Idempotency-Key, на сервере таблица ключей с уникальным индексом: вставляем ключ в той же транзакции, что и платёж, а при повторе отдаём сохранённый ответ.",
        5,
    ),
    (
        "Проверяем, был ли уже платёж с такой суммой и счётом за последние 5 минут, и если был — не проводим второй раз.",
        2,
    ),
    (
        "Передаём ключ идемпотентности в заголовке и кладём его в Redis с TTL; если ключ уже есть — возвращаем 409.",
        None,
    ),
]
E2E_CANDIDATE_EMAIL = "e2e-candidate@itscout.ru"  # служебный кандидат e2e (§18), не герой показа


def weighted(rng: random.Random, pairs: list[tuple]) -> object:
    values, weights = zip(*pairs, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


PRESERVED_TABLES = {"expert_pairs", "expert_labels", "angoff_ratings", "angoff_hofstee"}


_CYRILLIC = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        [
            "a",
            "b",
            "v",
            "g",
            "d",
            "e",
            "e",
            "zh",
            "z",
            "i",
            "y",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "r",
            "s",
            "t",
            "u",
            "f",
            "kh",
            "ts",
            "ch",
            "sh",
            "sch",
            "",
            "y",
            "",
            "e",
            "yu",
            "ya",
        ],
        strict=True,
    )
)


def _latin(name: str) -> str:
    """Telegram-ник только латиницей: имена в демо-данных русские."""
    return "".join(_CYRILLIC.get(char, char) for char in name.lower())


class Seeder:
    def __init__(self, db: AsyncSession, seed: int = SEED):
        self.db = db
        self.seed = seed
        self.rng = random.Random(seed)
        self.now = datetime.now(UTC).replace(microsecond=0)
        self.today = self.now.date()
        self.bank = get_bank()
        self.blueprints = get_blueprints()
        # Общий пароль сид-аккаунтов не живёт в коде: репозиторий публичный (docs/deploy.md §5.5)
        self.password_hash = hash_password(get_settings().demo_seed_password or secrets.token_urlsafe(18))
        self.exposures: Counter = Counter()
        self.correct: Counter = Counter()
        self.attempts_by_spec: Counter = Counter()
        self.competitions: list[dict] = []
        self.registry = {"participants": [], "competitions": [], "results": [], "ranks": []}
        self.fsp_counter = 1000
        self.candidates: list[dict] = []
        self.verified: dict[int, list[str]] = {}

    # ---------- общее ----------

    async def reset(self) -> None:
        # Экспертная разметка не зависит от демо-данных (снимки пар) и переживает reseed
        tables = ", ".join(
            f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name not in PRESERVED_TABLES
        )
        await self.db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    def user(self, email: str, role: Role, created_at: datetime) -> User:
        user = User(
            email=email,
            password_hash=self.password_hash,
            role=role,
            email_verified_at=created_at,
            created_at=created_at,
            seeded=True,
        )
        self.db.add(user)
        return user

    def build_admin(self) -> None:
        settings = get_settings()
        if settings.demo_admin_password:
            admin = self.user(settings.demo_admin_email, Role.admin, self.now)
            admin.password_hash = hash_password(settings.demo_admin_password)

    def consents(self, user: User, kinds: list[ConsentKind], at: datetime) -> None:
        for kind in kinds:
            self.db.add(
                Consent(
                    user_id=user.id, kind=kind, policy_version=get_settings().policy_version, granted_at=at
                )
            )

    # ---------- ФСП ----------

    def build_competitions(self) -> None:
        counter = 0
        for discipline, templates in data.COMPETITION_TEMPLATES.items():
            for year in range(2022, 2027):
                for level, name in templates:
                    if self.rng.random() < 0.45:
                        continue
                    counter += 1
                    month = self.rng.randint(1, 9 if year == 2026 else 12)
                    low, high = data.PARTICIPANTS[level]
                    competition = {
                        "id": f"C-{counter:03d}",
                        "name": name.format(year=year, region=self.rng.choice(data.REGIONS)),
                        "discipline": discipline,
                        "level": level,
                        "format": "individual" if discipline == "algorithmic" else "team",
                        "held_on": date(year, month, self.rng.randint(1, 28)).isoformat(),
                        "participants_count": self.rng.randint(low, high),
                        "organizer": "Федерация спортивного программирования",
                    }
                    self.competitions.append(competition)
        self.registry["competitions"] = self.competitions

    def fsp_history(
        self, spec: str, theta: float, forced: list[tuple] | None = None
    ) -> tuple[str, list, list]:
        """Результаты коррелируют с θ: сильнее кандидат — выше перцентиль места (§12.1)."""
        self.fsp_counter += 1
        fsp_id = f"FSP-{self.today.year}-{self.fsp_counter:04d}"
        results, ranks = [], []
        options = data.FSP_DISCIPLINES[spec]
        plan = forced or [
            (*self.rng.choice(options), None)
            for _ in range(self.rng.choices([1, 2, 3, 4, 5], [30, 30, 20, 12, 8])[0])
        ]
        used = set()
        for discipline, role, wanted_pct, *level in plan:
            pool = [
                c
                for c in self.competitions
                if c["discipline"] == discipline
                and c["id"] not in used
                and (not level or c["level"] == level[0])
            ]
            if not pool:
                continue
            competition = self.rng.choice(pool)
            used.add(competition["id"])
            pct = (
                wanted_pct
                if wanted_pct is not None
                else 1 / (1 + math.exp(-(1.3 * theta + self.rng.gauss(0, 0.8))))
            )
            participants = competition["participants_count"]
            place = max(1, min(participants, round(1 + (1 - pct) * (participants - 1))))
            prize = "winner" if place == 1 else "prize" if place <= 3 else "participant"
            results.append({"competition": competition, "place": place, "team_role": role, "prize": prize})
            if discipline == "algorithmic" and pct > 0.85 and self.rng.random() < 0.5:
                rank = "КМС" if pct > 0.97 else "I" if pct > 0.93 else "II" if pct > 0.9 else "III"
                ranks.append({"discipline": discipline, "rank": rank, "awarded_at": competition["held_on"]})
        return fsp_id, results, ranks

    def register_participant(self, fsp_id: str, full_name: str, results: list, ranks: list) -> None:
        self.registry["participants"].append(
            {"fsp_id": fsp_id, "full_name": full_name, "region": self.rng.choice(data.REGIONS)}
        )
        for index, result in enumerate(results):
            self.registry["results"].append(
                {
                    "id": f"{fsp_id}-R{index}",
                    "fsp_id": fsp_id,
                    "competition_id": result["competition"]["id"],
                    "team_role": result["team_role"],
                    "place": result["place"],
                    "prize": result["prize"],
                }
            )
        for rank in ranks:
            self.registry["ranks"].append({"fsp_id": fsp_id, **rank})

    @staticmethod
    def records(results: list, ranks: list) -> tuple[list[ResultRecord], list[RankRecord]]:
        return (
            [
                ResultRecord(
                    competition_id=r["competition"]["id"],
                    competition_name=r["competition"]["name"],
                    discipline=r["competition"]["discipline"],
                    level=r["competition"]["level"],
                    format=r["competition"]["format"],
                    held_on=date.fromisoformat(r["competition"]["held_on"]),
                    place=r["place"],
                    participants=r["competition"]["participants_count"],
                    team_role=r["team_role"],
                    prize=r["prize"],
                )
                for r in results
            ],
            [RankRecord(r["discipline"], r["rank"], date.fromisoformat(r["awarded_at"])) for r in ranks],
        )

    def write_registry(self) -> None:
        path = Path(get_settings().fsp_data_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.registry, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)

    # ---------- тест через движок ----------

    def exposure(self, spec: str) -> dict[str, float]:
        total = max(self.attempts_by_spec[spec], 1)
        return {template_id: count / total for template_id, count in self.exposures.items()}

    def simulate(self, spec: str, grade: str, theta: float, modules: list[str], started_at: datetime) -> dict:
        """Прохождение теста движком без записи в БД: ответы по 3PL от θ кандидата (§12.1)."""
        rng = self.rng
        config = AttemptConfig(spec, grade, rng.getrandbits(31), "full", tuple(modules))
        planner = Planner(config, self.bank, self.blueprints, self.exposure(spec))
        history: list[Answered] = []
        items: list[dict] = []
        moment = started_at
        open_scores = []
        while (next_item := planner.next_item(history)) is not None:
            template = next_item.template
            instance = render(template, next_item.instance_seed)
            elapsed = timedelta(seconds=rng.randint(15, min(template.time_limit_sec, 140)))
            if instance.kind == "open_approach":
                response = {"text": rng.choice(data.OPEN_ANSWERS)}
                item_score = None
                # Без LLM оценка подхода в синтетике коррелирует с θ; помечено в flags
                open_scores.append(1 / (1 + math.exp(-(theta - template.irt.b) * 1.5)))
            else:
                b = template.irt.b + rng.gauss(0, INSTANCE_NOISE)
                correct = rng.random() < float(probability(theta, template.irt.a, b, template.guessing))
                response = self.response_for(instance, correct)
                item_score = score(instance.kind, instance.key, response)
            items.append(
                {
                    "template": template,
                    "instance": instance,
                    "seed": next_item.instance_seed,
                    "stage": next_item.stage,
                    "scored": next_item.scored,
                    "response": response,
                    "score": item_score,
                    "shown_at": moment,
                    "elapsed": elapsed,
                }
            )
            moment += elapsed
            history.append(Answered(template.id, next_item.stage, next_item.scored, item_score))
        return {
            "config": config,
            "items": items,
            "summary": planner.summarize(history),
            "open_scores": open_scores,
            "finished_at": moment,
            "history": history,
        }

    async def take_test(
        self,
        candidate: Candidate,
        spec: str,
        grade: str,
        purpose: AttemptPurpose,
        theta: float,
        stack_modules: list[str],
        started_at: datetime,
        wanted: set[str] | None = None,
    ) -> TestAttempt:
        run = self.simulate(spec, grade, theta, stack_modules, started_at)
        # Герои демо: перебрасываем попытку, пока результат не совпадёт со сценарием показа
        for _ in range(40):
            if wanted is None or run["summary"].result in wanted:
                break
            run = self.simulate(spec, grade, theta, stack_modules, started_at)
        self.attempts_by_spec[spec] += 1
        summary = run["summary"]
        attempt = TestAttempt(
            candidate_id=candidate.id,
            specialization=spec,
            grade_target=Grade(grade),
            purpose=purpose,
            blueprint={"mode": "full", "stack_modules": stack_modules},
            seed=run["config"].seed,
            status=AttemptStatus.completed,
            flags={},
            started_at=started_at,
            theta=round(summary.theta, 4),
            se=round(summary.se, 4),
            result=AttemptResult(summary.result),
            topic_scores=summary.topic_scores,
            skill_scores=summary.skill_scores,
            finished_at=run["finished_at"],
            stage=max((a.stage for a in run["history"]), default=1),
        )
        if run["open_scores"]:
            attempt.approach_score = round(sum(run["open_scores"]) / len(run["open_scores"]), 3)
            attempt.flags = {"approach_graded_by": "seed"}
        self.db.add(attempt)
        await self.db.flush()
        for position, item in enumerate(run["items"]):
            template, instance = item["template"], item["instance"]
            self.exposures[template.id] += 1
            self.correct[template.id] += int(item["score"] or 0)
            self.db.add(
                TestAttemptItem(
                    attempt_id=attempt.id,
                    template_id=template.id,
                    template_version=template.version,
                    instance_seed=item["seed"],
                    stage=item["stage"],
                    position=position,
                    scored=item["scored"],
                    payload=instance.public_payload(),
                    answer_key=instance.key,
                    response=item["response"],
                    score=item["score"],
                    shown_at=item["shown_at"],
                    answered_at=item["shown_at"] + item["elapsed"],
                    time_ms=int(item["elapsed"].total_seconds() * 1000),
                )
            )
        self.verified[attempt.id] = summary.verified_skills
        return attempt

    def response_for(self, instance, correct: bool) -> dict:
        key = instance.key
        if instance.kind in {"single_choice", "multi_choice", "code_output"}:
            if correct:
                return {"choice_ids": key["choice_ids"]}
            wrong = [option.id for option in instance.options if option.id not in key["choice_ids"]]
            return {"choice_ids": [self.rng.choice(wrong)] if wrong else []}
        if instance.kind == "ordering":
            if correct:
                return {"order": key["order"]}
            order = key["order"][:]
            order[0], order[1] = order[1], order[0]
            return {"order": order}
        if instance.kind == "numeric":
            return {"number": key["number"] if correct else key["number"] + max(1, abs(key["number"]) * 0.3)}
        return {}

    def assign_category(self, candidate: Candidate, attempt: TestAttempt, at: datetime) -> CandidateCategory:
        category = CandidateCategory(
            candidate_id=candidate.id,
            specialization=attempt.specialization,
            grade=attempt.grade_target,
            theta=attempt.theta,
            attempt_id=attempt.id,
            assigned_at=at,
            valid_until=at + timedelta(days=get_settings().category_valid_days),
            is_current=True,
        )
        self.db.add(category)
        return category

    async def calibrate(
        self,
        candidate: Candidate,
        spec: str,
        declared: str,
        theta: float,
        modules: list[str],
        start: datetime,
        allow_upgrade: bool = True,
        wanted: set[str] | None = None,
    ) -> CandidateCategory | None:
        """Путь кандидата по §6.3: тест на заявленный грейд → вниз при провале → один раз вверх при уверенном."""
        grade, moment, category, last = declared, start, None, None
        tried: set[str] = set()
        while grade and grade not in tried:
            tried.add(grade)
            attempt = await self.take_test(
                candidate, spec, grade, AttemptPurpose.calibration, theta, modules, moment, wanted
            )
            moment = attempt.finished_at + timedelta(minutes=self.rng.randint(5, 90))
            last = attempt
            if attempt.result != AttemptResult.fail:
                category = self.assign_category(candidate, attempt, attempt.finished_at)
                break
            grade = self.blueprints.previous_grade(grade)
        if (
            allow_upgrade
            and category is not None
            and last.result == AttemptResult.confident_pass
            and self.rng.random() < 0.6
        ):
            higher = self.blueprints.next_grade(category.grade.value)
            if higher:
                attempt = await self.take_test(
                    candidate, spec, higher, AttemptPurpose.upgrade, theta, modules, moment
                )
                last = attempt
                if attempt.result != AttemptResult.fail:
                    category.is_current = False
                    category = self.assign_category(candidate, attempt, attempt.finished_at)
        if category is not None:
            for skill in self.verified.get(category.attempt_id, []):
                self.db.add(
                    CandidateSkill(
                        candidate_id=candidate.id,
                        skill_id=skill,
                        source=SkillSource.test,
                        evidence={"attempt_id": category.attempt_id},
                        updated_at=category.assigned_at,
                    )
                )
        return category

    # ---------- кандидаты ----------

    def person(self) -> tuple[str, str, bool]:
        female = self.rng.random() < 0.38
        first = self.rng.choice(data.FEMALE_FIRST if female else data.MALE_FIRST)
        last = self.rng.choice(data.LAST_NAMES)[1 if female else 0]
        return first, last, female

    async def candidate(
        self,
        index: int,
        spec: str,
        true_grade: str,
        *,
        email: str | None = None,
        name: tuple[str, str] | None = None,
        theta: float | None = None,
        city: str | None = None,
        module: str | None = None,
        fsp_plan: list[tuple] | None = None,
        with_fsp: bool | None = None,
        declared: str | None = None,
        salary: tuple[int, int] | None = None,
        hero: bool = False,
        skills: list[str] | None = None,
        formats: list[str] | None = None,
        wanted: set[str] | None = None,
    ) -> dict:
        rng = self.rng
        first, last = name or self.person()[:2]
        theta = theta if theta is not None else rng.gauss(THETA_BY_GRADE[true_grade], 0.35)
        stacks = data.SPEC_STACKS[spec]
        module = module if module is not None else rng.choice(list(stacks))
        skills = skills or rng.sample(stacks[module], k=min(len(stacks[module]), rng.randint(4, 8)))
        if declared is None:
            ladder = GRADE_ORDER
            base = ladder.index(true_grade) if true_grade in ladder else 0
            shift = rng.choices([1, 0, -1], [20, 70, 10])[0]
            declared = ladder[max(0, min(len(ladder) - 1, base + shift))]
        low, high = data.EXPERIENCE[true_grade]
        experience = round(rng.uniform(low, high), 1)
        salary_grade = declared if true_grade == "below" else true_grade
        s_low, s_high = data.SALARY[salary_grade]
        factor = data.SPEC_SALARY_FACTOR[spec]
        salary_min = salary[0] if salary else int(round(rng.uniform(s_low, s_high) * factor, -1)) * 1000
        salary_max = salary[1] if salary else salary_min + rng.choice([30, 50, 70]) * 1000
        created = self.now - timedelta(days=rng.randint(10, 160), hours=rng.randint(0, 23))

        user = self.user(email or f"candidate{index:04d}@{DEMO_DOMAIN}", Role.candidate, created)
        await self.db.flush()
        publication = email is not None or rng.random() < 0.92
        self.consents(
            user,
            [ConsentKind.pd_processing] + ([ConsentKind.profile_publication] if publication else []),
            created,
        )
        formats = formats or rng.choice(
            [
                ["remote"],
                ["hybrid"],
                ["office"],
                ["remote", "hybrid"],
                ["hybrid", "office"],
                ["remote", "hybrid", "office"],
            ]
        )
        candidate = Candidate(
            user_id=user.id,
            first_name=first,
            last_name=last,
            phone=f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
            telegram=f"@{_latin(first).lower()[:6]}_{index}",
            contact_email=user.email,
            city=city or weighted(rng, data.CITIES),
            relocation=rng.random() < 0.25,
            work_formats=[WorkFormat(f).value for f in formats],
            salary_min=salary_min,
            salary_max=salary_max,
            experience_years=experience,
            specialization=spec,
            roles=["developer"] if spec != "qa" else ["qa_engineer"],
            industries_exp=rng.sample(
                ["fintech", "ecommerce", "telecom", "govtech", "edtech", "medtech", "industry"], 2
            ),
            industries_pref=rng.sample(
                ["fintech", "ecommerce", "telecom", "govtech", "edtech", "medtech", "gamedev"], 2
            ),
            soft_skills=rng.sample(
                ["communication", "teamwork", "responsibility", "self_organization", "mentoring"], 2
            ),
            about=None,
            privacy={},
            hidden_employer_ids=[],
            search_status=weighted(
                rng, [(SearchStatus.active, 40), (SearchStatus.open, 50), (SearchStatus.hidden, 10)]
            )
            if email is None
            else SearchStatus.active,
            created_at=created,
            updated_at=created,
        )
        self.db.add(candidate)
        await self.db.flush()
        for skill_id in skills:
            self.db.add(
                CandidateSkill(
                    candidate_id=candidate.id,
                    skill_id=skill_id,
                    source=SkillSource.declared,
                    updated_at=created,
                )
            )
        answers = {
            "daily_work": [data.SPEC_DAILY[spec]],
            "favorite_tasks": [data.SPEC_FAVORITE[spec]],
            "main_language": data.MODULE_LANGUAGE[module],
            "stack": skills,
            "experience_years": experience,
            "work_formats": formats,
            "relocation": "yes" if candidate.relocation else "no",
            "salary": {"from": salary_min, "to": salary_max},
            "city": candidate.city,
        }
        self.db.add(
            SurveyResponse(
                candidate_id=candidate.id,
                answers=answers,
                spec_scores={spec: 1.0},
                specialization=spec,
                created_at=created,
            )
        )
        modules = [module] if module else []

        category = await self.calibrate(
            candidate,
            spec,
            declared,
            theta,
            modules,
            created + timedelta(minutes=20),
            allow_upgrade=not hero,
            wanted=wanted or ({"pass", "confident_pass"} if hero else None),
        )

        has_fsp = with_fsp if with_fsp is not None else rng.random() < data.FSP_PROBABILITY[spec]
        if has_fsp:
            fsp_id, results, ranks = self.fsp_history(spec, theta, fsp_plan)
            self.register_participant(fsp_id, f"{first} {last}", results, ranks)
            if results or ranks:
                candidate.fsp_id = fsp_id
                # Большинство — через ФСП ID (mock Keycloak), каждый седьмой — номером вручную: в демо видна
                # пометка «владение не подтверждено», и такой ФСП в score не идёт (§9.3). Демо-кандидат Анна —
                # вручную: в сценарии она повышает привязку до подтверждённой входом через ФСП ID
                if hero:
                    manual = email == get_settings().demo_candidate_email
                else:
                    manual = zlib.crc32(fsp_id.encode()) % 7 == 0
                candidate.fsp_link_method = FspLinkMethod.manual if manual else FspLinkMethod.oidc
                candidate.fsp_linked_at = created + timedelta(days=1)
                self.consents(user, [ConsentKind.fsp_import], created + timedelta(days=1))
                await self.db.flush()
                await fsp_service.store_evidence(
                    self.db, candidate, *self.records(results, ranks), today=self.today
                )
        record = {"candidate": candidate, "user": user, "spec": spec, "theta": theta, "category": category}
        self.candidates.append(record)
        return record

    async def build_candidates(self) -> None:
        index = 0
        # Герои демо (§17): заранее известные сильные профили
        self.heroes = {
            "anna": await self.candidate(
                0,
                "backend",
                "middle",
                email=get_settings().demo_candidate_email,
                name=("Анна", "Ковалёва"),
                theta=0.95,
                city="Москва",
                module="python",
                declared="middle",
                salary=(240000, 290000),
                formats=["hybrid", "office"],
                wanted={"confident_pass"},
                hero=True,
                skills=["python", "fastapi", "postgresql", "kafka", "docker", "redis", "sql", "git"],
                with_fsp=True,
                fsp_plan=[
                    ("product", "backend", 0.996, "national"),
                    ("algorithmic", None, 0.98, "national"),
                    ("product", "lead", 0.9, "interregional"),
                ],
            ),
            "ilya": await self.candidate(
                1,
                "frontend",
                "junior",
                email=f"ilya.smirnov@{DEMO_DOMAIN}",
                name=("Илья", "Смирнов"),
                hero=True,
                theta=-0.2,
                city="Казань",
                module="react",
                skills=["javascript", "typescript", "react", "redux", "html", "css", "git"],
                declared="junior",
                salary=(110000, 140000),
                with_fsp=False,
            ),
            "maria": await self.candidate(
                2,
                "devops",
                "senior",
                email=f"maria.orlova@{DEMO_DOMAIN}",
                name=("Мария", "Орлова"),
                theta=1.8,
                city="Санкт-Петербург",
                module="",
                declared="senior",
                salary=(380000, 450000),
                hero=True,
                with_fsp=True,
                skills=[
                    "linux",
                    "docker",
                    "kubernetes",
                    "terraform",
                    "prometheus",
                    "grafana",
                    "gitlab_ci",
                    "bash",
                ],
                fsp_plan=[("infosec", None, 0.99, "national"), ("infosec", None, 0.95, "interregional")],
            ),
        }
        index = 3
        for spec, count in data.SPEC_SHARE.items():
            for _ in range(count - (1 if spec in {"backend", "frontend", "devops"} else 0)):
                true_grade = weighted(self.rng, GRADE_SHARE)
                await self.candidate(index, spec, true_grade)
                index += 1
                if index % 50 == 0:
                    await self.db.flush()
        # Участник реестра без профиля на платформе — для демонстрации привязки ФСП ID
        _, results, ranks = self.fsp_history(
            "backend", 1.2, [("algorithmic", None, 0.93), ("product", "backend", 0.9)]
        )
        self.register_participant(FREE_FSP_ID, "Участник для демонстрации", results, ranks)
        await self.build_e2e_candidate(index)

    async def build_e2e_candidate(self, index: int) -> None:
        """Кандидат для e2e (§18): принимает приглашения тестовых работодателей вместо героев показа.

        Своя ветка RNG — данные остальных кандидатов и история взаимодействий не сдвигаются.
        """
        main_rng, self.rng = self.rng, random.Random(f"{self.seed}:e2e")
        try:
            self.e2e_candidate = await self.candidate(
                index,
                "backend",
                "middle",
                email=E2E_CANDIDATE_EMAIL,
                name=("Тест", "Автотестов"),
                theta=THETA_BY_GRADE["middle"],
                city="Казань",
                module="python",
                declared="middle",
                salary=(200000, 240000),
                formats=["remote", "hybrid"],
                skills=["python", "django", "postgresql", "docker", "git"],
                with_fsp=False,
                wanted={"pass"},
            )
        finally:
            self.rng = main_rng
        password = get_settings().e2e_candidate_password
        if password:
            self.e2e_candidate["user"].password_hash = hash_password(password)

    # ---------- команда ----------

    @staticmethod
    def team_email(member: TeamAccount, role: str) -> str:
        if member.email and "@" in member.email:
            local, domain = member.email.split("@", 1)
            return f"{local}+{role}@{domain}".lower()
        return f"{member.name}.{role}@{get_settings().team_accounts_domain}"

    async def build_team(self) -> None:
        """Аккаунты команды из TEAM_ACCOUNTS: у каждого админ, кандидат Backend · Middle и своя компания.

        Своя ветка RNG — демо-данные не зависят от состава команды.
        """
        main_rng = self.rng
        self.team_candidates: list[dict] = []
        try:
            for number, member in enumerate(get_settings().team_accounts):
                self.rng = random.Random(f"{self.seed}:team:{member.name}")
                password = hash_password(member.password)
                admin = self.user(self.team_email(member, "admin"), Role.admin, self.now)
                admin.password_hash = password
                record = await self.candidate(
                    TEAM_INDEX + number,
                    "backend",
                    "middle",
                    email=self.team_email(member, "candidate"),
                    name=(member.name.capitalize(), "Команда"),
                    theta=THETA_BY_GRADE["middle"],
                    module="python",
                    declared="middle",
                    skills=["python", "fastapi", "postgresql", "docker", "git"],
                    with_fsp=False,
                    wanted={"pass"},
                )
                record["user"].password_hash = password
                # Тестовые профили команды не видны демо-компаниям, которые смотрит жюри: только своим компаниям команды
                record["candidate"].hidden_employer_ids = [employer.id for employer in self.employers]
                self.team_candidates.append(record)
                user = self.user(self.team_email(member, "employer"), Role.employer, self.now)
                user.password_hash = password
                await self.db.flush()
                self.consents(user, [ConsentKind.pd_processing], self.now)
                self.db.add(
                    Employer(
                        user_id=user.id,
                        company_name=f"Команда ITScout · {member.name}",
                        industry="fintech",
                        description="Тестовая компания участника команды.",
                        contact_name=member.name.capitalize(),
                        contact_email=user.email,
                        created_at=self.now,
                        updated_at=self.now,
                    )
                )
                await self.db.flush()
        finally:
            self.rng = main_rng

    # ---------- работодатели ----------

    async def build_employers(self) -> None:
        settings = get_settings()
        self.employers = []
        for index, (company, industry, description) in enumerate(data.COMPANIES):
            email = settings.demo_employer_email if index == 0 else f"hr{index:02d}@{DEMO_DOMAIN}"
            created = self.now - timedelta(days=self.rng.randint(20, 120))
            user = self.user(email, Role.employer, created)
            await self.db.flush()
            self.consents(user, [ConsentKind.pd_processing], created)
            slug = f"company{index:02d}"
            employer = Employer(
                user_id=user.id,
                company_name=company,
                industry=industry,
                description=description,
                website=f"https://{slug}.example",
                contact_name=f"{self.person()[0]} — рекрутер",
                contact_email=f"hr@{slug}.example",
                contact_telegram=f"@{slug}_hr",
                created_at=created,
                updated_at=created,
            )
            self.db.add(employer)
            await self.db.flush()
            self.employers.append(employer)

    async def build_needs(self) -> None:
        catalog_needs = [
            (
                0,
                "Backend-разработчик в платёжную команду",
                "backend",
                "middle",
                ["python", "postgresql", "kafka"],
                ["fastapi", "docker"],
                "fintech",
                "hybrid",
                "Москва",
                220000,
                280000,
                True,
            ),
            (
                0,
                "Senior Java-разработчик кредитного конвейера",
                "backend",
                "senior",
                ["java", "spring_boot", "postgresql"],
                ["kafka", "kubernetes"],
                "fintech",
                "remote",
                None,
                330000,
                420000,
                True,
            ),
            (
                0,
                "DevOps-инженер платформы",
                "devops",
                "senior",
                ["kubernetes", "terraform", "prometheus"],
                ["helm", "ansible"],
                "fintech",
                "hybrid",
                "Москва",
                350000,
                450000,
                False,
            ),
            (
                1,
                "Frontend-разработчик витрины маркетплейса",
                "frontend",
                "middle",
                ["react", "typescript"],
                ["nextjs", "redux"],
                "ecommerce",
                "remote",
                None,
                200000,
                260000,
                True,
            ),
            (
                1,
                "QA-инженер (автотесты на Python)",
                "qa",
                "middle",
                ["pytest", "api_testing"],
                ["playwright"],
                "ecommerce",
                "remote",
                None,
                150000,
                210000,
                True,
            ),
            (
                2,
                "Data Scientist: предиктивное обслуживание",
                "data",
                "middle",
                ["python", "pandas", "scikit_learn"],
                ["catboost", "airflow"],
                "industry",
                "hybrid",
                "Екатеринбург",
                220000,
                300000,
                False,
            ),
            (
                3,
                "Go-разработчик сетевых сервисов",
                "backend",
                "middle",
                ["go", "postgresql", "grpc"],
                ["kubernetes"],
                "telecom",
                "remote",
                None,
                230000,
                300000,
                True,
            ),
            (
                4,
                "Junior Frontend (Vue) в медтех",
                "frontend",
                "junior",
                ["vue", "javascript"],
                ["typescript"],
                "medtech",
                "office",
                "Казань",
                90000,
                130000,
                False,
            ),
            (
                5,
                "Backend на Node.js для логистики",
                "backend",
                "middle",
                ["nodejs", "typescript", "postgresql"],
                ["mongodb"],
                "ecommerce",
                "remote",
                None,
                200000,
                260000,
                False,
            ),
            (
                6,
                "ML-инженер антифрода",
                "data",
                "senior",
                ["python", "pytorch", "sql"],
                ["spark", "mlflow"],
                "fintech",
                "remote",
                None,
                350000,
                450000,
                False,
            ),
            (
                7,
                "Junior QA (ручное тестирование)",
                "qa",
                "junior",
                ["test_design", "sql"],
                ["postman"],
                "edtech",
                "remote",
                None,
                70000,
                100000,
                False,
            ),
            (
                9,
                "SRE энергосетей",
                "devops",
                "middle",
                ["linux", "docker", "prometheus"],
                ["kubernetes"],
                "industry",
                "office",
                "Нижний Новгород",
                200000,
                260000,
                False,
            ),
            (
                11,
                "Стажёр backend (Python)",
                "backend",
                "intern",
                ["python", "sql"],
                ["git"],
                "govtech",
                "hybrid",
                "Москва",
                50000,
                70000,
                False,
            ),
        ]
        self.needs = []
        for (
            emp_index,
            title,
            spec,
            grade,
            req,
            opt,
            industry,
            fmt,
            city,
            s_from,
            s_to,
            published,
        ) in catalog_needs:
            created = self.now - timedelta(days=self.rng.randint(1, 30))
            need = HiringNeed(
                employer_id=self.employers[emp_index].id,
                title=title,
                raw_text=None,
                specialization=spec,
                grade=Grade(grade),
                required_skills=req,
                optional_skills=opt,
                industry=industry,
                work_format=WorkFormat(fmt),
                city=city,
                team_description=data.NEED_TEAMS[title],
                salary_from=s_from,
                salary_to=s_to,
                published=published,
                published_at=created if published else None,
                status=NeedStatus.active,
                created_at=created,
            )
            self.db.add(need)
            self.needs.append(need)
        await self.db.flush()

    async def build_interactions(self) -> None:
        """История приглашений и откликов со всеми статусами (§17) — для статистики отказов и репутации."""
        rng = self.rng
        visible = [c for c in self.candidates if c["category"] is not None]
        reasons = [
            (DeclineReason.salary, 40),
            (DeclineReason.stack, 15),
            (DeclineReason.work_format, 15),
            (DeclineReason.company, 10),
            (DeclineReason.not_looking, 15),
            (DeclineReason.other, 5),
        ]
        statuses = [
            (InvitationStatus.accepted, 25),
            (InvitationStatus.declined, 30),
            (InvitationStatus.viewed, 15),
            (InvitationStatus.sent, 20),
            (InvitationStatus.expired, 10),
        ]
        # Герои, служебный e2e-кандидат и профили команды не получают синтетических приглашений и откликов
        heroes = {
            id(hero["candidate"])
            for hero in [*self.heroes.values(), self.e2e_candidate, *self.team_candidates]
        }
        unlocked: set[tuple[int, int]] = set()
        self.interactions: list[tuple[HiringNeed, Invitation | Application]] = []

        def unlock(
            employer_id: int, candidate_id: int, source: UnlockSource, source_id: int, at: datetime
        ) -> None:
            # Первое событие раскрывает контакты; повторное (приглашение + отклик) уже ничего не меняет
            if (employer_id, candidate_id) in unlocked:
                return
            unlocked.add((employer_id, candidate_id))
            self.db.add(
                ContactUnlock(
                    employer_id=employer_id,
                    candidate_id=candidate_id,
                    source=source,
                    source_id=source_id,
                    unlocked_at=at,
                )
            )

        for need in self.needs:
            pool = [
                c for c in visible if c["spec"] == need.specialization and id(c["candidate"]) not in heroes
            ]
            for record in rng.sample(pool, min(len(pool), rng.randint(2, 6))):
                created = self.after(need.created_at, 200)
                status = weighted(rng, statuses)
                invitation = Invitation(
                    employer_id=need.employer_id,
                    candidate_id=record["candidate"].id,
                    need_id=need.id,
                    title=need.title,
                    message="Здравствуйте! Нам понравился ваш профиль — давайте обсудим роль в нашей команде.",
                    salary_from=need.salary_from,
                    salary_to=need.salary_to,
                    contact_method={"name": "Рекрутер", "telegram": "@recruiter_demo"},
                    status=status,
                    created_at=created,
                    expires_at=self.expiry(created, status),
                )
                if status != InvitationStatus.sent:
                    invitation.viewed_at = self.after(created, 30)
                if status in {InvitationStatus.accepted, InvitationStatus.declined}:
                    invitation.responded_at = self.after(invitation.viewed_at, 48)
                if status == InvitationStatus.declined:
                    invitation.decline_reason = weighted(rng, reasons)
                self.db.add(invitation)
                await self.db.flush()
                self.interactions.append((need, invitation))
                if status == InvitationStatus.accepted:
                    unlock(
                        need.employer_id,
                        record["candidate"].id,
                        UnlockSource.invitation,
                        invitation.id,
                        invitation.responded_at,
                    )
        for need in [n for n in self.needs if n.published]:
            pool = [
                c for c in visible if c["spec"] == need.specialization and id(c["candidate"]) not in heroes
            ]
            for record in rng.sample(pool, min(len(pool), rng.randint(1, 3))):
                created = self.after(need.created_at, 100)
                status = weighted(
                    rng,
                    [
                        (ApplicationStatus.sent, 40),
                        (ApplicationStatus.viewed, 30),
                        (ApplicationStatus.accepted, 20),
                        (ApplicationStatus.rejected, 10),
                    ],
                )
                application = Application(
                    need_id=need.id,
                    candidate_id=record["candidate"].id,
                    status=status,
                    created_at=created,
                    cover_note="Интересна ваша команда и стек, готов обсудить детали.",
                )
                if status != ApplicationStatus.sent:
                    application.viewed_at = self.after(created, 24)
                if status in {ApplicationStatus.accepted, ApplicationStatus.rejected}:
                    application.responded_at = self.after(application.viewed_at, 72)
                self.db.add(application)
                await self.db.flush()
                self.interactions.append((need, application))
                unlock(
                    need.employer_id,
                    record["candidate"].id,
                    UnlockSource.application,
                    application.id,
                    created,
                )
        demo_need = self.needs[0]
        for record in [
            c for c in visible if c["spec"] == "backend" and c["category"].grade.value == "middle"
        ][:2]:
            self.db.add(NeedShortlist(need_id=demo_need.id, candidate_id=record["candidate"].id))

    async def build_challenges(self) -> None:
        """Челлендж «Демо Банка» (§11.1) с тремя решившими; герои его не проходили — им покажут живьём."""
        rng = self.rng
        need = self.needs[0]
        published = self.now - timedelta(days=6)
        questions = [ChallengeQuestion.model_validate(q) for q in DEMO_CHALLENGE_QUESTIONS]
        challenge = Challenge(
            employer_id=self.employers[0].id,
            title="Платежи без двойных списаний",
            description=(
                "Ищем backend-разработчиков в платёжную команду. Пять вопросов про идемпотентность, транзакции "
                "и надёжную доставку событий — около семи минут."
            ),
            specialization=need.specialization,
            grade=None,
            skills=["python", "postgresql"],
            time_per_question_sec=90,
            questions_per_attempt=None,
            questions=challenges_service.stored_questions(questions),
            status=ChallengeStatus.published,
            created_at=published - timedelta(days=1),
            published_at=published,
        )
        self.db.add(challenge)
        await self.db.flush()

        heroes = {
            id(hero["candidate"])
            for hero in [*self.heroes.values(), self.e2e_candidate, *self.team_candidates]
        }
        pool = [
            c
            for c in self.candidates
            if c["category"] is not None
            and c["category"].specialization == need.specialization
            and id(c["candidate"]) not in heroes
        ]
        for index, record in enumerate(pool[:3]):
            started = published + timedelta(days=1 + index, hours=rng.randint(9, 18))
            items = []
            for number, question in enumerate(challenge.questions):
                shown = started + timedelta(seconds=90 * number)
                answered = shown + timedelta(seconds=rng.randint(25, 80))
                # Третий решивший ошибается в двух вопросах — список решивших не из одних 100%
                right = not (index == 2 and number in (1, 3))
                option_map = {str(i): option["id"] for i, option in enumerate(question["options"], 1)}
                if question["kind"] == "open_approach":
                    response = {"text": DEMO_CHALLENGE_OPEN_ANSWERS[index]}
                elif question["kind"] == "numeric":
                    response = {"number": question["key"]["number"] + (0 if right else 5)}
                else:
                    wrong = [
                        o["id"] for o in question["options"] if o["id"] not in question["key"]["choice_ids"]
                    ][:1]
                    response = {"choice_ids": question["key"]["choice_ids"] if right else wrong}
                points = (
                    None
                    if question["kind"] == "open_approach"
                    else score(question["kind"], question["key"], response)
                )
                items.append(
                    {
                        "question_id": question["id"],
                        "option_map": option_map,
                        "shown_at": shown.isoformat(),
                        "answered_at": answered.isoformat(),
                        "response": response,
                        "score": points,
                        "late": False,
                    }
                )
            attempt = ChallengeAttempt(
                challenge_id=challenge.id,
                candidate_id=record["candidate"].id,
                status=ChallengeAttemptStatus.in_progress,
                items=items,
                started_at=started,
            )
            challenges_service.finalize(attempt, challenge, items, started + timedelta(minutes=8))
            self.db.add(attempt)
        await self.db.flush()

    async def build_tasks(self) -> None:
        """Регулярные задания «Демо Банка» (§11) с решениями; герои заданий не получают — им предложат живьём."""
        rng = self.rng
        need = self.needs[0]
        bank_employer = self.employers[0]
        created = self.now - timedelta(days=12)
        auto = EmployerTask(
            employer_id=bank_employer.id,
            need_id=need.id,
            specialization=need.specialization,
            grade=need.grade,
            kind=TaskKind.auto,
            template_pool=pool_key(self.bank.templates[DEMO_TASK_TEMPLATE]),
            title="Индекс для ленты платежей",
            rubric=[],
            created_at=created,
        )
        approach = EmployerTask(
            employer_id=bank_employer.id,
            need_id=need.id,
            specialization=need.specialization,
            grade=need.grade,
            kind=TaskKind.approach,
            title="Повторная оплата без двойного списания",
            prompt="Клиент мобильного банка может отправить запрос оплаты дважды (повтор по таймауту). Как сделать так, чтобы деньги списались ровно один раз?",
            rubric=DEMO_APPROACH_RUBRIC,
            created_at=created + timedelta(hours=1),
        )
        self.db.add_all([auto, approach])
        await self.db.flush()

        heroes = {
            id(hero["candidate"])
            for hero in [*self.heroes.values(), self.e2e_candidate, *self.team_candidates]
        }
        pool = [
            c
            for c in self.candidates
            if c["category"] is not None
            and c["category"].specialization == need.specialization
            and c["category"].grade == need.grade
            and id(c["candidate"]) not in heroes
        ]
        template = self.bank.templates[DEMO_TASK_TEMPLATE]
        for index, record in enumerate(pool[:3]):
            offered = created + timedelta(days=1, hours=index * 5)
            instance = render(template, rng.getrandbits(31))
            correct = index != 2
            response = self.response_for(instance, correct)
            assignment = TaskAssignment(
                task_id=auto.id,
                candidate_id=record["candidate"].id,
                template_id=template.id,
                offered_at=offered,
                due_at=offered + timedelta(days=7),
                status=AssignmentStatus.submitted,
                payload=instance.public_payload(),
                answer_key=instance.key,
                response=response,
                submitted_at=offered + timedelta(hours=3),
                score=score(instance.kind, instance.key, response),
                graded_by=GradedBy.auto,
            )
            self.db.add(assignment)
            await self.db.flush()
            if correct:
                for skill in template.skills:
                    self.db.add(
                        CandidateSkill(
                            candidate_id=record["candidate"].id,
                            skill_id=skill,
                            source=SkillSource.task,
                            evidence={
                                "task_id": auto.id,
                                "assignment_id": assignment.id,
                                "template_id": template.id,
                            },
                            updated_at=assignment.submitted_at,
                        )
                    )
        # Ответы на подход: два оценены работодателем (LLM на демо выключен), третий ждёт оценки
        for index, (record, (text_answer, rating)) in enumerate(
            zip(pool[3:6], DEMO_APPROACH_ANSWERS, strict=False)
        ):
            offered = created + timedelta(days=2, hours=index * 7)
            self.db.add(
                TaskAssignment(
                    task_id=approach.id,
                    candidate_id=record["candidate"].id,
                    offered_at=offered,
                    due_at=offered + timedelta(days=7),
                    status=AssignmentStatus.submitted,
                    response={"text": text_answer},
                    submitted_at=offered + timedelta(hours=5),
                    score=(rating - 1) / 4 if rating else None,
                    graded_by=GradedBy.employer if rating else None,
                    employer_rating=rating,
                )
            )
        await self.db.flush()

    def after(self, start: datetime, max_hours: int) -> datetime:
        """Момент через 1..max_hours часов после start, но не позже «сейчас» — даты не уходят в будущее."""
        available = int((self.now - start).total_seconds() // 3600) - 1
        return start + timedelta(hours=self.rng.randint(1, max(1, min(max_hours, available))))

    def expiry(self, created: datetime, status: InvitationStatus) -> datetime:
        expires = created + timedelta(days=get_settings().invitation_ttl_days)
        if status == InvitationStatus.expired:
            return min(expires, self.now - timedelta(hours=1))
        if status in {InvitationStatus.sent, InvitationStatus.viewed}:
            # Активные приглашения демо не должны истечь до показа
            return max(expires, self.now + timedelta(days=7))
        return expires

    async def snapshot_interactions(self) -> None:
        """Снимки «почему вы» тем же расчётом, что и в API, — после того как индекс выдачи построен."""
        for need, item in self.interactions:
            employer_id = item.employer_id if isinstance(item, Invitation) else need.employer_id
            match = await matching_service.snapshot_for(self.db, employer_id, item.candidate_id, need)
            if match is None:
                continue
            explanation = match.explanation.model_dump(mode="json")
            item.match_snapshot = (
                explanation if isinstance(item, Invitation) else {"score": match.score, **explanation}
            )

    # ---------- финал ----------

    async def finalize(self) -> None:
        await self.db.flush()
        for spec, grade in {
            (c.specialization, c.grade) for c in [r["category"] for r in self.candidates] if c is not None
        }:
            await categories_service.recompute_percentiles(self.db, spec, grade)
        await self.db.flush()
        for record in self.candidates:
            await matching_service.refresh_candidate(self.db, record["candidate"].id)
        for template_id, shown in self.exposures.items():
            template = self.bank.templates[template_id]
            self.db.add(
                TemplateStat(
                    template_id=template_id,
                    version=template.version,
                    status=TemplateStatus(template.status),
                    irt_a=template.irt.a,
                    irt_b=template.irt.b,
                    irt_c=template.guessing,
                    exposures=shown,
                    correct=self.correct[template_id],
                )
            )

    async def run(self) -> dict:
        await self.reset()
        self.build_competitions()
        await self.build_candidates()
        await self.build_employers()
        self.build_admin()
        await self.build_team()
        await self.build_needs()
        await self.build_interactions()
        await self.build_tasks()
        await self.build_challenges()
        await self.finalize()
        await self.db.flush()
        await self.snapshot_interactions()
        await self.db.commit()
        self.write_registry()
        categories = Counter(
            f"{r['category'].specialization}:{r['category'].grade.value}"
            for r in self.candidates
            if r["category"]
        )
        return {
            "candidates": len(self.candidates),
            "with_category": sum(1 for r in self.candidates if r["category"]),
            "with_fsp": sum(1 for r in self.candidates if r["candidate"].fsp_id),
            "employers": len(self.employers),
            "needs": len(self.needs),
            "categories": dict(sorted(categories.items())),
        }


async def run_seed(seed: int = SEED) -> dict:
    async with SessionFactory() as db:
        return await Seeder(db, seed).run()


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(json.dumps(asyncio.run(run_seed()), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
