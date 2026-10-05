"""Клиент LLM для извлечения структуры из текста (§9.2 / T08).

LLM только разбирает текст: результат всегда проверяется по справочникам вызывающим кодом,
score и решения о выдаче LLM не принимает. Любая ошибка провайдера → None, вызывающий
продолжает со словарным разбором.

Yandex AI Studio платный, поэтому вызов защищён: при app_env=test сеть не вызывается никогда,
одинаковые запросы берутся из дискового кэша, суточные лимиты вызовов и токенов и часовой лимит
на пользователя хранятся в llm_state_dir. Выключатель — LLM_PROVIDER=none (по умолчанию).
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

YANDEX_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
TIMEOUT_SECONDS = 20.0
CACHE_MAX_ENTRIES = 500
# Грубая оценка входных токенов до вызова, чтобы не превысить суточный лимит
CHARS_PER_TOKEN_ESTIMATE = 3
HOUR_SECONDS = 3600

BUDGET_FILE = "budget.json"
CACHE_FILE = "cache.json"

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_lock = asyncio.Lock()
_user_calls: dict[int, deque[float]] = defaultdict(deque)


async def post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    """Транспорт вынесен отдельно, чтобы тесты подменяли его без сети."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Первый JSON-объект из ответа модели: без ```-ограждений и текста вокруг."""
    candidates = [match.group(1) for match in _FENCE.finditer(text)] + [text]
    decoder = json.JSONDecoder()
    for chunk in candidates:
        start = chunk.find("{")
        while start != -1:
            try:
                value, _ = decoder.raw_decode(chunk, start)
            except json.JSONDecodeError:
                start = chunk.find("{", start + 1)
                continue
            if isinstance(value, dict):
                return value
            start = chunk.find("{", start + 1)
    return None


def is_enabled() -> bool:
    settings = get_settings()
    if settings.app_env == "test":
        return False
    if settings.llm_provider == "yandex":
        return bool(settings.yandex_api_key and settings.yandex_folder_id)
    return False


def _state_dir() -> Path:
    return Path(get_settings().llm_state_dir)


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _read_json(name: str) -> dict[str, Any]:
    path = _state_dir() / name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("LLM state file %s is unreadable, starting it over", path)
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(name: str, data: dict[str, Any]) -> None:
    directory = _state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f"{name}.tmp"
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, directory / name)


def _budget() -> dict[str, Any]:
    data = _read_json(BUDGET_FILE)
    if data.get("day") != _today():
        return {"day": _today(), "calls": 0, "tokens": 0}
    return {"day": data["day"], "calls": int(data.get("calls", 0)), "tokens": int(data.get("tokens", 0))}


def llm_status() -> dict[str, Any]:
    """Состояние LLM для /health: включён ли, расход за сегодня (UTC) и лимиты."""
    settings = get_settings()
    budget = _budget()
    return {
        "enabled": is_enabled(),
        "provider": settings.llm_provider,
        "day": budget["day"],
        "calls_today": budget["calls"],
        "tokens_today": budget["tokens"],
        "limits": {
            "daily_calls": settings.llm_daily_call_limit,
            "daily_tokens": settings.llm_daily_token_limit,
            "user_hourly_calls": settings.llm_user_hourly_limit,
            "max_input_chars": settings.llm_max_input_chars,
            "max_output_tokens": settings.llm_max_output_tokens,
        },
    }


def _cache_key(system: str, user: str) -> str:
    model = get_settings().yandex_model
    return hashlib.sha256(f"{model}\n{system}\n{user}".encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    entry = _read_json(CACHE_FILE).get(key)
    return entry.get("text") if isinstance(entry, dict) else None


def _cache_put(key: str, text: str) -> None:
    cache = _read_json(CACHE_FILE)
    cache[key] = {"text": text, "at": time.time()}
    if len(cache) > CACHE_MAX_ENTRIES:
        oldest = sorted(cache, key=lambda item: cache[item].get("at", 0))
        for stale in oldest[: len(cache) - CACHE_MAX_ENTRIES]:
            del cache[stale]
    _write_json(CACHE_FILE, cache)


def _user_allowed(user_id: int | None, now: float) -> bool:
    if user_id is None:
        return True
    calls = _user_calls[user_id]
    while calls and now - calls[0] >= HOUR_SECONDS:
        calls.popleft()
    return len(calls) < get_settings().llm_user_hourly_limit


def _reserve(estimate: int) -> bool:
    """Списывает вызов из суточного бюджета заранее: параллельные запросы не превысят лимит."""
    settings = get_settings()
    budget = _budget()
    if (
        budget["calls"] + 1 > settings.llm_daily_call_limit
        or budget["tokens"] + estimate > settings.llm_daily_token_limit
    ):
        return False
    budget["calls"] += 1
    _write_json(BUDGET_FILE, budget)
    return True


def _record_tokens(tokens: int) -> None:
    budget = _budget()
    budget["tokens"] += tokens
    _write_json(BUDGET_FILE, budget)


def _usage_tokens(data: dict[str, Any]) -> int:
    usage = data.get("result", {}).get("usage", {}) or {}
    if usage.get("totalTokens") is not None:
        return int(usage["totalTokens"])
    return int(usage.get("inputTextTokens", 0) or 0) + int(usage.get("completionTokens", 0) or 0)


async def _yandex_call(system: str, user: str) -> tuple[str, int]:
    settings = get_settings()
    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0,
            "maxTokens": str(settings.llm_max_output_tokens),
        },
        "messages": [{"role": "system", "text": system}, {"role": "user", "text": user}],
    }
    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "x-folder-id": settings.yandex_folder_id,
    }
    data = await post_json(YANDEX_COMPLETION_URL, headers, body)
    return data["result"]["alternatives"][0]["message"]["text"], _usage_tokens(data)


async def complete_json(
    system: str, user: str, schema_hint: str, user_id: int | None = None
) -> dict[str, Any] | None:
    """Ответ модели как JSON-объект или None: LLM выключен, бюджет исчерпан, ошибка или не JSON."""
    if not is_enabled():
        return None
    settings = get_settings()
    prompt = f"{system}\n\nОтветь только JSON-объектом по схеме:\n{schema_hint}"
    text_in = user[: settings.llm_max_input_chars]
    key = _cache_key(prompt, text_in)
    estimate = (len(prompt) + len(text_in)) // CHARS_PER_TOKEN_ESTIMATE + settings.llm_max_output_tokens

    async with _lock:
        try:
            cached = _cache_get(key)
            if cached is not None:
                return extract_json_object(cached)
            now = time.time()
            if not _user_allowed(user_id, now):
                log.warning("llm budget exhausted: hourly limit for user %s", user_id)
                return None
            if not _reserve(estimate):
                log.warning("llm budget exhausted: daily limit reached")
                return None
        except OSError:
            # Без учёта расхода звать платный API нельзя
            log.warning("llm budget state is not writable, call refused", exc_info=True)
            return None
        if user_id is not None:
            _user_calls[user_id].append(now)

    started = time.monotonic()
    try:
        answer, tokens = await _yandex_call(prompt, text_in)
    except Exception:
        log.warning("LLM request failed", exc_info=True)
        return None
    duration = time.monotonic() - started
    log.info("llm call: tokens=%s duration=%.2fs user=%s", tokens, duration, user_id)

    async with _lock:
        try:
            _record_tokens(tokens)
            _cache_put(key, answer)
        except OSError:
            log.warning("llm state write failed", exc_info=True)

    parsed = extract_json_object(answer)
    if parsed is None:
        log.warning("LLM answer is not a JSON object: %.200s", answer)
    return parsed
