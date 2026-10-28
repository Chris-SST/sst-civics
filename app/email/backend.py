"""Email backends. `console` writes .eml files to a local outbox and logs the subject,
`smtp` sends through any SMTP provider, `memory` collects messages for tests."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

from app.config import get_settings
from app.db import utcnow

log = logging.getLogger(__name__)


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str | None = None


@dataclass
class MemoryOutbox:
    messages: list[OutgoingEmail] = field(default_factory=list)

    def clear(self) -> None:
        self.messages.clear()


memory_outbox = MemoryOutbox()


def _build(msg: OutgoingEmail) -> EmailMessage:
    settings = get_settings()
    em = EmailMessage()
    em["From"] = settings.email_from
    em["To"] = msg.to
    em["Subject"] = msg.subject
    em.set_content(msg.text)
    if msg.html:
        em.add_alternative(msg.html, subtype="html")
    return em


def send(msg: OutgoingEmail) -> None:
    settings = get_settings()
    backend = settings.email_backend
    if backend == "memory":
        memory_outbox.messages.append(msg)
        return
    if backend == "console":
        out = Path(settings.email_outbox_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = utcnow().strftime("%Y%m%d-%H%M%S-%f")
        path = out / f"{stamp}.eml"
        path.write_bytes(_build(msg).as_bytes())
        # Log the recipient domain and subject only; never the body.
        log.info("Email to *@%s: %s -> %s", msg.to.split("@")[-1], msg.subject, path)
        return
    if backend == "smtp":
        em = _build(msg)
        context = ssl.create_default_context()
        if settings.smtp_starttls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                s.starttls(context=context)
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(em)
        else:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=context, timeout=20
            ) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(em)
        log.info("Email sent to *@%s: %s", msg.to.split("@")[-1], msg.subject)
        return
    raise ValueError(f"Unknown email backend {backend}")
