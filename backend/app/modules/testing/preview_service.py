"""«Проверка под вакансию» (§10.7): требования → blueprint → примеры заданий из банка → черновики LLM.

Работает без LLM: разбор текста словарный, blueprint и примеры детерминированы. LLM только предлагает
черновики шаблонов для навыков, которых нет в банке; они всегда pilot и в оценку не входят.
Ключи ответов в ответ не попадают — это тот же инвариант, что и для попыток теста.
"""

from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm
from app.core.enums import Grade, ItemKind, TemplateStatus
from app.core.errors import AppError
from app.modules.catalog.service import get_catalog
from app.modules.needs import service as needs_service
from app.modules.needs.parser import parse_need_text
from app.modules.needs.schemas import NeedDraft
from app.modules.survey import service as survey_service
from app.modules.testing.engine import vacancy
from app.modules.testing.engine.bank import CONTENT_DIR, GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.render import render
from app.modules.testing.schemas import (
    BlueprintPreview,
    ItemOption,
    LlmTemplateDraft,
    PreviewItem,
    SkillRef,
    TopicWeight,
    VacancyExample,
    VacancyTestPreview,
    VacancyTestPreviewRequest,
)

DEFAULT_SEED = 1
DEFAULT_GRADE = Grade.middle
MAX_DRAFTS = 3

LLM_SYSTEM = (
    "Ты помогаешь пополнять банк заданий технического теста. Для каждого навыка из списка предложи "
    "черновик одного короткого задания с выбором ответа: название, тема из списка допустимых, "
    "формулировка вопроса. Не пиши ответы и варианты. Черновик проверит человек."
)


class PreviewError(AppError):
    status_code = 422
    code = "vacancy_not_recognized"


@lru_cache
def examples() -> list[VacancyExample]:
    """Демо-набор вакансий из content/demo_vacancies/ (§10.7)."""
    items: list[VacancyExample] = []
    for path in sorted((CONTENT_DIR / "demo_vacancies").glob("*.yaml")):
        with path.open(encoding="utf-8") as file:
            items += [VacancyExample.model_validate(raw) for raw in yaml.safe_load(file) or []]
    return items


def _names() -> tuple[dict[str, str], dict[str, str]]:
    catalog = get_catalog()
    return (
        {skill.id: skill.name for skill in catalog.skills},
        {item.slug.value: item.name for item in catalog.grades},
    )


def _difficulty(b: float, grade_names: dict[str, str]) -> str:
    """Сложность словами: самый высокий грейд, порог которого не выше b шаблона."""
    blueprints = get_blueprints()
    level = next((g for g in reversed(GRADE_ORDER) if b >= blueprints.cut(g)), None)
    return f"уровень {grade_names.get(level, level)}" if level else "ниже уровня стажёра"


async def _requirements(db: AsyncSession, user_id: int, body: VacancyTestPreviewRequest) -> NeedDraft:
    if body.need_id is not None:
        need = await needs_service.get_own_need(db, user_id, body.need_id)
        return NeedDraft(
            title=need.title,
            specialization=need.specialization,
            grade=need.grade,
            required_skills=list(need.required_skills or []),
            optional_skills=list(need.optional_skills or []),
            industry=need.industry,
            team_description=need.team_description,
            work_format=need.work_format,
            city=need.city,
            salary_from=need.salary_from,
            salary_to=need.salary_to,
        )
    parsed = await parse_need_text(body.raw_text or "", user_id=user_id)
    return parsed.draft


def _check_specialization(draft: NeedDraft) -> str:
    if not draft.specialization:
        raise PreviewError(
            "Не удалось определить специализацию по тексту: добавьте стек и обязанности",
            code="specialization_not_detected",
        )
    spec = next((s for s in get_catalog().specializations if s.slug == draft.specialization), None)
    if spec is None or not spec.has_test or draft.specialization not in get_blueprints().specializations:
        raise PreviewError("Для этой специализации тест появится позже", code="no_test_for_specialization")
    return draft.specialization


def _weight_changes(plan: vacancy.VacancyBlueprint, skill_names: dict[str, str]) -> list[str]:
    topic_names = get_blueprints().topic_names
    changes = [
        f"{skill_names.get(b.skill, b.skill)} ({'обязательный' if b.required else 'желательный'}) "
        f"→ +{b.weight} к весу темы «{topic_names.get(b.topic, b.topic)}»"
        for b in plan.boosts
    ]
    if plan.stack_modules:
        changes.append(f"Стек-модули по навыкам вакансии: {', '.join(plan.stack_modules)}")
    changes += [
        f"Тема «{topic_names.get(topic, topic)}» без шаблонов под стек вакансии — её задания "
        "распределены по другим темам"
        for topic in plan.dropped_topics
    ]
    return changes


def _blueprint_out(
    plan: vacancy.VacancyBlueprint, grade: Grade, skill_names: dict[str, str]
) -> BlueprintPreview:
    topic_names = get_blueprints().topic_names
    topics = sorted(
        {*plan.base_topics, *plan.topics},
        key=lambda t: (-plan.topics.get(t, 0), -plan.base_topics.get(t, 0), t),
    )
    return BlueprintPreview(
        specialization=plan.specialization,
        grade=grade,
        total_items=sum(plan.topics.values()),
        topics=[
            TopicWeight(
                topic=topic,
                name=topic_names.get(topic, topic),
                base_items=plan.base_topics.get(topic, 0),
                items=plan.topics.get(topic, 0),
            )
            for topic in topics
        ],
        stack_modules=plan.stack_modules,
        weight_changes=_weight_changes(plan, skill_names),
    )


