"""Job functions. Each takes the arq context as its first argument."""

from __future__ import annotations

import logging
import smtplib
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


# A failed send (mail server down, connection refused, rate limit) is tried again after
# 10 s, 30 s, 1 min and 2 min, within the worker's max_tries (5). Every email goes through
# send_email, sign-in links included, and those are waited for, so the first retries are
# quick. Inline jobs (tests, dev) raise the error instead.
SEND_RETRY_SECONDS = (10, 30, 60, 120)


def retry_send(ctx: dict[str, Any], exc: Exception) -> None:
    tries = ctx.get("job_try")
    if not tries:
        raise exc
    from arq import Retry

    log.warning("Email send failed (try %s): %s", tries, exc.__class__.__name__)
    delay = SEND_RETRY_SECONDS[min(tries, len(SEND_RETRY_SECONDS)) - 1]
    raise Retry(defer=delay) from exc


async def send_email(
    ctx: dict[str, Any], kind: str, locale: str, to: str, params: dict[str, str]
) -> None:
    try:
        backend.send(messages.build(kind, locale, to, **params))
    except (smtplib.SMTPException, OSError) as exc:
        retry_send(ctx, exc)


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


async def check_source_links(ctx: dict[str, Any]) -> int:
    """Weekly: HEAD or GET every source cited by a question file (no AI). Questions with a
    broken link get `file_sync_pending` and a report is written (app/content/links.py).
    Returns the number of broken URLs."""
    from app.content.links import run_link_check

    async with SessionLocal() as db:
        report = await run_link_check(db)
    return len(report.broken)


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


async def send_daily_digest(ctx: dict[str, Any]) -> int:
    """Daily: the owner's operations digest (app/ops/digest.py, D-072). Returns the number
    of emails sent; 0 when switched off with DIGEST_ENABLED=false."""
    from app.config import get_settings
    from app.ops.digest import run_digest

    if not get_settings().digest_enabled:
        return 0
    try:
        async with SessionLocal() as db:
            _, emails = await run_digest(db)
    except (smtplib.SMTPException, OSError) as exc:
        retry_send(ctx, exc)
        return 0
    return len(emails)


# --- Article pipeline (D-073, app/articles/) -----------------------------------------------


async def articles_tick(ctx: dict[str, Any]) -> int:
    """Every 15 minutes: import the plan, start due productions, send due proposals and
    start due publications (app/articles/workflow.py). Production and publication run as
    their own jobs. Returns the number of actions; 0 when ARTICLES_ENABLED is false."""
    from app.articles.workflow import tick
    from app.config import get_settings

    if not get_settings().articles_enabled:
        return 0
    redis = ctx.get("redis")

    async def run(job: str, key: str) -> None:
        # One queued or running job per article and step (arq refuses a second job id).
        await redis.enqueue_job(job, key, _job_id=f"{job}:{key}")

    async with SessionLocal() as db:
        report = await tick(db, run=run if redis is not None else None)
    return len(report.actions)


async def produce_article(ctx: dict[str, Any], key: str) -> str | None:
    """Write, fact-check and translate one article (long job, no automatic retry: the
    claim in the database keeps a second run of the same article from starting)."""
    from app.articles.workflow import get_by_key, run_production
    from app.config import get_settings

    if not get_settings().articles_enabled:
        return None
    async with SessionLocal() as db:
        article = await get_by_key(db, key)
        if article is None:
            return None
        return await run_production(db, article)


async def publish_article(ctx: dict[str, Any], key: str) -> str | None:
    """Write the files of an approved article, request the build and wait for it."""
    from app.articles.workflow import get_by_key, run_publication
    from app.config import get_settings

    if not get_settings().articles_enabled:
        return None
    async with SessionLocal() as db:
        article = await get_by_key(db, key)
        if article is None:
            return None
        return await run_publication(db, article)
