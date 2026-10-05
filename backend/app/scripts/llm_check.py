"""Проверка LLM на стенде: все сценарии продукта через настоящего провайдера.

Запуск в контейнере backend, не включая LLM для пользователей:
    docker compose ... exec -T -e LLM_PROVIDER=yandex backend python -m app.scripts.llm_check
(без SSH — `gh workflow run server-ops.yml -f action=llm-check`).

Кэш и суточный бюджет — во временном каталоге, чтобы проверка шла в сеть, а не в кэш, и не тратила
лимиты пользователей. Печатаются только итоги разбора синтетических текстов: ни ключей, ни ПДн.
Код выхода 1, если хоть один сценарий не прошёл.
"""

import asyncio
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable

import httpx

from app.core import llm
from app.core.config import get_settings

NEED_TEXT = (
    "Ищем Middle Python-разработчика в платёжную команду финтеха. Обязательно: FastAPI, PostgreSQL, "
    "Docker. Будет плюсом: Kafka, Kubernetes. Пишем сервисы платёжного шлюза, нагрузка 3 тыс. RPS. "
    "Формат гибрид, Москва. Вилка 220–260 тыс. ₽ на руки."
)
RESUME_TEXT = """Иван Тестов
Backend-разработчик
Москва, готов к переезду. Telegram: @ivan_test_demo

Опыт работы
2022 — настоящее время, ООО «Пример Софт», Python-разработчик
Разработка REST API на FastAPI, PostgreSQL, Redis, Celery; покрытие тестами pytest.
2020 — 2022, АО «Демо Банк», младший разработчик
Поддержка внутренних сервисов на Django, миграции схемы, CI в GitLab.

Навыки: Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kafka, ClickHouse, Git
О себе: люблю разбираться в производительности, наставничество джунов.
"""
QUESTION = "Как бы вы спроектировали ограничение частоты запросов (rate limiting) для публичного API?"
RUBRIC = [
    "Ограничение считается по ключу клиента (API-ключ, пользователь или IP)",
    "Счётчики хранятся в общем хранилище, доступном всем инстансам (например, Redis)",
    "Назван алгоритм: token bucket, leaky bucket или скользящее окно",
    "При превышении возвращается 429 и заголовок Retry-After",
]
GOOD_ANSWER = (
    "Лимит по API-ключу клиента, счётчики в Redis, чтобы все инстансы видели одно состояние. "
    "Алгоритм token bucket: ведро на ключ, пополнение с фиксированной скоростью. При превышении — "
    "HTTP 429 с заголовком Retry-After."
)
WEAK_ANSWER = "Поставлю nginx, он сам всё ограничит."


def _line(ok: bool, name: str, details: str) -> None:
    print(f"[{'OK' if ok else 'FAIL'}] {name}: {details}", flush=True)


async def check_raw() -> tuple[bool, str]:
    """Прямой вызов: показывает HTTP-ошибку провайдера, которую complete_json превращает в None."""
    try:
        text, tokens = await llm._yandex_call('Ответь JSON-объектом {"ok": true}', "проверка связи")
    except httpx.HTTPStatusError as error:
        return False, f"HTTP {error.response.status_code}: {error.response.text[:300]}"
    except httpx.HTTPError as error:
        return False, f"{type(error).__name__}: {error}"
    parsed = llm.extract_json_object(text)
    return parsed == {"ok": True}, f"ответ {text[:80]!r}, токенов {tokens}"


async def check_need() -> tuple[bool, str]:
    from app.modules.needs import parser

    base = parser.parse_dict(NEED_TEXT).draft
    result = await parser.parse_need_text(NEED_TEXT)
    draft = result.draft
    added = [
        key
        for key, value in draft.model_dump().items()
        if value not in (None, [], "") and getattr(base, key, None) in (None, [], "")
    ]
    details = (
        f"parser={result.parser.value}; {draft.specialization}/{draft.grade}; "
        f"обязательные {draft.required_skills}; желательные {draft.optional_skills}; "
        f"вилка {draft.salary_from}–{draft.salary_to}; LLM дополнил: {added or 'ничего'}; "
        f"не распознано {result.unmapped_terms}"
    )
    ok = draft.salary_from == 220000 and draft.salary_to == 260000 and draft.specialization == "backend"
    return ok, details


