"""Словарный разбор текста потребности и слияние с LLM (§8.1 п.2, T08)."""

import json
from pathlib import Path

import httpx
import pytest

from app.core import llm
from app.core.config import get_settings
from app.core.enums import Grade, ParserKind, WorkFormat
from app.modules.needs import parser

BACKEND_FINTECH = """Middle Python-разработчик (Backend) в платёжный сервис
Мы — финтех-команда, делаем платёжную платформу для банков.
Требования:
- опыт коммерческой разработки на Python от 3 лет;
- FastAPI или Django, асинхронность;
- PostgreSQL, умение писать сложные запросы;
- Kafka, опыт работы с Kafka Streams;
- Docker, CI/CD.
Будет плюсом:
- Kubernetes;
- ClickHouse.
Условия: полностью удалённая работа, зарплата от 250 000 до 300 000 ₽ на руки.
"""

FRONTEND_JUNIOR = """Junior Frontend-разработчик
Ищем начинающего фронтенд-разработчика в команду интернет-магазина.
Что нужно:
• уверенное знание JavaScript, TypeScript и React;
• HTML, CSS, адаптивная вёрстка;
• Git.
Работа в офисе в Москве (м. Белорусская), гибкое начало дня.
Зарплата от 120 000 ₽.
"""

QA_MIDDLE = """QA-инженер (Middle), автоматизация тестирования
Задачи: писать автотесты на Python (pytest), тестирование API, ревью тест-кейсов.
Требования: опыт от 2 лет, знание SQL, Postman, Allure.
Будет плюсом: k6 и опыт нагрузочного тестирования.
Гибридный формат, Санкт-Петербург. Вилка 180–230 тыс. руб.
"""

DEVOPS_SENIOR = """Senior DevOps / SRE инженер
Ищем инженера в команду платформы, которая отвечает за инфраструктуру всех продуктов.
Требования:
- Kubernetes (k8s), Helm, Terraform, Ansible;
- Prometheus, Grafana;
- Linux на уровне администратора;
- GitLab CI.
Желательно: опыт с Yandex Cloud.
Удалёнка или офис в Казани. Зарплата до 400к.
"""


def test_backend_fintech_remote():
    result = parser.parse_dict(BACKEND_FINTECH)
    draft = result.draft

    assert draft.specialization == "backend"
    assert draft.grade == Grade.middle
    assert {"python", "fastapi", "django", "postgresql", "kafka", "docker", "ci_cd", "concurrency"} <= set(
        draft.required_skills
    )
    assert set(draft.optional_skills) == {"kubernetes", "clickhouse"}
    assert draft.salary_from == 250_000 and draft.salary_to == 300_000
    assert draft.work_format == WorkFormat.remote
    assert draft.city is None
    assert draft.industry == "fintech"
    assert draft.title == "Middle Backend-разработчик"
    assert "Kafka Streams" in result.unmapped_terms
    assert "requirements" not in draft.required_skills


def test_frontend_junior_office_moscow():
    draft = parser.parse_dict(FRONTEND_JUNIOR).draft

    assert draft.specialization == "frontend"
    assert draft.grade == Grade.junior
    assert {"javascript", "typescript", "react", "html", "css", "git"} == set(draft.required_skills)
    assert draft.optional_skills == []
    assert draft.salary_from == 120_000 and draft.salary_to is None
    assert draft.work_format == WorkFormat.office
    assert draft.city == "Москва"
    assert draft.industry == "ecommerce"


def test_qa_middle_optional_k6():
    result = parser.parse_dict(QA_MIDDLE)
    draft = result.draft

    assert draft.specialization == "qa"
    assert draft.grade == Grade.middle
    assert {"python", "pytest", "test_automation", "api_testing", "sql", "postman", "allure"} <= set(
        draft.required_skills
    )
    assert "load_testing" in draft.optional_skills
    assert "k6" in result.unmapped_terms
    assert draft.salary_from == 180_000 and draft.salary_to == 230_000
    assert draft.work_format == WorkFormat.hybrid
    assert draft.city == "Санкт-Петербург"


