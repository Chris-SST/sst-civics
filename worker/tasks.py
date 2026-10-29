"""Job functions. Each takes the arq context as its first argument."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.auth.sessions import purge_expired_sessions
from app.billing import stripe_client
from app.billing.events import apply_subscription, handle_event
from app.db import SessionLocal, utcnow
from app.email import backend, messages
from app.models import Family, GenerationBatch, StripeEvent
from app.questions import pipeline

log = logging.getLogger(__name__)


async def send_email(
    ctx: dict[str, Any], kind: str, locale: str, to: str, params: dict[str, str]
) -> None:
    backend.send(messages.build(kind, locale, to, **params))


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


async def reconcile_subscriptions(ctx: dict[str, Any]) -> int:
    """Nightly: re-read every subscription from Stripe so missed webhooks heal."""
    updated = 0
    async with SessionLocal() as db:
        families = (
            (await db.execute(select(Family).where(Family.stripe_subscription_id.is_not(None))))
            .scalars()
            .all()
        )
        for family in families:
            try:
                sub = stripe_client.retrieve_subscription(family.stripe_subscription_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("Reconcile: could not fetch subscription: %s", exc.__class__.__name__)
                continue
            apply_subscription(family, sub)
            updated += 1
        await db.commit()
    log.info("Reconciled %d subscriptions", updated)
    return updated


async def purge_sessions(ctx: dict[str, Any]) -> int:
    async with SessionLocal() as db:
        n = await purge_expired_sessions(db)
        await db.commit()
    return n


async def generate_questions_direct(ctx: dict[str, Any], batch_id: str) -> int:
    """Direct-mode generation: one provider call per topic and difficulty, with checks."""
    import uuid

    async with SessionLocal() as db:
        batch = await db.get(GenerationBatch, uuid.UUID(batch_id))
        if batch is None or batch.status != "submitted":
            return 0
        batch.status = "running"
        await db.commit()
        try:
            n = await pipeline.generate_direct(db, batch)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            batch = await db.get(GenerationBatch, uuid.UUID(batch_id))
            if batch is not None:
                batch.status = "failed"
                batch.error = f"{exc.__class__.__name__}: {exc}"[:2000]
                await db.commit()
            log.exception("Direct generation failed for batch %s", batch_id)
            return 0
    log.info("Generated %d questions for batch %s", n, batch_id)
    return n


async def poll_generation_batches(ctx: dict[str, Any]) -> int:
    """Every 10 minutes: fetch results of provider batches that have ended."""
    processed = 0
    async with SessionLocal() as db:
        batches = (
            (
                await db.execute(
                    select(GenerationBatch).where(
                        GenerationBatch.mode == "batch",
                        GenerationBatch.status == "submitted",
                        GenerationBatch.provider_batch_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for batch in batches:
            try:
                n = await pipeline.process_batch(db, batch)
                if n or batch.status == "processed":
                    processed += 1
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                log.warning("Polling batch %s failed: %s", batch.id, exc.__class__.__name__)
    return processed
