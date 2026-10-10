"""Outbound e-mail abstraction.

Only SMTP is implemented. Without SMTP configuration:
* development/test: the message is written to the application log (marked as
  NOT SENT) so password recovery can be exercised locally;
* production: sending fails loudly and the caller reports that e-mail delivery
  is not configured instead of pretending it succeeded.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

log = logging.getLogger("app.email")


class EmailNotConfigured(RuntimeError):
    pass


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str


# Messages captured in development/test (inspected by tests; never persisted).
DEV_OUTBOX: list[OutgoingEmail] = []


def send_email(message: OutgoingEmail) -> None:
    settings = get_settings()
    if settings.smtp_host and settings.smtp_from:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return
    if settings.environment in ("development", "test"):
        DEV_OUTBOX.append(message)
        if settings.environment == "development":
            # The body may contain a one-time link; this branch only exists in development.
            print(f"\n[DEV E-MAIL — NOT SENT] To: {message.to}\nSubject: {message.subject}\n{message.body}\n", flush=True)
        return
    raise EmailNotConfigured("SMTP no está configurado.")
