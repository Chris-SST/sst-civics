"""Apply Stripe webhook events to our records. Called from the background worker. Every
handler is idempotent.

TODO(task 0.7): one-off Civics Pass checkout. `checkout.session.completed` must grant an
`Entitlement` for the canton in the line item's price lookup key. The subscription handlers
of the source app were removed with the subscription fields."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import Payment, User

log = logging.getLogger(__name__)


# Keys in Stripe objects that carry the customer's contact or address details. None of the
# handlers needs them, so they are dropped before a webhook payload is stored (task 0.6).
PERSONAL_KEYS = frozenset(
    {
        "customer_email",
        "customer_name",
        "customer_phone",
        "customer_address",
        "customer_shipping",
        "customer_tax_ids",
        "customer_details",
        "billing_details",
        "shipping",
        "shipping_details",
        "email",
        "phone",
        "address",
    }
)


def scrub_personal_fields(value: Any) -> Any:
    """A copy of a Stripe payload without contact and address details, at any depth."""
    if isinstance(value, dict):
        return {k: scrub_personal_fields(v) for k, v in value.items() if k not in PERSONAL_KEYS}
    if isinstance(value, list):
        return [scrub_personal_fields(v) for v in value]
    return value


def _ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=UTC) if value else None


async def _user_by_customer(db: AsyncSession, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    return result.scalar_one_or_none()


async def _user_by_id(db: AsyncSession, user_id: str | None) -> User | None:
    if not user_id:
        return None
    try:
        return await db.get(User, uuid.UUID(user_id))
    except ValueError:
        return None


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
    user = await _user_by_id(db, session.get("client_reference_id") or meta.get("user_id"))
    if user is None:
        user = await _user_by_customer(db, session.get("customer"))
    if user is None:
        log.warning("Checkout session without a matching user")
        return
    if session.get("customer"):
        user.stripe_customer_id = session["customer"]
    # TODO(task 0.7): grant the canton entitlement for a paid one-off session here.


async def on_invoice_paid(db: AsyncSession, invoice: dict[str, Any]) -> None:
    user = await _user_by_customer(db, invoice.get("customer"))
    if user is None:
        return
    existing = await db.execute(select(Payment).where(Payment.stripe_invoice_id == invoice["id"]))
    if existing.scalar_one_or_none() is None:
        db.add(
            Payment(
                user_id=user.id,
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


HANDLERS = {
    "checkout.session.completed": on_checkout_completed,
    "invoice.paid": on_invoice_paid,
}
