"""Резюме → черновик профиля и PDF-профиль (§7, T15): разбор, инварианты, доступ к PDF."""

import io
import os
from datetime import UTC, datetime, timedelta

import pdfplumber
import pytest

from app.core.config import get_settings
from app.core.enums import AttemptPurpose, AttemptResult, AttemptStatus, Grade, ParserKind, UnlockSource
from app.modules.categories.models import CandidateCategory
from app.modules.invitations.models import ContactUnlock
from app.modules.matching import service as matching_service
from app.modules.resume import parser
from app.modules.resume.service import extract_text
from app.modules.testing.models import TestAttempt as Attempt
from tests.resume_samples import ANNA, SAMPLES, make_pdf, make_scan_pdf
from tests.test_needs import candidate_id, employer_of, signup

API = "/api/v1"


def weasyprint_available() -> bool:
    # На Windows без GTK WeasyPrint не грузит pango (OSError); в CI (REQUIRE_WEASYPRINT=1) пропуск запрещён
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        if os.environ.get("REQUIRE_WEASYPRINT"):
            raise
        return False
    return True


needs_weasyprint = pytest.mark.skipif(not weasyprint_available(), reason="нет pango/cairo для WeasyPrint")


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    monkeypatch.setattr(parser.llm, "is_enabled", lambda: False)


def pdf_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


# ---------- словарный разбор пяти резюме ----------

EXPECTED = {
    "anna": {
        "skills": {"python", "fastapi", "django", "postgresql", "redis", "kafka", "docker", "git", "pytest"},
        "fields": {
            "first_name": "Анна",
            "last_name": "Кузнецова",
            "middle_name": "Сергеевна",
            "contact_email": "anna.kuznetsova@example.com",
            "phone": "+7 916 123-45-67",
            "telegram": "@anna_backend",
            "city": "Москва",
            "relocation": True,
            "salary_min": 250000,
            "experience_years": 4.5,
        },
        "unmapped": ["Tarantool"],
        "jobs": [
            ("ООО «Финтех Плюс»", "Backend-разработчик"),
            ("АО «Ритейл Тех»", "Junior Python-разработчик"),
        ],
    },
    "ilya": {
        "skills": {"javascript", "typescript", "react", "redux", "html", "css", "webpack", "jest"},
        "fields": {
            "first_name": "Ilya",
            "last_name": "Smirnov",
            "contact_email": "ilya.smirnov@example.com",
            "telegram": "@ilya_front",
            "city": "Санкт-Петербург",
            "salary_min": 120000,
        },
        "unmapped": ["Storybook"],
        "jobs": [("Studio Pixel", "Frontend Developer")],
    },
    "maria": {
        "skills": {
            "kubernetes",
            "docker",
            "terraform",
            "ansible",
            "prometheus",
            "grafana",
            "linux",
            "gitlab_ci",
            "bash",
            "python",
        },
        "fields": {
            "first_name": "Мария",
            "last_name": "Волкова",
            "phone": "+7 843 200-30-40",
            "city": "Казань",
            "experience_years": 7.0,
        },
        "unmapped": [],
        "jobs": [("Телеком Регион", "DevOps Lead"), ("Облако Про", "Site Reliability Engineer")],
    },
    "dmitry": {
        "skills": {
            "python",
            "pandas",
            "numpy",
            "scikit_learn",
            "pytorch",
            "sql",
            "airflow",
            "spark",
            "mlflow",
        },
        "fields": {
            "first_name": "Дмитрий",
            "last_name": "Петров",
            "telegram": "@dpetrov_ml",
            "city": "Новосибирск",
            "salary_min": 200000,
            "salary_max": 260000,
        },
        "unmapped": ["Optuna"],
        "jobs": [("Энерго Аналитика", "Senior Data Scientist"), ("Завод Север", "Data Scientist")],
    },
    "elena": {
        "skills": {"manual_testing", "python", "selenium", "playwright", "postman", "sql", "jira", "allure"},
        "fields": {
            "first_name": "Елена",
            "last_name": "Сидорова",
            "middle_name": "Викторовна",
            "phone": "+7 912 000-11-22",
            "city": "Екатеринбург",
            "experience_years": 3.0,
        },
        "unmapped": ["TestRail"],
        "jobs": [("Медтех Онлайн", "QA-инженер")],
    },
}


