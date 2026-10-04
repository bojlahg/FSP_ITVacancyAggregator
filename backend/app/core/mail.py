import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

log = logging.getLogger("itscout.mail")


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    async def send(self, mail: Mail) -> None: ...


class ConsoleSender:
    """Письма в лог — пока домен в Unisender не подтверждён."""

    async def send(self, mail: Mail) -> None:
        log.warning("EMAIL to=%s subject=%s\n%s", mail.to, mail.subject, mail.text)


class SmtpSender:
    """SMTP: Mailpit в dev; в проде — почтовый ящик через SSL (465) или STARTTLS (587) с логином."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _send_sync(self, mail: Mail) -> None:
        settings = self._settings
        message = EmailMessage()
        message["From"] = f"{settings.email_from_name} <{settings.email_from}>"
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.text)
        message.add_alternative(mail.html, subtype="html")
        context = ssl.create_default_context()
        if settings.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=context)
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)

    async def send(self, mail: Mail) -> None:
        await asyncio.to_thread(self._send_sync, mail)


class UnisenderSender:
    """Unisender Go transactional API (HTTPS) — §20."""

    def __init__(self, settings: Settings):
        self._settings = settings

    async def send(self, mail: Mail) -> None:
        payload = {
            "message": {
                "recipients": [{"email": mail.to}],
                "subject": mail.subject,
                "from_email": self._settings.email_from,
                "from_name": self._settings.email_from_name,
                "body": {"html": mail.html, "plaintext": mail.text},
                "track_links": 0,
                "track_read": 0,
            }
        }
        url = self._settings.unisender_api_url.rstrip("/") + "/email/send.json"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url, json=payload, headers={"X-API-KEY": self._settings.unisender_api_key}
            )
            response.raise_for_status()


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.email_backend == "smtp":
        return SmtpSender(settings)
    if settings.email_backend == "unisender":
        return UnisenderSender(settings)
    return ConsoleSender()


async def send_safely(mail: Mail) -> None:
    """Для BackgroundTasks: сбой почты не должен ронять запрос пользователя."""
    try:
        await get_email_sender().send(mail)
    except Exception:
        log.exception("failed to send email to %s", mail.to)