def test_devops_senior_salary_to_only():
    draft = parser.parse_dict(DEVOPS_SENIOR).draft

    assert draft.specialization == "devops"
    assert draft.grade == Grade.senior
    assert {
        "kubernetes",
        "helm",
        "terraform",
        "ansible",
        "prometheus",
        "grafana",
        "linux",
        "gitlab_ci",
    } <= set(draft.required_skills)
    assert draft.optional_skills == ["yandex_cloud"]
    assert draft.salary_from is None and draft.salary_to == 400_000
    assert draft.work_format == WorkFormat.hybrid
    assert draft.city == "Казань"


@pytest.mark.parametrize(
    "text",
    [
        "Ищем Head of Sales для go to market стратегии",
        "Ведущий C-level менеджер, опыт R&D",
        "Присылайте CV на почту, будем рады",
        "Требования: ответственность. Наши плюсы — дружная команда и сети магазинов",
        "Компания с 5000 сотрудников и 10 000 клиентов",
    ],
)
def test_no_false_positive_skills(text):
    draft = parser.parse_dict(text).draft

    assert draft.required_skills == [] and draft.optional_skills == []
    assert draft.salary_from is None and draft.salary_to is None


@pytest.mark.parametrize(
    ("text", "skill"),
    [
        ("Backend-разработчик на Go, опыт от 3 лет", "go"),
        ("Стек: Python, Go, PostgreSQL", "go"),
        ("Нужен опыт разработки на C и C++", "c"),
        ("Знание языка R для статистики", "r"),
        ("Опыт с PyTorch, CV, NLP", "computer_vision"),
        ("Работа с кафкой и постгресом", "kafka"),
        ("Работа с кафкой и постгресом", "postgresql"),
        ("Пишем на Vue3 и Node.js", "vue"),
        ("Пишем на Vue3 и Node.js", "nodejs"),
    ],
)
def test_context_and_morphology_matches(text, skill):
    assert skill in parser.parse_dict(text).draft.required_skills


def test_unit_tests_not_unity_and_spring_boot_longest_match():
    draft = parser.parse_dict("Java, Spring Boot, юнит-тесты и модульное тестирование на JUnit").draft

    assert "unity" not in draft.required_skills
    assert "spring_boot" in draft.required_skills and "spring" not in draft.required_skills
    assert {"unit_testing", "junit"} <= set(draft.required_skills)


def test_experience_heuristics_and_lead():
    assert parser.detect_grade("Требуется опыт от 6 лет в разработке", "Разработчик") == Grade.senior
    assert parser.detect_grade("Нужен опыт не менее 1 года", "Разработчик") == Grade.junior
    assert parser.detect_grade("", "Tech Lead Java") == Grade.senior
    assert parser.detect_grade("Мы — ведущая компания рынка", "Разработчик") is None
    assert parser.detect_grade("", "Стажёр-аналитик") == Grade.intern


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ЗП 200-300 тыс. gross", (200_000, 300_000)),
        ("Вилка: 250к", (250_000, 250_000)),
        ("Оклад до 350 000 рублей", (None, 350_000)),
        ("от 1,5 млн в год", (1_500_000, None)),
        ("Опыт от 3 до 5 лет", (None, None)),
    ],
)
def test_salary_patterns(text, expected):
    assert parser.detect_salary(text) == expected


async def test_parse_without_llm_is_dict(monkeypatch):
    monkeypatch.setattr(parser.llm, "is_enabled", lambda: False)

    result = await parser.parse_need_text(BACKEND_FINTECH)

    assert result.parser == ParserKind.dict
    assert result.draft.specialization == "backend"


