"""Запрещённые требования в тексте потребности (§8.1): правила content/need_text_rules.yaml."""

from app.core.config import get_settings
from app.core.text_rules import check_texts
from app.modules.needs.schemas import NeedTextIssue

RULES_FILE = "need_text_rules.yaml"


def text_issues(title: str | None, raw_text: str | None, team_description: str | None) -> list[NeedTextIssue]:
    """Пустой список при NEED_TEXT_CHECK=off; иначе замечания по правилам content/need_text_rules.yaml."""
    if get_settings().need_text_check == "off":
        return []
    return [
        NeedTextIssue(rule=i.rule, severity=i.severity, label=i.label, message=i.message, fragment=i.fragment)
        for i in check_texts(RULES_FILE, title, raw_text, team_description)
    ]
