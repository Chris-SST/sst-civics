"""Job functions. Each takes the arq context as its first argument."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.auth import email_link, one_time
from app.auth.sessions import purge_expired_sessions
from app.billing.events import handle_event
from app.db import SessionLocal, utcnow
from app.email import backend, messages
from app.models import Entitlement, StripeEvent

log = logging.getLogger(__name__)


async def send_email(
    ctx: dict[str, Any], kind: str, locale: str, to: str, params: dict[str, str]
) -> None:
    backend.send(messages.build(kind, locale, to, **params))


async def send_sign_in_link(
    ctx: dict[str, Any], email: str, locale: str, next_path: str | None = None
) -> None:
    """Look up the address and email a sign-in link if it has an account (see
    app/auth/email_link.py). Never logs the address."""
    async with SessionLocal() as db:
        await email_link.send_sign_in_link(db, email, locale, next_path)


async def process_stripe_event(ctx: dict[str, Any], event_id: str) -> None:
    async with SessionLocal() as db:
        row = await db.get(StripeEvent, event_id)
        if row is None:
            log.warning("Stripe event %s not found", event_id)
            return
        if row.processed_at is not None:
            return
        try:
            await handle_event(db, row.payload)
            row.processed_at = utcnow()
            row.error = None
            await db.commit()
        except Exception as exc:
            await db.rollback()
            row = await db.get(StripeEvent, event_id)
            if row is not None:
                row.error = f"{exc.__class__.__name__}: {exc}"[:2000]
                await db.commit()
            log.exception("Failed to process Stripe event %s", event_id)
            from arq import Retry

            raise Retry(defer=ctx.get("job_try", 1) * 60) from exc


async def purge_sessions(ctx: dict[str, Any]) -> int:
    """Hourly: expired sessions, and one-time tokens expired more than a day ago."""
    async with SessionLocal() as db:
        n = await purge_expired_sessions(db)
        n += await one_time.purge_old_tokens(db)
        await db.commit()
    return n


async def log_expiring_entitlements(ctx: dict[str, Any]) -> int:
    """Nightly: count the entitlements that end in the next 7 days. Changes nothing and
    sends nothing; the number is the basis for a later reminder email."""
    now = utcnow()
    async with SessionLocal() as db:
        n = await db.scalar(
            select(func.count())
            .select_from(Entitlement)
            .where(Entitlement.expires_at > now, Entitlement.expires_at <= now + timedelta(days=7))
        )
    log.info("Entitlements expiring in the next 7 days: %d", n or 0)
    return int(n or 0)