async def check_resume() -> tuple[bool, str]:
    from app.modules.resume import parser

    data = await parser.ask_llm(RESUME_TEXT, None)
    if data is None:
        return False, "LLM не вернул ответ, прошедший схему (после повтора) — откат на словарь"
    result = parser.merge_llm(parser.parse_dict(RESUME_TEXT), data)
    draft = result.draft
    filled = sorted(key for key, value in draft.model_dump().items() if value not in (None, [], "", {}))
    details = (
        f"used_llm={result.used_llm}; заполнено {len(filled)} полей: {', '.join(filled)}; "
        f"мест работы {len(draft.experience)}; не распознано {result.unmapped_terms}"
    )
    return result.used_llm and len(draft.experience) >= 1, details


async def check_rubric() -> tuple[bool, str]:
    good = await llm.rubric_hits(QUESTION, RUBRIC, GOOD_ANSWER, None)
    weak = await llm.rubric_hits(QUESTION, RUBRIC, WEAK_ANSWER, None)
    if good is None or weak is None:
        return False, f"ответ не по форме: сильный {good}, слабый {weak}"
    total = len(RUBRIC)
    return sum(good) > sum(weak), f"сильный ответ {sum(good)}/{total} {good}; слабый {sum(weak)}/{total}"


async def check_drafts() -> tuple[bool, str]:
    from app.modules.survey import service as survey_service
    from app.modules.testing import preview_service
    from app.modules.testing.engine import vacancy
    from app.modules.testing.engine.bank import get_bank, get_blueprints

    covered = {skill for template in get_bank().templates.values() for skill in template.skills}
    names, _ = preview_service._names()
    uncovered = [skill for skill in names if skill not in covered][:2]
    if not uncovered:
        return True, "все навыки справочника покрыты банком — черновики не нужны"
    plan = vacancy.build(
        get_bank(),
        get_blueprints(),
        "backend",
        ["python", *uncovered],
        [],
        survey_service.stack_modules_for("backend", {"stack": ["python"]}),
    )
    available, note, drafts = await preview_service._llm_block(plan, names, 0)
    titles = "; ".join(f"{d.title} [{d.topic}, {d.status}]" for d in drafts)
    return available and bool(drafts), f"навыки {uncovered}: {len(drafts)} черновиков — {titles or note}"


CHECKS: list[tuple[str, Callable[[], Awaitable[tuple[bool, str]]]]] = [
    ("связь с провайдером", check_raw),
    ("разбор потребности (§8.1)", check_need),
    ("разбор резюме (§7)", check_resume),
    ("чек-лист подхода (§10.5, §11)", check_rubric),
    ("черновики шаблонов (§10.7)", check_drafts),
]


async def main() -> int:
    settings = get_settings()
    if not llm.is_enabled():
        print(
            f"LLM выключен: LLM_PROVIDER={settings.llm_provider}, APP_ENV={settings.app_env}, "
            f"ключ {'задан' if settings.yandex_api_key else 'не задан'}, "
            f"folder {'задан' if settings.yandex_folder_id else 'не задан'}"
        )
        return 1
    print(f"Провайдер {settings.llm_provider}, модель {settings.yandex_model}")
    failed = 0
    with tempfile.TemporaryDirectory() as state_dir:
        settings.llm_state_dir = state_dir
        for name, check in CHECKS:
            started = time.monotonic()
            try:
                ok, details = await check()
            except Exception as error:  # проверка должна дойти до конца и показать все сценарии
                ok, details = False, f"{type(error).__name__}: {error}"
            _line(ok, name, f"{details} ({time.monotonic() - started:.1f} с)")
            failed += not ok
        status = llm.llm_status()
        print(f"Итого: вызовов {status['calls_today']}, токенов {status['tokens_today']}")
    print("Все сценарии работают" if not failed else f"Не прошло сценариев: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
