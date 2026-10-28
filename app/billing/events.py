"""Apply Stripe webhook events to our records. Called from the background worker and
from the nightly reconciliation. Every handler is idempotent."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import plans, stripe_client
from app.db import utcnow
from app.email.messages import app_link
from app.jobs import send_email_job
from app.models import PAYER_ROLES, Family, Payment, User

log = logging.getLogger(__name__)


def _ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value else None


async def _family_by_customer(db: AsyncSession, customer_id: str | None) -> Family | None:
    if not customer_id:
        return None
    result = await db.execute(select(Family).where(Family.stripe_customer_id == customer_id))
    return result.scalar_one_or_none()


async def _family_by_subscription(db: AsyncSession, sub_id: str | None) -> Family | None:
    if not sub_id:
        return None
    result = await db.execute(select(Family).where(Family.stripe_subscription_id == sub_id))
    return result.scalar_one_or_none()


async def _family_by_id(db: AsyncSession, family_id: str | None) -> Family | None:
    if not family_id:
        return None
    try:
        return await db.get(Family, uuid.UUID(family_id))
    except ValueError:
        return None


async def _payer(db: AsyncSession, family: Family) -> User | None:
    result = await db.execute(
        select(User).where(User.family_id == family.id, User.role.in_(PAYER_ROLES))
    )
    return result.scalars().first()


def apply_subscription(family: Family, sub: dict[str, Any]) -> None:
    """Copy plan, quantity, status and period end from a Stripe subscription object."""
    items = (sub.get("items") or {}).get("data") or []
    first = items[0] if items else {}
    price = first.get("price") or {}
    lookup = price.get("lookup_key") or (sub.get("metadata") or {}).get("plan_key")
    family.stripe_subscription_id = sub["id"]
    if lookup:
        family.plan_key = lookup
    family.quantity = int(first.get("quantity") or 1)
    family.subscription_status = sub.get("status")
    # Newer API versions keep the period on the item, older ones on the subscription.
    family.current_period_end = _ts(
        first.get("current_period_end") or sub.get("current_period_end")
    )
    family.trial_end = _ts(sub.get("trial_end"))
    family.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    if family.subscription_status == "past_due":
        family.past_due_since = family.past_due_since or utcnow()
    elif family.subscription_status in ("active", "trialing"):
        family.past_due_since = None
        family.payment_warning = False


async def handle_event(db: AsyncSession, event: dict[str, Any]) -> None:
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    handler = HANDLERS.get(etype)
    if handler is None:
        log.info("Ignoring Stripe event type %s", etype)
        return
    await handler(db, obj)


async def on_checkout_completed(db: AsyncSession, session: dict[str, Any]) -> None:
    meta = session.get("metadata") or {}
    family = await _family_by_id(db, session.get("client_reference_id") or meta.get("family_id"))
    if family is None:
        family = await _family_by_customer(db, session.get("customer"))
    if family is None:
        log.warning("Checkout session without a matching family")
        return
    if session.get("customer"):
        family.stripe_customer_id = session["customer"]
    if session.get("mode") == "subscription" and session.get("subscription"):
        sub_id = session["subscription"]
        family.stripe_subscription_id = sub_id
        if meta.get("plan_key"):
            family.plan_key = meta["plan_key"]
        try:
            apply_subscription(family, stripe_client.retrieve_subscription(sub_id))
        except Exception as exc:  # noqa: BLE001
            # The subscription.created event will fill in the rest.
            log.warning("Could not fetch subscription after checkout: %s", exc.__class__.__name__)
    elif session.get("mode") == "payment":
        plan_key = meta.get("plan_key")
        quantity = int(meta.get("quantity") or 1)
        if plan_key == plans.ASK_TUTOR_SINGLE:
            family.tutor_credits += quantity
        elif plan_key == plans.EXAM_SPRINT:
            family.exam_sprint_purchased_at = utcnow()


async def on_subscription_changed(db: AsyncSession, sub: dict[str, Any]) -> None:
    family = await _family_by_subscription(db, sub.get("id"))
    if family is None:
        family = await _family_by_customer(db, sub.get("customer"))
    if family is None:
        family = await _family_by_id(db, (sub.get("metadata") or {}).get("family_id"))
    if family is None:
        log.warning("Subscription event without a matching family")
        return
    apply_subscription(family, sub)


async def on_subscription_deleted(db: AsyncSession, sub: dict[str, Any]) -> None:
    family = await _family_by_subscription(db, sub.get("id"))
    if family is None:
        return
    family.subscription_status = "canceled"
    family.cancel_at_period_end = False
    family.current_period_end = (
        _ts(sub.get("ended_at") or sub.get("current_period_end")) or family.current_period_end
    )


async def on_trial_will_end(db: AsyncSession, sub: dict[str, Any]) -> None:
    family = await _family_by_subscription(db, sub.get("id"))
    if family is None:
        return
    payer = await _payer(db, family)
    if payer and payer.email:
        await send_email_job(
            "trial_ending", payer.locale, payer.email, link=app_link("/parent/billing")
        )


async def on_invoice_paid(db: AsyncSession, invoice: dict[str, Any]) -> None:
    family = await _family_by_customer(db, invoice.get("customer"))
    if family is None:
        return
    existing = await db.execute(select(Payment).where(Payment.stripe_invoice_id == invoice["id"]))
    if existing.scalar_one_or_none() is None:
        db.add(
            Payment(
                family_id=family.id,
                stripe_invoice_id=invoice["id"],
                amount_cents=int(invoice.get("amount_paid") or 0),
                currency=(invoice.get("currency") or "chf").lower(),
                paid_at=_ts(
                    ((invoice.get("status_transitions") or {}).get("paid_at"))
                    or invoice.get("created")
                )
                or utcnow(),
            )
        )
    family.payment_warning = False
    family.past_due_since = None


async def on_invoice_payment_failed(db: AsyncSession, invoice: dict[str, Any]) -> None:
    family = await _family_by_customer(db, invoice.get("customer"))
    if family is None:
        return
    family.payment_warning = True
    family.past_due_since = family.past_due_since or utcnow()
    payer = await _payer(db, family)
    if payer and payer.email:
        await send_email_job(
            "payment_failed", payer.locale, payer.email, link=app_link("/parent/billing")
        )


HANDLERS = {
    "checkout.session.completed": on_checkout_completed,
    "customer.subscription.created": on_subscription_changed,
    "customer.subscription.updated": on_subscription_changed,
    "customer.subscription.deleted": on_subscription_deleted,
    "customer.subscription.trial_will_end": on_trial_will_end,
    "invoice.paid": on_invoice_paid,
    "invoice.payment_failed": on_invoice_payment_failed,
}
