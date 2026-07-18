import asyncio
import smtplib
from email.message import EmailMessage
from functools import partial

from app.core.config import get_settings


def _smtp_send(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        print(f"[DEV EMAIL] To: {to}\nSubject: {subject}\n{body}\n{'─'*60}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email or settings.smtp_username
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email without blocking the event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, partial(_smtp_send, to, subject, body))