def _sample_items(
    plan: vacancy.VacancyBlueprint, draft: NeedDraft, grade: Grade, seed: int
) -> list[PreviewItem]:
    skill_names, grade_names = _names()
    topic_names = get_blueprints().topic_names
    skills = list(draft.required_skills) + list(draft.optional_skills)
    templates = vacancy.sample_templates(get_bank(), get_blueprints(), plan, skills, grade.value)
    items = []
    for template in templates:
        instance = render(template, seed)  # ключ instance.key остаётся на сервере
        items.append(
            PreviewItem(
                template_id=template.id,
                topic=template.topic,
                topic_name=topic_names.get(template.topic, template.topic),
                skills=[skill_names.get(skill, skill) for skill in template.skills],
                difficulty_b=template.irt.b,
                difficulty=_difficulty(template.irt.b, grade_names),
                kind=ItemKind(instance.kind),
                stem=instance.stem,
                code=instance.code,
                code_language=instance.code_language,
                options=[ItemOption(id=option.id, text=option.text) for option in instance.options],
            )
        )
    return items


def _drafts_from_llm(
    data: dict[str, Any] | None, uncovered: list[str], topics: set[str], skill_names: dict[str, str]
) -> list[LlmTemplateDraft]:
    """Ответ LLM проверяется по справочникам: тема только из blueprint, навыки только из непокрытых."""
    raw = data.get("drafts") if isinstance(data, dict) else None
    by_name = {skill_names.get(s, s).lower(): s for s in uncovered} | {s: s for s in uncovered}
    drafts: list[LlmTemplateDraft] = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        title, stem, topic = entry.get("title"), entry.get("stem"), entry.get("topic")
        skills = entry.get("skills") if isinstance(entry.get("skills"), list) else []
        known = [by_name[s.lower()] for s in skills if isinstance(s, str) and s.lower() in by_name]
        if not (isinstance(title, str) and isinstance(stem, str) and title.strip() and stem.strip()):
            continue
        if topic not in topics or not known:
            continue
        drafts.append(
            LlmTemplateDraft(
                title=title.strip()[:200],
                topic=topic,
                skills=[skill_names.get(s, s) for s in dict.fromkeys(known)],
                stem=stem.strip()[:1000],
                status=TemplateStatus.pilot,
            )
        )
        if len(drafts) == MAX_DRAFTS:
            break
    return drafts


async def _llm_block(
    plan: vacancy.VacancyBlueprint, skill_names: dict[str, str], user_id: int
) -> tuple[bool, str, list[LlmTemplateDraft]]:
    uncovered = plan.uncovered_skills
    available = llm.is_enabled()
    if not uncovered:
        return available, "Все навыки вакансии покрыты банком шаблонов — черновики не нужны.", []
    names = ", ".join(skill_names.get(s, s) for s in uncovered)
    if not available:
        return (
            False,
            f"Для навыков {names} в банке нет шаблонов. Генерация черновиков LLM на этом стенде "
            "выключена: тест собирается из калиброванного банка, черновики появятся после включения LLM.",
            [],
        )
    topics = sorted(plan.topics)
    hint = (
        '{"drafts": [{"title": string, "topic": "' + "|".join(topics) + '", '
        '"skills": [skill_id], "stem": string}]}'
    )
    user_text = "Навыки: " + ", ".join(f"{s} ({skill_names.get(s, s)})" for s in uncovered)
    data = await llm.complete_json(LLM_SYSTEM, user_text, hint, user_id=user_id)
    drafts = _drafts_from_llm(data, uncovered, set(topics), skill_names)
    if not drafts:
        return True, f"Для навыков {names} LLM не вернул пригодных черновиков — попробуйте позже.", []
    return (
        True,
        "Черновики LLM: статус pilot, проходят ревью и калибровку и не влияют на оценку до неё.",
        drafts,
    )


async def preview(db: AsyncSession, user_id: int, body: VacancyTestPreviewRequest) -> VacancyTestPreview:
    draft = await _requirements(db, user_id, body)
    specialization = _check_specialization(draft)
    grade = draft.grade or DEFAULT_GRADE
    skill_names, _ = _names()
    skills = list(draft.required_skills) + list(draft.optional_skills)
    plan = vacancy.build(
        get_bank(),
        get_blueprints(),
        specialization,
        list(draft.required_skills),
        list(draft.optional_skills),
        survey_service.stack_modules_for(specialization, {"stack": skills}),
    )
    seed = body.regenerate_seed if body.regenerate_seed is not None else DEFAULT_SEED
    available, note, drafts = await _llm_block(plan, skill_names, user_id)
    return VacancyTestPreview(
        requirements=draft,
        blueprint=_blueprint_out(plan, grade, skill_names),
        sample_items=_sample_items(plan, draft, grade, seed),
        seed=seed,
        uncovered_skills=[SkillRef(id=s, name=skill_names.get(s, s)) for s in plan.uncovered_skills],
        llm_available=available,
        llm_note=note,
        llm_drafts=drafts,
    )
