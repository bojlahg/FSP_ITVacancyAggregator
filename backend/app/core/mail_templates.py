"""Шаблоны писем: текст и простой HTML из одного описания (docs/implementation.md §8.9).

Контактов кандидата в письмах нет: работодатель видит их только в кабинете после записи в contact_unlocks.
"""

from html import escape

from app.core.config import get_settings
from app.core.mail import Mail

SETTINGS_PATH = {"candidate": "/candidate/settings", "employer": "/employer/company"}


def link(path: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}{path}"


def _one_line(value: str) -> str:
    """Пользовательский текст в теме и строках письма — без переводов строк."""
    return " ".join(value.split())


def _rubles(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def salary_range(salary_from: int, salary_to: int) -> str:
    return f"{_rubles(salary_from)} – {_rubles(salary_to)} ₽"


def _compose(
    to: str,
    subject: str,
    paragraphs: list[str],
    action_path: str,
    action_label: str,
    settings_path: str | None,
) -> Mail:
    url = link(action_path)
    footer = f"Отключить уведомления можно в настройках: {link(settings_path)}" if settings_path else None
    text_parts = ["Здравствуйте!", *paragraphs, f"{action_label}: {url}"]
    if footer:
        text_parts += ["—", footer]
    html_parts = [
        "<p>Здравствуйте!</p>",
        *(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs),
        f'<p><a href="{escape(url)}" style="display:inline-block;padding:10px 18px;border-radius:6px;'
        f'background:#1B1C21;color:#FFFFFF;text-decoration:none">{escape(action_label)}</a></p>',
    ]
    if footer:
        settings_url = escape(link(settings_path or ""))
        html_parts.append(
            '<p style="margin-top:24px;color:#6B6C70;font-size:12px">'
            f'Отключить уведомления можно в <a href="{settings_url}">настройках</a>.</p>'
        )
    html = (
        '<div style="font-family:Inter,Arial,sans-serif;font-size:14px;line-height:1.5;color:#1B1C21;'
        f'max-width:560px">{"".join(html_parts)}<p style="color:#6B6C70;font-size:12px">ITScout</p></div>'
    )
    return Mail(to=to, subject=f"ITScout: {_one_line(subject)}", text="\n\n".join(text_parts), html=html)


def verification(to: str, url_path: str, ttl_hours: int) -> Mail:
    return _compose(
        to,
        "подтвердите почту",
        [
            "Подтвердите адрес почты для ITScout, перейдя по ссылке.",
            f"Ссылка действует {ttl_hours} ч. Если вы не регистрировались — просто проигнорируйте письмо.",
        ],
        url_path,
        "Подтвердить почту",
        settings_path=None,
    )


def invitation_received(to: str, company: str, title: str, salary_from: int, salary_to: int) -> Mail:
    company, title = _one_line(company), _one_line(title)
    return _compose(
        to,
        f"приглашение от {company}",
        [
            f"Компания {company} приглашает вас: «{title}».",
            f"Вилка: {salary_range(salary_from, salary_to)} в месяц.",
            "Примите или отклоните приглашение в кабинете: работодатель увидит ваши контакты "
            "только после принятия.",
        ],
        "/candidate/invitations",
        "Открыть приглашения",
        SETTINGS_PATH["candidate"],
    )


def invitation_withdrawn(to: str, company: str, title: str) -> Mail:
    company, title = _one_line(company), _one_line(title)
    return _compose(
        to,
        f"{company} отозвала приглашение",
        [f"Компания {company} отозвала приглашение «{title}». Отвечать на него больше не нужно."],
        "/candidate/invitations",
        "Открыть приглашения",
        SETTINGS_PATH["candidate"],
    )


def invitation_accepted(to: str, candidate_name: str, title: str, candidate_id: int) -> Mail:
    name, title = _one_line(candidate_name), _one_line(title)
    return _compose(
        to,
        f"{name} принял(а) приглашение",
        [
            f"Кандидат {name} принял(а) приглашение «{title}».",
            "Контакты кандидата открыты в карточке в кабинете.",
        ],
        f"/employer/candidates/{candidate_id}",
        "Открыть карточку кандидата",
        SETTINGS_PATH["employer"],
    )


def invitation_declined(to: str, candidate_name: str, title: str, reason: str) -> Mail:
    name, title = _one_line(candidate_name), _one_line(title)
    return _compose(
        to,
        f"{name} отклонил(а) приглашение",
        [
            f"Кандидат {name} отклонил(а) приглашение «{title}».",
            f"Причина: {reason}. Сводка причин отказов — в разделе приглашений.",
        ],
        "/employer/invitations",
        "Открыть приглашения",
        SETTINGS_PATH["employer"],
    )


def application_received(
    to: str, candidate_name: str, vacancy_title: str, candidate_id: int, need_id: int
) -> Mail:
    name, title = _one_line(candidate_name), _one_line(vacancy_title)
    return _compose(
        to,
        f"новый отклик на «{title}»",
        [
            f"Кандидат {name} откликнулся на вакансию «{title}».",
            "Карточка, совпадение и контакты кандидата — в кабинете.",
        ],
        f"/employer/candidates/{candidate_id}?need={need_id}",
        "Открыть карточку кандидата",
        SETTINGS_PATH["employer"],
    )


def debug_test(to: str) -> Mail:
    return _compose(
        to,
        "проверка почты",
        ["Это тестовое письмо из отладочного раздела ITScout: доставка почты работает."],
        "/",
        "Открыть ITScout",
        settings_path=None,
    )
