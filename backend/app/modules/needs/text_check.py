"""Проверка текста потребности на запрещённые требования (§8.1): правила из content/need_text_rules.yaml.

Детерминированные регулярные выражения без LLM: работодатель видит, что именно сработало, и правит текст.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import yaml

from app.core.config import get_settings
from app.modules.catalog.service import CONTENT_DIR
from app.modules.needs.schemas import NeedTextIssue

Severity = Literal["block", "warn"]


@dataclass(frozen=True)
class _Rule:
    id: str
    severity: Severity
    label: str
    message: str
    patterns: tuple[re.Pattern[str], ...]
    unless_before: re.Pattern[str] | None


@dataclass(frozen=True)
class TextIssue:
    rule: str
    severity: Severity
    label: str
    message: str
    fragment: str


@lru_cache
def _rules() -> tuple[int, tuple[_Rule, ...]]:
    with (CONTENT_DIR / "need_text_rules.yaml").open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    rules = tuple(
        _Rule(
            id=item["id"],
            severity=item["severity"],
            label=item["label"],
            message=item["message"],
            patterns=tuple(re.compile(pattern, re.IGNORECASE) for pattern in item["patterns"]),
            unless_before=re.compile(item["unless_before"], re.IGNORECASE)
            if item.get("unless_before")
            else None,
        )
        for item in data["rules"]
    )
    return int(data["context_chars"]), rules


def check_texts(*texts: str | None) -> list[TextIssue]:
    """По одному замечанию на правило: первое найденное совпадение во всех текстах."""
    context, rules = _rules()
    issues = []
    for rule in rules:
        for text in filter(None, texts):
            fragment = _first_match(rule, text, context)
            if fragment:
                issues.append(TextIssue(rule.id, rule.severity, rule.label, rule.message, fragment))
                break
    return issues


def _first_match(rule: _Rule, text: str, context: int) -> str | None:
    for pattern in rule.patterns:
        for match in pattern.finditer(text):
            before = text[max(0, match.start() - context) : match.start()]
            if rule.unless_before and rule.unless_before.search(before):
                continue
            return match.group(0).strip()
    return None


def text_issues(title: str | None, raw_text: str | None, team_description: str | None) -> list[NeedTextIssue]:
    """Пустой список при NEED_TEXT_CHECK=off; иначе замечания по правилам content/need_text_rules.yaml."""
    if get_settings().need_text_check == "off":
        return []
    return [
        NeedTextIssue(rule=i.rule, severity=i.severity, label=i.label, message=i.message, fragment=i.fragment)
        for i in check_texts(title, raw_text, team_description)
    ]
