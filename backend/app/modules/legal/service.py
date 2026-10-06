"""Юридические документы (§13.1): тексты в content/legal/*.yaml, числа подставляются из тех же
настроек, что использует код подбора и теста, — правила рекомендаций не расходятся с расчётом."""

from functools import lru_cache
from typing import Any, get_args

import yaml

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.modules.catalog.service import CONTENT_DIR
from app.modules.legal.schemas import LegalDocument, LegalDocumentRef, LegalSlug
from app.modules.matching.scoring import get_rules
from app.modules.testing.engine.bank import get_blueprints

SLUGS: tuple[str, ...] = get_args(LegalSlug)


def _num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",").replace("-", "−")


def placeholders() -> dict[str, str]:
    settings = get_settings()
    rules = get_rules()
    weights, fit, value = rules.weights, rules.category_fit, rules.skill_value
    cuts = get_blueprints().scale.cuts
    return {
        "operator": settings.legal_operator,
        "contact_email": settings.legal_contact_email,
        **{f"w_{name}": _num(weight) for name, weight in weights.items()},
        **{f"vps_{name}": _num(weight) for name, weight in rules.vps_weights.items()},
        **{f"cut_{grade}": _num(cut, 1) for grade, cut in cuts.items()},
        "fit_exact": _num(fit["exact"]),
        "fit_adj_spec": _num(fit["adjacent_specialization"]),
        "fit_adj_grade": _num(fit["adjacent_grade"]),
        "fit_adj_both": _num(fit["adjacent_both"]),
        "fit_unconfirmed": _num(fit["unconfirmed"]),
        "sv_verified": _num(value["verified"], 1),
        "sv_fsp": _num(value["fsp_confirmed"], 1),
        "sv_declared": _num(value["declared"], 1),
        "sv_parent": _num(value["parent_only"], 1),
        "required_weight": _num(rules.required_weight, 1),
        "optional_weight": _num(rules.optional_weight, 1),
        "ability_share": _num(rules.strength["ability_share"], 1),
        "topic_share": _num(1 - rules.strength["ability_share"], 1),
        "half_life_days": str(int(rules.freshness["half_life_days"])),
        "salary_share": _num(rules.conditions["salary_share"], 1),
        "format_share": _num(rules.conditions["format_share"], 1),
        "salary_tolerance_pct": str(round(rules.conditions["salary_tolerance"] * 100)),
    }


def _fill(node: Any, values: dict[str, str]) -> Any:
    if isinstance(node, str):
        return node.format_map(values)
    if isinstance(node, list):
        return [_fill(item, values) for item in node]
    if isinstance(node, dict):
        return {key: _fill(item, values) for key, item in node.items()}
    return node


@lru_cache
def _raw(slug: str) -> dict[str, Any]:
    with (CONTENT_DIR / "legal" / f"{slug}.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def list_documents() -> list[LegalDocumentRef]:
    return [LegalDocumentRef(slug=slug, title=_raw(slug)["title"]) for slug in SLUGS]


def get_document(slug: str) -> LegalDocument:
    if slug not in SLUGS:
        raise NotFoundError("Документ не найден", code="legal_document_not_found")
    data = _fill(_raw(slug), placeholders())
    return LegalDocument(slug=slug, version=get_settings().policy_version, **data)