async def test_llm_merge_adds_only_catalog_values(monkeypatch):
    async def fake_llm(system: str, user: str, schema_hint: str, user_id: int | None = None) -> dict:
        assert "postgresql" in schema_hint and user_id == 7
        return {
            "specialization": "frontend",  # словарь уже определил backend — не перезаписываем
            "grade": "lead",  # вне справочника — отбрасываем
            "required_skills": ["redis", "Kafka Streams", "python"],
            "optional_skills": ["grpc"],
            "industry": "fintech",
            "city": "Москва",
            "salary_from": 999_999,
            "salary_to": 1,
            "unmapped_terms": ["Debezium"],
        }

    monkeypatch.setattr(llm, "complete_json", fake_llm)

    result = await parser.parse_need_text(BACKEND_FINTECH, user_id=7)
    draft = result.draft

    assert result.parser == ParserKind.llm
    assert draft.specialization == "backend"
    assert draft.grade == Grade.middle
    assert "redis" in draft.required_skills and "grpc" in draft.optional_skills
    assert draft.required_skills.count("python") == 1
    assert draft.salary_from == 250_000 and draft.salary_to == 300_000
    assert draft.city == "Москва"
    assert "Debezium" in result.unmapped_terms
    assert [term.lower() for term in result.unmapped_terms].count("kafka streams") == 1


def test_title_from_grade_and_specialization_or_first_clause():
    text = "Ищем junior backend-разработчика на Python в финтех-команду. Стек: FastAPI, PostgreSQL."
    assert parser.parse_dict(text).draft.title == "Junior Backend-разработчик"
    assert parser.parse_dict(DEVOPS_SENIOR).draft.title == "Senior DevOps-инженер"
    assert parser.compose_title("qa", None, "что угодно") == "QA-инженер"
    assert parser.compose_title("data", Grade.intern, None) == "Стажёр Data Scientist"

    unknown = parser.parse_dict("Нужен человек в команду, срочно! Работа с документами и отчётами.").draft
    assert unknown.specialization is None and unknown.title == "Нужен человек в команду"
    assert parser.compose_title(None, Grade.middle, "Ищем сильного инженера.") == "Ищем сильного инженера"
    assert parser.compose_title(None, None, None) is None


async def test_llm_specialization_and_grade_rebuild_title(monkeypatch):
    async def fake_llm(system: str, user: str, schema_hint: str, user_id: int | None = None) -> dict:
        return {"specialization": "qa", "grade": "junior"}

    monkeypatch.setattr(llm, "complete_json", fake_llm)

    result = await parser.parse_need_text("Нужен человек в команду, срочно! Проверять релизы.")

    assert result.parser == ParserKind.llm
    assert result.draft.title == "Junior QA-инженер"


def test_llm_merge_ignores_invalid_payload():
    base = parser.parse_dict(FRONTEND_JUNIOR)

    merged, contributed = parser.merge_llm(
        base, {"grade": "guru", "required_skills": "react", "salary_to": "x"}
    )

    assert contributed is False
    assert merged.draft == base.draft


def test_extract_json_object_strips_fences():
    text = 'Вот ответ:\n```json\n{"grade": "middle", "required_skills": ["python"]}\n```'

    assert llm.extract_json_object(text) == {"grade": "middle", "required_skills": ["python"]}
    assert llm.extract_json_object("нет json") is None


YANDEX_ANSWER = {
    "result": {
        "alternatives": [{"message": {"role": "assistant", "text": '```json\n{"grade": "middle"}\n```'}}],
        "usage": {"inputTextTokens": "100", "completionTokens": "20", "totalTokens": "120"},
    }
}