@pytest.mark.parametrize("name", list(SAMPLES))
def test_five_resumes_parse_into_expected_profile(name):
    text, pages = extract_text(make_pdf(SAMPLES[name]), max_pages=10)
    result = parser.parse_dict(text)
    expected = EXPECTED[name]

    assert pages == 1
    assert expected["skills"] <= set(result.draft.skills)
    for field, value in expected["fields"].items():
        assert getattr(result.draft, field) == value, field
    assert result.unmapped_terms == expected["unmapped"]
    assert [(job.company, job.position) for job in result.draft.experience] == expected["jobs"]


def test_experience_dates_and_total_years():
    result = parser.parse_dict(ANNA)
    newest, oldest = result.draft.experience
    assert (newest.started_on.isoformat(), newest.ended_on) == ("2022-01-01", None)
    assert (oldest.started_on.isoformat(), oldest.ended_on.isoformat()) == ("2020-03-01", "2021-12-01")
    total = parser.total_experience_years(result.draft.experience, today=datetime(2024, 3, 1).date())
    assert total == 4.0


# ---------- LLM только дополняет словарь ----------


def fake_llm(monkeypatch, answers: list[dict | None]) -> list[str]:
    calls: list[str] = []

    async def complete_json(system, user, schema_hint, user_id=None):
        calls.append(system)
        return answers[len(calls) - 1] if len(calls) <= len(answers) else None

    monkeypatch.setattr(parser.llm, "is_enabled", lambda: True)
    monkeypatch.setattr(parser.llm, "complete_json", complete_json)
    return calls


async def test_llm_fills_gaps_but_never_overrides_dictionary(monkeypatch):
    calls = fake_llm(
        monkeypatch,
        [
            {
                "first_name": "Ольга",
                "city": "Казань",
                "skills": ["Kotlin", "python", "Tarantool"],
                "roles": ["team_lead", "astronaut"],
                "grade": "senior",
                "experience": [{"company": "X", "position": "Y", "started_on": "2020-01"}],
            }
        ],
    )

    result = await parser.parse_resume_text(ANNA)

    assert len(calls) == 1 and result.used_llm
    assert result.draft.first_name == "Анна" and result.draft.city == "Москва"
    assert "kotlin" in result.draft.skills and result.draft.skills.count("python") == 1
    assert "team_lead" in result.draft.roles and "astronaut" not in result.draft.roles
    assert "Tarantool" in result.unmapped_terms
    assert [job.company for job in result.draft.experience] == ["ООО «Финтех Плюс»", "АО «Ритейл Тех»"]
    assert not hasattr(result.draft, "grade")


async def test_llm_invalid_answer_is_retried_once_then_falls_back_to_dictionary(monkeypatch):
    calls = fake_llm(monkeypatch, [{"salary_min": "много"}, {"experience_years": -3}, {"city": "Сочи"}])

    result = await parser.parse_resume_text(ANNA)

    assert len(calls) == 2 and parser.LLM_RETRY_NOTE in calls[1]
    assert not result.used_llm
    assert result.draft == parser.parse_dict(ANNA).draft


# ---------- загрузка резюме ----------


async def upload(client, headers, content: bytes, name: str = "cv.pdf", media: str = "application/pdf"):
    return await client.post(
        f"{API}/candidates/me/resume", files={"file": (name, content, media)}, headers=headers
    )


async def test_upload_returns_prefill_and_does_not_touch_profile(client, session, tmp_path):
    headers = await signup(client, "anna@example.com", role="candidate")

    response = await upload(client, headers, make_pdf(ANNA))

    assert response.status_code == 200, response.text
    body = response.json()
    prefill = body["prefill"]
    assert body["parser"] == ParserKind.dict
    assert prefill["first_name"] == "Анна" and prefill["phone"] == "+7 916 123-45-67"
    assert {"python", "fastapi", "postgresql"} <= {item["skill_id"] for item in prefill["declared_skills"]}
    assert len(prefill["experience"]) == 2
    assert {"first_name", "declared_skills", "experience"} <= set(body["from_resume"])
    assert body["suggested_grade"] == Grade.senior
    assert body["unmapped_terms"] == ["Tarantool"]
    assert len(list(tmp_path.rglob("*.pdf"))) == 1

    profile = (await client.get(f"{API}/candidates/me", headers=headers)).json()
    assert profile["first_name"] is None and profile["skills"] == []


