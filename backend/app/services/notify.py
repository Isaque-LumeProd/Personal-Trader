"""Envio de notificações por Telegram e e-mail (SMTP)."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from ..config import Settings

log = logging.getLogger(__name__)


def channels_available(settings: Settings) -> dict[str, bool]:
    return {
        "telegram": bool(settings.telegram_bot_token),
        "email": bool(settings.smtp_host and (settings.smtp_from or settings.smtp_user)),
    }


async def send_telegram(settings: Settings, chat_id: str, text: str) -> bool:
    if not settings.telegram_bot_token:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
        if resp.status_code != 200:
            log.warning("telegram respondeu %s: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("falha ao enviar telegram: %s", exc)
        return False


def _send_email_sync(settings: Settings, to: str, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:  # type: ignore[arg-type]
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def send_email(settings: Settings, to: str, subject: str, text: str) -> bool:
    if not channels_available(settings)["email"]:
        return False
    try:
        await asyncio.to_thread(_send_email_sync, settings, to, subject, text)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("falha ao enviar e-mail: %s", exc)
        return False
