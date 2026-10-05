"""Стандартный PDF-профиль кандидата (§7, «Экспорт»): HTML-шаблон в стиле брендбука → WeasyPrint.

Две версии: обезличенная (до раскрытия контактов) и полная (после раскрытия и для самого кандидата).
Что попадает в обезличенную версию, решает вызывающий код теми же правилами, что и карточка кандидата;
здесь дополнительно вычищаются контакты из свободного текста («О себе», описания опыта).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import segno
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings
from app.modules.candidates.schemas import Contacts, ExperienceItem, SkillState
from app.modules.catalog.service import get_catalog
from app.modules.fsp.schemas import FspProfileOut
from app.modules.resume import parser
from app.modules.testing.schemas import TopicScore

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
HIDDEN_COMPANY = "Компания скрыта до контакта"
REDACTED = "[контакт скрыт]"
MAX_FSP_ACHIEVEMENTS = 5

Variant = Literal["full", "public"]

FSP_LEVELS = {
    "international": "международный",
    "national": "всероссийский",
    "interregional": "межрегиональный",
    "regional": "региональный",
    "municipal": "муниципальный",
}
WORK_FORMATS = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}
SKILL_STATUS = {
    "verified": "проверено тестом",
    "fsp_confirmed": "подтверждено ФСП",
    "task_confirmed": "подтверждено заданием",
    "declared": "заявлено",
}
_LINK = re.compile(r"(?:https?://|www\.|t\.me/)\S+", re.IGNORECASE)


@dataclass
class TopicRow:
    name: str
    percent: int
    items: int


@dataclass
class ProfileDocument:
    variant: Variant
    candidate_id: int
    name: str
    category_label: str | None
    percentile: float | None
    city: str | None = None
    relocation: bool = False
    work_formats: list[str] = field(default_factory=list)
    salary_min: int | None = None
    experience_years: float | None = None
    contacts: Contacts | None = None
    topics: list[TopicRow] = field(default_factory=list)
    verified_skills: list[str] = field(default_factory=list)
    other_skills: list[tuple[str, str]] = field(default_factory=list)
    fsp_ranks: list[str] = field(default_factory=list)
    fsp_achievements: list[str] = field(default_factory=list)
    fsp_competencies: list[str] = field(default_factory=list)
    experience: list[ExperienceItem] = field(default_factory=list)
    about: str | None = None
    roles: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)


def redact_contacts(text: str | None) -> str | None:
    """Email, телефоны, Telegram и ссылки из свободного текста — до раскрытия контактов их не видно."""
    if not text:
        return text
    for pattern in (parser.EMAIL, _LINK, parser.PHONE, parser.TELEGRAM, parser.TELEGRAM_AT):
        text = pattern.sub(REDACTED, text)
    return text


def display_name(first_name: str | None, last_name: str | None, show_last_name: bool) -> str:
    """Имя и первая буква фамилии — как в обезличенной карточке (§8.1 п.5)."""
    last = last_name or ""
    shown = last if show_last_name else (f"{last[:1]}." if last else "")
    return f"{first_name or 'Кандидат'} {shown}".strip()


def _names(slugs: list[str], items) -> list[str]:
    known = {item.slug: item.name for item in items}
    return [known.get(slug, slug) for slug in slugs]


def labels(roles: list[str], industries: list[str], soft_skills: list[str]) -> dict[str, list[str]]:
    catalog = get_catalog()
    return {
        "roles": _names(roles, catalog.team_roles),
        "industries": _names(industries, catalog.industries),
        "soft_skills": _names(soft_skills, catalog.soft_skills),
    }


def topic_rows(scores: list[TopicScore]) -> list[TopicRow]:
    return [TopicRow(name=item.name, percent=round(item.score * 100), items=item.items) for item in scores]


def skill_groups(skills: list[SkillState]) -> tuple[list[str], list[tuple[str, str]]]:
    verified = [skill.name for skill in skills if skill.status == "verified"]
    others = [(skill.name, SKILL_STATUS[skill.status]) for skill in skills if skill.status != "verified"]
    return verified, others


def fsp_lines(fsp: FspProfileOut | None) -> tuple[list[str], list[str], list[str]]:
    if fsp is None or not fsp.linked:
        return [], [], []
    disciplines = {slug: item.name for slug, item in get_catalog().disciplines.items()}
    ranks = [f"{rank.rank} — {disciplines.get(rank.discipline, rank.discipline)}" for rank in fsp.ranks]
    achievements = []
    for item in fsp.achievements[:MAX_FSP_ACHIEVEMENTS]:
        role = f", роль: {item.team_role}" if item.team_role else ""
        achievements.append(
            f"{item.place} место из {item.participants} — {item.competition_name} "
            f"({FSP_LEVELS.get(item.level, item.level)}, {item.held_on.year}{role})"
        )
    competencies = [f"{item.name} — {round(item.score * 100)}%" for item in fsp.competencies]
    return ranks, achievements, competencies


def experience_for(items: list[ExperienceItem], variant: Variant) -> list[ExperienceItem]:
    if variant == "full":
        return items
    return [
        item.model_copy(update={"company": HIDDEN_COMPANY, "description": redact_contacts(item.description)})
        for item in items
    ]


def profile_url(candidate_id: int) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/employer/candidates/{candidate_id}"


def _format_money(value: int | None) -> str:
    return f"{value:,}".replace(",", " ") if value is not None else ""


def _format_period(item: ExperienceItem) -> str:
    start = item.started_on.strftime("%m.%Y") if item.started_on else "…"
    end = item.ended_on.strftime("%m.%Y") if item.ended_on else "н. в."
    return f"{start} — {end}"


def _plural(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def _years(value: float | None) -> str:
    """Стаж «3 года 5 мес.»: дробные годы из опроса и резюме показываем в годах и месяцах."""
    if value is None:
        return ""
    months = round(float(value) * 12)
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} {_plural(years, 'год', 'года', 'лет')}")
    if rest:
        parts.append(f"{rest} мес.")
    return " ".join(parts) or "меньше месяца"


@lru_cache
def _environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(ASSETS_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["money"] = _format_money
    environment.filters["period"] = _format_period
    environment.filters["years"] = _years
    return environment


def render_html(document: ProfileDocument, today: date | None = None) -> str:
    url = profile_url(document.candidate_id)
    qr = segno.make(url, error="m").svg_data_uri(scale=3, border=0, dark="#1B1C21")
    return (
        _environment()
        .get_template("profile.html")
        .render(
            doc=document,
            formats=[WORK_FORMATS.get(item, item) for item in document.work_formats],
            url=url,
            qr=qr,
            today=(today or date.today()).strftime("%d.%m.%Y"),
        )
    )


def render_pdf(document: ProfileDocument) -> bytes:
    """HTML → PDF. Синхронно и тяжело для CPU — вызывать из пула потоков."""
    # WeasyPrint тянет pango/cairo через cffi: импорт здесь, чтобы приложение стартовало и без них
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    font_config = FontConfiguration()
    html = HTML(string=render_html(document), base_url=str(ASSETS_DIR))
    return html.write_pdf(font_config=font_config)


def pdf_filename(document: ProfileDocument) -> str:
    suffix = "" if document.variant == "full" else "-public"
    return f"itscout-profile-{document.candidate_id}{suffix}.pdf"
