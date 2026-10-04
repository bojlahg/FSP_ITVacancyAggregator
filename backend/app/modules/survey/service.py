"""Опрос (§6.2): рекомендация специализации, подсказка грейда, стек-модули теста."""

from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Grade, SkillSource, WorkFormat
from app.core.errors import AppError, ConflictError
from app.modules.candidates.models import Candidate, CandidateSkill
from app.modules.catalog.service import CONTENT_DIR, get_catalog
from app.modules.categories import service as categories_service
from app.modules.survey.models import SurveyResponse
from app.modules.survey.schemas import (
    SpecializationScore,
    SurveyOption,
    SurveyQuestion,
    SurveyResult,
)

# Вклад заявленного навыка в балл специализации по семейству навыка
FAMILY_WEIGHTS: dict[str, dict[str, float]] = {
    "backend": {"backend": 0.1, "fullstack": 0.05},
    "frontend": {"frontend": 0.1, "fullstack": 0.05},
    "mobile": {"mobile": 0.1},
    "qa": {"qa": 0.1},
    "devops": {"devops": 0.1},
    "data": {"data": 0.1},
    "ml": {"data": 0.1},
    "database": {"backend": 0.05, "data": 0.05},
    "analysis": {"analyst": 0.1},
    "gamedev": {"gamedev": 0.1},
}
SKILL_CONTRIBUTION_CAP = 0.5


class SurveyValidationError(AppError):
    status_code = 422
    code = "survey_invalid"
    message = "Ответы на опрос заполнены не полностью"