async def test_account_deletion_removes_resume_file(client, session, tmp_path):
    headers = await signup(client, "anna@example.com", role="candidate")
    assert (await upload(client, headers, make_pdf(ANNA))).status_code == 200
    assert len(list(tmp_path.rglob("*.pdf"))) == 1

    deleted = await client.delete(f"{API}/candidates/me", headers=headers)

    assert deleted.status_code == 200, deleted.text
    assert list(tmp_path.rglob("*.pdf")) == []


async def test_confirmed_prefill_saves_skills_only_as_declared(client, session):
    headers = await signup(client, "anna@example.com", role="candidate")
    prefill = (await upload(client, headers, make_pdf(ANNA))).json()["prefill"]

    saved = await client.put(f"{API}/candidates/me", json=prefill, headers=headers)

    assert saved.status_code == 200, saved.text
    profile = saved.json()
    assert profile["first_name"] == "Анна" and profile["city"] == "Москва"
    assert {skill["status"] for skill in profile["skills"]} == {"declared"}
    assert profile["category"] is None


async def test_prefill_keeps_what_candidate_already_entered(client, session):
    headers = await signup(client, "anna@example.com", role="candidate")
    own = {
        "first_name": "Аня",
        "city": "Тверь",
        "declared_skills": [{"skill_id": "go"}],
        "work_formats": ["office"],
    }
    assert (await client.put(f"{API}/candidates/me", json=own, headers=headers)).status_code == 200

    prefill = (await upload(client, headers, make_pdf(ANNA))).json()["prefill"]

    assert prefill["first_name"] == "Аня" and prefill["city"] == "Тверь"
    assert prefill["last_name"] == "Кузнецова"
    skills = [item["skill_id"] for item in prefill["declared_skills"]]
    assert skills[0] == "go" and "python" in skills
    assert prefill["work_formats"] == ["office", "hybrid", "remote"]


async def test_scan_without_text_asks_to_fill_manually(client, session):
    headers = await signup(client, "anna@example.com", role="candidate")

    response = await upload(client, headers, make_scan_pdf())

    assert response.status_code == 200
    body = response.json()
    assert body["from_resume"] == [] and "заполните профиль вручную" in body["warnings"][0].lower()


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"PK\x03\x04 docx", "not_pdf"), (b"%PDF-1.7 broken", "invalid_pdf")],
)
async def test_upload_rejects_bad_files(client, session, content, code):
    headers = await signup(client, "anna@example.com", role="candidate")

    response = await upload(client, headers, content)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


async def test_upload_rejects_large_file(client, session, monkeypatch):
    headers = await signup(client, "anna@example.com", role="candidate")
    monkeypatch.setattr(get_settings(), "resume_max_bytes", 1000)

    response = await upload(client, headers, make_pdf(ANNA))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "file_too_large"


async def test_employer_cannot_upload_resume_or_get_candidate_pdf(client, session):
    employer = await signup(client, "hr@bank.ru")

    assert (await upload(client, employer, make_pdf(ANNA))).status_code == 403
    assert (await client.get(f"{API}/candidates/me/profile.pdf", headers=employer)).status_code == 403


# ---------- PDF-профиль: обезличенный и полный ----------

ANNA_PROFILE = {
    "first_name": "Анна",
    "last_name": "Кузнецова",
    "phone": "+7 916 123-45-67",
    "telegram": "@anna_backend",
    "contact_email": "anna.private@example.com",
    "city": "Москва",
    "work_formats": ["hybrid"],
    "salary_min": 250000,
    "experience_years": 4.5,
    "about": "Пишу платёжные сервисы. Связь: anna.private@example.com",
    "declared_skills": [{"skill_id": "fastapi"}],
    "experience": [
        {
            "company": "Финтех Плюс",
            "position": "Backend-разработчик",
            "started_on": "2022-01-01",
            "description": "Платежи. Telegram @anna_backend",
        }
    ],
}
CONTACT_MARKERS = ["Кузнецова", "123-45-67", "anna.private", "anna_backend", "Финтех Плюс"]


