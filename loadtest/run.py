"""Нагрузочный тест ITScout (п. 3.5 ТЗ): десятки одновременных пользователей на основных операциях.

Замкнутая модель: N виртуальных пользователей, каждый в цикле делает запрос и «думает» think-time секунд.
Только GET-запросы и демо-вход — данные не меняются, тест можно направить на любой стенд с DEMO_MODE=true.
См. docs/performance.md.
"""

import argparse
import asyncio
import json
import math
import random
import statistics
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

API = "/api/v1"
# /auth/* ограничен 20 запросами в минуту на IP+путь (app/core/ratelimit.py): держим запас
LOGIN_LIMIT_PER_MINUTE = 18
# access-токен живёт 15 минут: перевыпускаем пул заранее
TOKEN_MAX_AGE_SECONDS = 12 * 60

EMPLOYER_ACTIONS = {
    "recommendations": 30,
    "talent_search": 25,
    "candidate_card": 25,
    "salary_coverage": 10,
    "needs_list": 10,
}
CANDIDATE_ACTIONS = {
    "candidate_me": 40,
    "candidate_invitations": 30,
    "vacancies_match": 30,
}
ENDPOINT_PATHS = {
    "recommendations": "GET /needs/{id}/recommendations",
    "talent_search": "GET /talent/search",
    "candidate_card": "GET /talent/candidates/{id}?need_id=",
    "salary_coverage": "GET /needs/{id}/salary-coverage",
    "needs_list": "GET /needs",
    "candidate_me": "GET /candidates/me",
    "candidate_invitations": "GET /candidates/me/invitations",
    "vacancies_match": "GET /vacancies?match=true",
}
GRADES = ["intern", "junior", "middle", "senior"]
SORTS = ["vps", "percentile", "fresh"]


class TokenPool:
    """Пул access-токенов демо-аккаунтов: вход один раз, дальше токены переиспользуются."""

    def __init__(self, client: httpx.AsyncClient, size: int) -> None:
        self.client = client
        self.size = size
        self.tokens: dict[str, list[str]] = {}
        self.issued_at = 0.0
        self._logins: deque[float] = deque()

    async def _login(self, persona: str) -> str:
        while True:
            now = time.monotonic()
            while self._logins and now - self._logins[0] > 60:
                self._logins.popleft()
            if len(self._logins) >= LOGIN_LIMIT_PER_MINUTE:
                await asyncio.sleep(60 - (now - self._logins[0]) + 0.5)
                continue
            self._logins.append(now)
            response = await self.client.post(f"{API}/auth/demo-login", json={"persona": persona})
            if response.status_code == 429:
                await asyncio.sleep(float(response.headers.get("retry-after", 10)))
                continue
            response.raise_for_status()
            return response.json()["access_token"]

    async def ensure(self) -> None:
        if self.tokens and time.monotonic() - self.issued_at < TOKEN_MAX_AGE_SECONDS:
            return
        self.tokens = {p: [await self._login(p) for _ in range(self.size)] for p in ("employer", "candidate")}
        self.issued_at = time.monotonic()

    def get(self, persona: str, index: int) -> str:
        tokens = self.tokens[persona]
        return tokens[index % len(tokens)]


@dataclass
class Fixtures:
    need_ids: list[int]
    candidates_by_need: dict[int, list[int]]
    specializations: list[str]


@dataclass
class Recorder:
    latencies: dict[str, list[float]] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    error_samples: list[str] = field(default_factory=list)

    def add(self, label: str, seconds: float, error: str | None) -> None:
        self.latencies.setdefault(label, []).append(seconds)
        if error is not None:
            self.errors[label] = self.errors.get(label, 0) + 1
            if len(self.error_samples) < 10:
                self.error_samples.append(f"{label}: {error}")


async def load_fixtures(client: httpx.AsyncClient, pool: TokenPool) -> Fixtures:
    headers = {"Authorization": f"Bearer {pool.get('employer', 0)}"}
    needs = (await client.get(f"{API}/needs", headers=headers)).raise_for_status().json()
    need_ids = [n["id"] for n in needs if n.get("status") == "active"] or [n["id"] for n in needs]
    if not need_ids:
        raise SystemExit("У демо-работодателя нет потребностей: выполните reseed")
    candidates_by_need: dict[int, list[int]] = {}
    for need_id in need_ids:
        recs = await client.get(f"{API}/needs/{need_id}/recommendations", headers=headers)
        items = recs.raise_for_status().json()["candidates"]
        candidates_by_need[need_id] = [c["candidate"]["id"] for c in items]
    catalog = await client.get(f"{API}/catalog/specializations", headers=headers)
    specializations = [s["slug"] for s in catalog.raise_for_status().json()]
    return Fixtures(need_ids, candidates_by_need, specializations)