@lru_cache
def survey_config() -> dict[str, Any]:
    with (CONTENT_DIR / "survey.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def _options(question: dict) -> list[dict]:
    source = question.get("source")
    if source == "team_roles":
        return [{"id": item.slug, "label": item.name} for item in get_catalog().team_roles]
    if source == "industries":
        return [{"id": item.slug, "label": item.name} for item in get_catalog().industries]
    return question.get("options", [])


def get_questions() -> list[SurveyQuestion]:
    return [
        SurveyQuestion(
            id=question["id"],
            text=question["text"],
            kind=question["kind"],
            required=question.get("required", True),
            options=[SurveyOption(id=option["id"], label=option["label"]) for option in _options(question)],
        )
        for question in survey_config()["questions"]
    ]


def _validate(answers: dict[str, Any]) -> list[dict]:
    issues = []
    skill_ids = {skill.id for skill in get_catalog().skills}
    for question in survey_config()["questions"]:
        qid, kind = question["id"], question["kind"]
        value = answers.get(qid)
        empty = value in (None, "", []) or (kind == "salary_range" and not isinstance(value, dict))
        if empty:
            if question.get("required", True):
                issues.append(
                    {"loc": ["body", "answers", qid], "msg": "Ответьте на вопрос", "type": "missing"}
                )
            continue
        allowed = {option["id"] for option in _options(question)}
        if (
            kind == "single"
            and value not in allowed
            or kind == "multi"
            and (not isinstance(value, list) or not set(value) <= allowed)
        ):
            issues.append({"loc": ["body", "answers", qid], "msg": "Недопустимый вариант", "type": "enum"})
        elif kind == "skills" and (not isinstance(value, list) or not set(value) <= skill_ids):
            issues.append({"loc": ["body", "answers", qid], "msg": "Неизвестный навык", "type": "enum"})
        elif kind == "number" and (not isinstance(value, int | float) or not 0 <= value <= 60):
            issues.append({"loc": ["body", "answers", qid], "msg": "Число от 0 до 60", "type": "value_error"})
        elif kind == "salary_range":
            low, high = value.get("from"), value.get("to")
            if not (isinstance(low, int) and isinstance(high, int) and 0 < low <= high):
                issues.append(
                    {
                        "loc": ["body", "answers", qid],
                        "msg": "Вилка «от ≤ до» в рублях",
                        "type": "value_error",
                    }
                )
    return issues


def score_specializations(answers: dict[str, Any]) -> dict[str, float]:
    """Сумма весов выбранных вариантов + небольшой вклад навыков; нормировка на максимум (§6.2)."""
    scores: dict[str, float] = defaultdict(float)
    for question in survey_config()["questions"]:
        value = answers.get(question["id"])
        chosen = value if isinstance(value, list) else [value]
        for option in question.get("options", []):
            if option["id"] in chosen:
                for spec, weight in option.get("weights", {}).items():
                    scores[spec] += weight
    families = {skill.id: skill.family for skill in get_catalog().skills}
    from_skills: dict[str, float] = defaultdict(float)
    for skill_id in answers.get("stack") or []:
        for spec, weight in FAMILY_WEIGHTS.get(families.get(skill_id, ""), {}).items():
            from_skills[spec] += weight
    for spec, value in from_skills.items():
        scores[spec] += min(value, SKILL_CONTRIBUTION_CAP)
    top = max(scores.values(), default=0.0)
    return {spec: round(value / top, 3) for spec, value in scores.items()} if top else {}


def suggest_grade(experience_years: float | None) -> Grade:
    years = experience_years or 0.0
    for rule in survey_config()["grade_hint"]:
        if years < rule["max_years"] or rule["max_years"] >= 100:
            return Grade(rule["grade"])
    return Grade.senior


def stack_modules_for(specialization: str, answers: dict[str, Any]) -> list[str]:
    declared = {*(answers.get("stack") or []), answers.get("main_language")}
    modules = survey_config()["stack_modules"].get(specialization, {})
    return [module for module, skills in modules.items() if declared & set(skills)]


async def latest_response(db: AsyncSession, candidate_id: int) -> SurveyResponse | None:
    return await db.scalar(
        select(SurveyResponse)
        .where(SurveyResponse.candidate_id == candidate_id)
        .order_by(SurveyResponse.created_at.desc(), SurveyResponse.id.desc())
        .limit(1)
    )


def result_of(response: SurveyResponse) -> SurveyResult:
    names = {spec.slug: spec.name for spec in get_catalog().specializations}
    ranked = sorted(response.spec_scores.items(), key=lambda item: (-item[1], item[0]))
    top = ranked[0][0] if ranked else response.specialization
    return SurveyResult(
        response_id=response.id,
        recommended=[
            SpecializationScore(specialization=spec, name=names.get(spec, spec), score=value)
            for spec, value in ranked[:3]
            if value > 0
        ],
        suggested_grade=suggest_grade(response.answers.get("experience_years")),
        stack_modules=stack_modules_for(top, response.answers),
    )


async def submit(db: AsyncSession, candidate: Candidate, answers: dict[str, Any]) -> SurveyResult:
    issues = _validate(answers)
    if issues:
        raise SurveyValidationError(details=issues)
    scores = score_specializations(answers)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top = ranked[0][0] if ranked else "backend"

    response = SurveyResponse(
        candidate_id=candidate.id, answers=answers, spec_scores=scores, specialization=top
    )
    db.add(response)
    _apply_to_profile(candidate, answers)
    await _replace_declared_skills(db, candidate.id, answers.get("stack") or [])
    await db.commit()
    return result_of(response)


def _apply_to_profile(candidate: Candidate, answers: dict[str, Any]) -> None:
    candidate.experience_years = answers.get("experience_years")
    candidate.roles = answers.get("roles") or []
    candidate.industries_exp = answers.get("industries_exp") or []
    candidate.industries_pref = answers.get("industries_pref") or []
    candidate.work_formats = [WorkFormat(value).value for value in answers.get("work_formats") or []]
    candidate.city = answers.get("city") or candidate.city
    candidate.relocation = answers.get("relocation") == "yes"
    salary = answers.get("salary") or {}
    candidate.salary_min, candidate.salary_max = salary.get("from"), salary.get("to")


async def _replace_declared_skills(db: AsyncSession, candidate_id: int, skill_ids: list[str]) -> None:
    await db.execute(
        delete(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate_id, CandidateSkill.source == SkillSource.declared
        )
    )
    now = datetime.now(UTC)
    for skill_id in dict.fromkeys(skill_ids):
        db.add(
            CandidateSkill(
                candidate_id=candidate_id, skill_id=skill_id, source=SkillSource.declared, updated_at=now
            )
        )


async def confirm_specialization(db: AsyncSession, candidate: Candidate, specialization: str) -> None:
    if specialization not in {spec.slug for spec in get_catalog().specializations}:
        raise AppError("Неизвестная специализация", code="unknown_specialization")
    if await latest_response(db, candidate.id) is None:
        raise ConflictError("Сначала пройдите опрос", code="survey_required")
    current = await categories_service.get_current(db, candidate.id)
    if current is not None and current.specialization != specialization:
        raise ConflictError(
            "Специализация закреплена за действующей категорией",
            code="specialization_locked",
            details={"specialization": current.specialization},
        )
    candidate.specialization = specialization
    await db.commit()
