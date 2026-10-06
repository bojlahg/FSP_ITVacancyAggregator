"""Банк шаблонов и blueprint'ы (§10.2–10.3): загрузка из backend/content и проверка целостности."""

from collections import Counter
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.modules.testing.engine.generators import load_all
from app.modules.testing.engine.model import CHOICE_KINDS, Template
from app.modules.testing.engine.render import render

CONTENT_DIR = Path(__file__).resolve().parents[4] / "content"
GRADE_ORDER = ["intern", "junior", "middle", "senior"]


class ModeConfig(BaseModel):
    stage1_items: int
    stage2_items: int
    extra_items_max: int
    pilot_slots: int


class Scale(BaseModel):
    cuts: dict[str, float]
    stage_split: float


class Selection(BaseModel):
    window: float
    exposure_cap: float
    exposure_strength: float
    window_step: float
    edge_offset: float
    open_candidates: int


class VerifySkill(BaseModel):
    min_items: int
    min_share: float


class VacancyConfig(BaseModel):
    boost_required: int
    boost_optional: int
    sample_items: int


class SpecBlueprint(BaseModel):
    topics: dict[str, int]


class Blueprints(BaseModel):
    scale: Scale
    modes: dict[str, ModeConfig]
    selection: Selection
    verify_skill: VerifySkill
    open_approach_from_grade: str
    vacancy: VacancyConfig
    topic_names: dict[str, str]
    specializations: dict[str, SpecBlueprint]

    def cut(self, grade: str) -> float:
        return self.scale.cuts[grade]

    def next_grade(self, grade: str) -> str | None:
        index = GRADE_ORDER.index(grade)
        return GRADE_ORDER[index + 1] if index + 1 < len(GRADE_ORDER) else None

    def previous_grade(self, grade: str) -> str | None:
        index = GRADE_ORDER.index(grade)
        return GRADE_ORDER[index - 1] if index > 0 else None


class Bank(BaseModel):
    templates: dict[str, Template] = Field(default_factory=dict)

    def for_spec(self, specialization: str) -> list[Template]:
        return [t for t in self.templates.values() if specialization in t.specializations]


@lru_cache
def get_blueprints() -> Blueprints:
    with (CONTENT_DIR / "blueprints.yaml").open(encoding="utf-8") as file:
        return Blueprints.model_validate(yaml.safe_load(file))


def load_bank(templates_dir: Path | None = None) -> Bank:
    directory = templates_dir or CONTENT_DIR / "templates"
    templates: dict[str, Template] = {}
    duplicates: list[str] = []
    for path in sorted(directory.rglob("*.yaml")):
        with path.open(encoding="utf-8") as file:
            for raw in yaml.safe_load(file) or []:
                template = Template.model_validate(raw)
                if template.id in templates:
                    duplicates.append(template.id)
                templates[template.id] = template
    if duplicates:
        raise ValueError(f"повторяющиеся id шаблонов: {sorted(set(duplicates))}")
    return Bank(templates=templates)


@lru_cache
def get_bank() -> Bank:
    return load_bank()


def validate_bank(bank: Bank, blueprints: Blueprints, skill_ids: set[str], seeds: int = 25) -> list[str]:
    """Проверки, которые гоняет CI: каждый шаблон рендерится, варианты корректны, ссылки существуют."""
    errors: list[str] = []
    generators = load_all()
    for template in bank.templates.values():
        prefix = template.id
        for spec in template.specializations:
            blueprint = blueprints.specializations.get(spec)
            if blueprint is None:
                errors.append(f"{prefix}: специализация {spec} без blueprint")
            elif template.topic not in blueprint.topics and template.kind != "open_approach":
                errors.append(f"{prefix}: тема {template.topic} не входит в blueprint {spec}")
        if template.topic not in blueprints.topic_names:
            errors.append(f"{prefix}: нет названия темы {template.topic} в topic_names")
        errors += [
            f"{prefix}: неизвестный навык {skill}" for skill in template.skills if skill not in skill_ids
        ]
        if template.generator and template.generator not in generators:
            errors.append(f"{prefix}: генератор {template.generator} не зарегистрирован")
            continue
        try:
            first = render(template, 1)
            if render(template, 1) != first:
                errors.append(f"{prefix}: рендер недетерминирован")
            variants = set()
            for seed in range(seeds):
                instance = render(template, seed)
                variants.add((instance.stem, instance.code, tuple(o.text for o in instance.options)))
                if template.kind in CHOICE_KINDS and len(instance.options) != template.n_options:
                    errors.append(
                        f"{prefix}: seed {seed}: вариантов {len(instance.options)} ≠ {template.n_options}"
                    )
                    break
            if len(variants) < 2 and template.kind != "open_approach":
                errors.append(f"{prefix}: все экземпляры одинаковые — нет параметризации")
        except Exception as exc:
            errors.append(f"{prefix}: ошибка рендера: {exc}")
    return errors


def coverage(bank: Bank, blueprints: Blueprints) -> dict[str, Counter]:
    """Сколько активных шаблонов на тему у каждой специализации — для отчёта и проверки объёма."""
    result: dict[str, Counter] = {}
    for spec in blueprints.specializations:
        result[spec] = Counter(t.topic for t in bank.for_spec(spec) if t.status == "active")
    return result