def build_request(action: str, rng: random.Random, fx: Fixtures) -> tuple[str, dict[str, str | int]]:
    need_id = rng.choice(fx.need_ids)
    match action:
        case "recommendations":
            return f"{API}/needs/{need_id}/recommendations", {}
        case "salary_coverage":
            return f"{API}/needs/{need_id}/salary-coverage", {}
        case "needs_list":
            return f"{API}/needs", {}
        case "candidate_card":
            pool = fx.candidates_by_need.get(need_id) or [
                c for ids in fx.candidates_by_need.values() for c in ids
            ]
            return f"{API}/talent/candidates/{rng.choice(pool)}", {"need_id": need_id}
        case "talent_search":
            params: dict[str, str | int] = {"sort": rng.choice(SORTS), "limit": 30}
            if rng.random() < 0.7:
                params["specialization"] = rng.choice(fx.specializations)
            if rng.random() < 0.5:
                params["grade"] = rng.choice(GRADES)
            return f"{API}/talent/search", params
        case "candidate_me":
            return f"{API}/candidates/me", {}
        case "candidate_invitations":
            return f"{API}/candidates/me/invitations", {}
        case "vacancies_match":
            return f"{API}/vacancies", {"match": "true"}
    raise ValueError(action)


async def virtual_user(
    index: int,
    persona: str,
    client: httpx.AsyncClient,
    pool: TokenPool,
    fx: Fixtures,
    rec: Recorder,
    deadline: float,
    args: argparse.Namespace,
) -> None:
    rng = random.Random(args.seed * 1000 + index)
    actions = EMPLOYER_ACTIONS if persona == "employer" else CANDIDATE_ACTIONS
    names, weights = list(actions), list(actions.values())
    headers = {"Authorization": f"Bearer {pool.get(persona, index)}"}
    # Разносим старт, чтобы пользователи не приходили одной волной
    await asyncio.sleep(rng.uniform(0, args.think_max))
    while time.monotonic() < deadline:
        action = rng.choices(names, weights)[0]
        url, params = build_request(action, rng, fx)
        started = time.perf_counter()
        error: str | None = None
        try:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code >= 400:
                error = f"HTTP {response.status_code} {response.text[:120]}"
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"
        rec.add(action, time.perf_counter() - started, error)
        think = rng.uniform(args.think_min, args.think_max)
        await asyncio.sleep(min(think, max(0.0, deadline - time.monotonic())))


def percentile(sorted_values: list[float], q: float) -> float:
    # метод ближайшего ранга: наименьшее значение, не меньше которого q доля измерений
    return sorted_values[max(1, math.ceil(q * len(sorted_values))) - 1]


def summarize(values: list[float], errors: int, elapsed: float) -> dict[str, float | int]:
    ordered = sorted(values)
    ms = 1000.0
    return {
        "count": len(ordered),
        "errors": errors,
        "error_rate": round(errors / len(ordered), 4) if ordered else 0.0,
        "rps": round(len(ordered) / elapsed, 2),
        "mean_ms": round(statistics.fmean(ordered) * ms, 1) if ordered else 0.0,
        "p50_ms": round(percentile(ordered, 0.50) * ms, 1) if ordered else 0.0,
        "p95_ms": round(percentile(ordered, 0.95) * ms, 1) if ordered else 0.0,
        "p99_ms": round(percentile(ordered, 0.99) * ms, 1) if ordered else 0.0,
        "max_ms": round(ordered[-1] * ms, 1) if ordered else 0.0,
    }