async def candidate_with_category(client, session, email: str = "anna@example.com") -> tuple[dict, int]:
    headers = await signup(client, email, role="candidate")
    assert (await client.put(f"{API}/candidates/me", json=ANNA_PROFILE, headers=headers)).status_code == 200
    candidate = await candidate_id(session, email)
    now = datetime.now(UTC)
    attempt = Attempt(
        candidate_id=candidate,
        specialization="backend",
        grade_target=Grade.middle,
        purpose=AttemptPurpose.calibration,
        blueprint={},
        seed=1,
        status=AttemptStatus.completed,
        theta=0.6,
        se=0.3,
        result=AttemptResult.passed,
        topic_scores={"databases": {"score": 0.85, "items": 4}, "http_api": {"score": 0.6, "items": 3}},
        skill_scores={},
        finished_at=now,
    )
    session.add(attempt)
    await session.flush()
    session.add(
        CandidateCategory(
            candidate_id=candidate,
            specialization="backend",
            grade=Grade.middle,
            theta=0.6,
            percentile=0.78,
            attempt_id=attempt.id,
            assigned_at=now,
            valid_until=now + timedelta(days=365),
            is_current=True,
        )
    )
    await session.flush()
    await matching_service.refresh_candidate(session, candidate)
    await session.commit()
    return headers, candidate


@needs_weasyprint
async def test_candidate_downloads_full_and_public_pdf(client, session):
    headers, _ = await candidate_with_category(client, session)

    full = await client.get(f"{API}/candidates/me/profile.pdf", headers=headers)
    public = await client.get(f"{API}/candidates/me/profile.pdf?variant=public", headers=headers)

    assert full.status_code == 200 and full.headers["content-type"] == "application/pdf"
    assert full.content.startswith(b"%PDF")
    text = pdf_text(full.content)
    assert "Кузнецова Анна" in text and "Backend · Middle" in text and "Базы данных" in text
    assert all(marker in text for marker in ["123-45-67", "anna.private", "Финтех Плюс"])
    public_text = pdf_text(public.content)
    assert "Анна К." in public_text and "Backend · Middle" in public_text
    assert not [marker for marker in CONTACT_MARKERS if marker in public_text]


@needs_weasyprint
async def test_employer_gets_public_pdf_until_contacts_are_unlocked(client, session):
    _, candidate = await candidate_with_category(client, session)
    employer_headers = await signup(client, "hr@bank.ru")
    employer = await employer_of(session, "hr@bank.ru")

    before = await client.get(f"{API}/talent/candidates/{candidate}/profile.pdf", headers=employer_headers)

    assert before.status_code == 200, before.text
    assert "public" in before.headers["content-disposition"]
    text = pdf_text(before.content)
    assert "Анна К." in text and "FastAPI" in text and "обезличенная" in text.lower()
    assert not [marker for marker in CONTACT_MARKERS if marker in text]

    session.add(
        ContactUnlock(
            employer_id=employer.id, candidate_id=candidate, source=UnlockSource.invitation, source_id=1
        )
    )
    await session.commit()
    after = await client.get(f"{API}/talent/candidates/{candidate}/profile.pdf", headers=employer_headers)

    assert after.status_code == 200
    unlocked = pdf_text(after.content)
    assert all(marker in unlocked for marker in CONTACT_MARKERS)


async def test_candidate_pdf_access_rules(client, session):
    candidate_headers, candidate = await candidate_with_category(client, session)
    employer_headers = await signup(client, "hr@bank.ru")

    as_candidate = await client.get(
        f"{API}/talent/candidates/{candidate}/profile.pdf", headers=candidate_headers
    )
    missing = await client.get(f"{API}/talent/candidates/999999/profile.pdf", headers=employer_headers)
    anonymous = await client.get(f"{API}/talent/candidates/{candidate}/profile.pdf")

    assert as_candidate.status_code == 403
    assert missing.status_code == 404
    assert anonymous.status_code == 401

    hidden = await client.put(
        f"{API}/candidates/me", json=ANNA_PROFILE | {"search_status": "hidden"}, headers=candidate_headers
    )
    assert hidden.status_code == 200
    blocked = await client.get(f"{API}/talent/candidates/{candidate}/profile.pdf", headers=employer_headers)
    assert blocked.status_code == 404