@pytest.fixture
def transport(monkeypatch, tmp_path) -> list[dict]:
    """LLM включён как на проде, но транспорт подменён: сеть не трогаем, вызовы считаем."""
    settings = get_settings()
    for name, value in {
        "app_env": "dev",
        "llm_provider": "yandex",
        "yandex_api_key": "fake-key",
        "yandex_folder_id": "fake-folder",
        "llm_state_dir": str(tmp_path / "llm"),
    }.items():
        monkeypatch.setattr(settings, name, value)
    calls: list[dict] = []

    async def fake_post(url: str, headers: dict, body: dict) -> dict:
        calls.append(body)
        return YANDEX_ANSWER

    monkeypatch.setattr(llm, "post_json", fake_post)
    return calls


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectTimeout("timeout"), httpx.HTTPStatusError("503", request=None, response=None), "не json"],
)
async def test_need_parse_falls_back_to_dict_when_llm_fails(transport, monkeypatch, failure):
    async def broken_post(url: str, headers: dict, body: dict) -> dict:
        if isinstance(failure, Exception):
            raise failure
        return {"result": {"alternatives": [{"message": {"text": failure}}], "usage": {"totalTokens": "5"}}}

    monkeypatch.setattr(llm, "post_json", broken_post)

    result = await parser.parse_need_text(BACKEND_FINTECH, user_id=1)

    assert result.parser == ParserKind.dict
    assert result.draft == parser.parse_dict(BACKEND_FINTECH).draft


async def test_llm_never_calls_network_in_test_env(transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "test")

    assert await llm.complete_json("system", "текст вакансии", "{}", user_id=1) is None
    assert transport == []
    assert llm.llm_status()["enabled"] is False


async def test_llm_cache_truncation_and_usage(transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_max_input_chars", 10)

    first = await llm.complete_json("system", "очень длинный текст вакансии", "{}", user_id=1)
    second = await llm.complete_json("system", "очень длинный текст вакансии", "{}", user_id=1)

    assert first == second == {"grade": "middle"}
    assert len(transport) == 1
    assert transport[0]["messages"][1]["text"] == "очень длинный текст вакансии"[:10]
    assert transport[0]["completionOptions"]["maxTokens"] == str(get_settings().llm_max_output_tokens)
    status = llm.llm_status()
    assert status["enabled"] is True
    assert (status["calls_today"], status["tokens_today"]) == (1, 120)


async def test_llm_daily_call_limit(transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_daily_call_limit", 2)

    results = [await llm.complete_json("system", f"текст {index}", "{}") for index in range(3)]

    assert results[:2] == [{"grade": "middle"}] * 2 and results[2] is None
    assert len(transport) == 2


async def test_llm_daily_token_limit(transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_daily_token_limit", 100)

    assert await llm.complete_json("system", "текст", "{}") is None
    assert transport == []


async def test_llm_user_hourly_limit(transport, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_user_hourly_limit", 1)

    assert await llm.complete_json("system", "первый", "{}", user_id=5) is not None
    assert await llm.complete_json("system", "второй", "{}", user_id=5) is None
    assert await llm.complete_json("system", "второй", "{}", user_id=6) is not None
    assert len(transport) == 2
    # Часовой лимит хранится в файле состояния, а не в памяти: его видят все процессы backend
    shared = json.loads((Path(get_settings().llm_state_dir) / llm.USERS_FILE).read_text(encoding="utf-8"))
    assert set(shared) == {"5", "6"} and len(shared["5"]) == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Ищем Middle Python-разработчика в платёжную команду. Обязательно: FastAPI, PostgreSQL, Docker. "
            "Будет плюсом: Kafka, Kubernetes.",
            "backend",
        ),
        ("Нужен разработчик на Go: gRPC, PostgreSQL, Docker, Kubernetes, Helm", "backend"),
        (".NET-разработчик, ASP.NET Core, MS SQL, Docker", "backend"),
        ("React-разработчик в команду личного кабинета, TypeScript, Docker", "frontend"),
        ("DevOps-инженер: Docker, Kubernetes, Terraform, Prometheus", "devops"),
        ("Инженер по автоматизации тестирования на Python: pytest, Playwright, Docker", "qa"),
    ],
)
def test_specialization_from_role_language_beats_infra_skills(text, expected):
    """Язык рядом с ролью («Python-разработчик») весит больше, чем Docker и Kubernetes в стеке."""
    assert parser.parse_dict(text).draft.specialization == expected