async def run_level(
    users: int, client: httpx.AsyncClient, pool: TokenPool, fx: Fixtures, args: argparse.Namespace
) -> dict:
    await pool.ensure()
    rec = Recorder()
    employers = round(users * args.employer_share)
    started = time.monotonic()
    deadline = started + args.duration
    await asyncio.gather(
        *(
            virtual_user(i, persona, client, pool, fx, rec, deadline, args)
            for i, persona in enumerate(["employer"] * employers + ["candidate"] * (users - employers))
        )
    )
    elapsed = time.monotonic() - started
    all_values = [v for values in rec.latencies.values() for v in values]
    return {
        "users": users,
        "employers": employers,
        "candidates": users - employers,
        "elapsed_s": round(elapsed, 1),
        "total": summarize(all_values, sum(rec.errors.values()), elapsed),
        "endpoints": {
            label: summarize(rec.latencies[label], rec.errors.get(label, 0), elapsed)
            for label in ENDPOINT_PATHS
            if label in rec.latencies
        },
        "error_samples": rec.error_samples,
    }


def print_level(level: dict) -> None:
    print(
        f"\n=== {level['users']} пользователей "
        f"({level['employers']} работодателей, {level['candidates']} кандидатов), {level['elapsed_s']} с ==="
    )
    header = f"{'endpoint':<40}{'n':>7}{'err':>6}{'rps':>8}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}"
    print(header)
    print("-" * len(header))
    rows = [(ENDPOINT_PATHS[k], v) for k, v in level["endpoints"].items()] + [("ВСЕГО", level["total"])]
    for name, s in rows:
        print(
            f"{name:<40}{s['count']:>7}{s['errors']:>6}{s['rps']:>8}"
            f"{s['p50_ms']:>9}{s['p95_ms']:>9}{s['p99_ms']:>9}{s['max_ms']:>9}"
        )
    for sample in level["error_samples"]:
        print(f"  ! {sample}")


def markdown(levels: list[dict]) -> str:
    lines = [
        "| Операция | Польз. | Запросов | RPS | p50, мс | p95, мс | p99, мс | Ошибки |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, path in [*ENDPOINT_PATHS.items(), ("__total__", "**Всего**")]:
        for level in levels:
            s = level["total"] if key == "__total__" else level["endpoints"].get(key)
            if s is None:
                continue
            name = path if key == "__total__" else f"`{path}`"
            lines.append(
                f"| {name} | {level['users']} | {s['count']} | {s['rps']} | {s['p50_ms']:.0f} | "
                f"{s['p95_ms']:.0f} | {s['p99_ms']:.0f} | {s['error_rate']:.1%} |"
            )
    return "\n".join(lines)


async def main(args: argparse.Namespace) -> int:
    connections = max(args.users) + 10
    limits = httpx.Limits(max_connections=connections, max_keepalive_connections=connections)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout, limits=limits) as client:
        health = (await client.get(f"{API}/health")).raise_for_status().json()
        print(f"{args.base_url}: {health}")
        pool = TokenPool(client, args.pool)
        await pool.ensure()
        fx = await load_fixtures(client, pool)
        print(f"потребностей: {len(fx.need_ids)}, специализаций: {len(fx.specializations)}")
        levels = []
        for users in args.users:
            level = await run_level(users, client, pool, fx, args)
            print_level(level)
            levels.append(level)
            await asyncio.sleep(args.pause)

    print("\n" + markdown(levels))
    if args.out:
        report = {
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "base_url": args.base_url,
            "settings": {k: v for k, v in vars(args).items() if k != "out"},
            "levels": levels,
        }
        await asyncio.to_thread(
            Path(args.out).write_text, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nотчёт: {args.out}")
    worst = max(level["total"]["error_rate"] for level in levels)
    return 1 if worst > args.max_error_rate else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000", help="стенд с DEMO_MODE=true")
    parser.add_argument("--users", default="10,30,50", type=lambda s: [int(x) for x in s.split(",")])
    parser.add_argument("--duration", type=float, default=60, help="длительность уровня, с")
    parser.add_argument("--think-min", type=float, default=1.0, help="мин. пауза между запросами, с")
    parser.add_argument("--think-max", type=float, default=3.0, help="макс. пауза между запросами, с")
    parser.add_argument("--employer-share", type=float, default=0.7, help="доля работодателей")
    parser.add_argument("--pool", type=int, default=5, help="токенов на роль (демо-вход ограничен 20/мин)")
    parser.add_argument("--pause", type=float, default=5, help="пауза между уровнями, с")
    parser.add_argument("--timeout", type=float, default=30, help="таймаут запроса, с")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-error-rate", type=float, default=0.01, help="выше — код выхода 1")
    parser.add_argument("--out", help="сохранить результаты в JSON")
    args = parser.parse_args()
    if args.think_max < args.think_min:
        parser.error("--think-max меньше --think-min")
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
