"""Справочники из backend/content/*.yaml (§5): валидируются при загрузке, ошибка роняет старт."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from app.core.enums import Grade

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"

SkillFamily = Literal[
    "language",
    "backend",
    "frontend",
    "mobile",
    "data",
    "ml",
    "devops",
    "qa",
    "database",
    "messaging",
    "architecture",
    "security",
    "tools",
    "analysis",
    "gamedev",
]


class Specialization(BaseModel):
    slug: str
    name: str
    short_name: str = Field(description="Для меток категорий: «Backend · Middle»")
    has_test: bool
    adjacent: list[str] = Field(default_factory=list)
    description: str = ""
    stack_modules: list[str] = Field(default_factory=list)


class GradeItem(BaseModel):
    slug: Grade
    name: str
    order: int
    experience_hint: str = ""


class Skill(BaseModel):
    id: str
    name: str
    family: SkillFamily
    parent: str | None = None
    aliases: list[str] = Field(default_factory=list)


class Named(BaseModel):
    slug: str
    name: str


class Competency(BaseModel):
    id: str
    name: str
    description: str = ""


class RoleLink(BaseModel):
    competencies: list[str]
    supports_family: SkillFamily | None = None


class Discipline(BaseModel):
    name: str
    direct: list[str] = Field(default_factory=list)
    by_role: dict[str, RoleLink] = Field(default_factory=dict)


class FspRules(BaseModel):
    level_weight: dict[str, float]
    recency_half_life_years: float
    role_link_factor: float
    rank_floor: dict[str, float]
    rank_order: list[str]


class Rules(BaseModel):
    fsp: FspRules


class Catalog(BaseModel):
    specializations: list[Specialization]
    grades: list[GradeItem]
    skills: list[Skill]
    industries: list[Named]
    soft_skills: list[Named]
    team_roles: list[Named]
    competencies: list[Competency]
    disciplines: dict[str, Discipline]
    competency_relevance: dict[str, dict[str, float]]
    rules: Rules

    @model_validator(mode="after")
    def check_references(self) -> "Catalog":
        errors: list[str] = []
        for label, ids in (
            ("specialization", [item.slug for item in self.specializations]),
            ("skill", [item.id for item in self.skills]),
            ("industry", [item.slug for item in self.industries]),
            ("competency", [item.id for item in self.competencies]),
        ):
            duplicates = {value for value in ids if ids.count(value) > 1}
            if duplicates:
                errors.append(f"duplicate {label} ids: {sorted(duplicates)}")

        spec_slugs = {item.slug for item in self.specializations}
        skill_ids = {item.id for item in self.skills}
        competency_ids = {item.id for item in self.competencies}

        for spec in self.specializations:
            errors += [
                f"{spec.slug}: unknown adjacent {slug}" for slug in spec.adjacent if slug not in spec_slugs
            ]
        for skill in self.skills:
            if skill.parent and skill.parent not in skill_ids:
                errors.append(f"skill {skill.id}: unknown parent {skill.parent}")

        owners: dict[str, str] = {}
        for skill in self.skills:
            for alias in {*skill.aliases, skill.id, skill.name.lower()}:
                owner = owners.setdefault(alias, skill.id)
                if owner != skill.id:
                    errors.append(f"alias '{alias}' used by {owner} and {skill.id}")

        for slug, discipline in self.disciplines.items():
            linked = [
                *discipline.direct,
                *(c for link in discipline.by_role.values() for c in link.competencies),
            ]
            errors += [
                f"discipline {slug}: unknown competency {c}" for c in linked if c not in competency_ids
            ]
        for spec, weights in self.competency_relevance.items():
            if spec not in spec_slugs:
                errors.append(f"competency_relevance: unknown specialization {spec}")
            errors += [
                f"competency_relevance.{spec}: unknown {c}" for c in weights if c not in competency_ids
            ]

        if errors:
            raise ValueError("Ошибки в справочниках backend/content:\n" + "\n".join(errors))
        return self

    def skill_aliases(self) -> dict[str, str]:
        """alias (lowercase) → skill id; основа словарного матчера (§9.2 / T08)."""
        index: dict[str, str] = {}
        for skill in self.skills:
            for alias in {*skill.aliases, skill.id, skill.name.lower()}:
                index[alias.lower()] = skill.id
        return index


def _read(name: str):
    with (CONTENT_DIR / name).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


@lru_cache
def get_catalog() -> Catalog:
    return Catalog(
        specializations=_read("specializations.yaml"),
        grades=_read("grades.yaml"),
        skills=_read("skills.yaml"),
        industries=_read("industries.yaml"),
        soft_skills=_read("soft_skills.yaml"),
        team_roles=_read("team_roles.yaml"),
        competencies=_read("competencies.yaml"),
        disciplines=_read("discipline_map.yaml"),
        competency_relevance=_read("competency_relevance.yaml"),
        rules=_read("rules.yaml"),
    )


def search_skills(query: str | None, family: str | None) -> list[Skill]:
    skills = get_catalog().skills
    if family:
        skills = [skill for skill in skills if skill.family == family]
    if query:
        needle = query.strip().lower()
        skills = [
            skill
            for skill in skills
            if needle in skill.name.lower() or any(needle in alias for alias in skill.aliases)
        ]
    return sorted(skills, key=lambda skill: skill.name.lower())
