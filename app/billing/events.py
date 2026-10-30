"""Apply Stripe webhook events to our records. Called from the background worker. Every
handler is idempotent.

One-off Civics Pass payments (D-015):

- `checkout.session.completed` with `payment_status=paid`, or
  `checkout.session.async_payment_succeeded` for delayed methods: grant or extend the
  canton entitlement and record a `Payment`, once per Checkout Session.
- `checkout.session.async_payment_failed`: nothing is recorded; logged only.
- `charge.refunded` (full refund): the entitlement the payment bought ends at the refund
  time, or loses the months the payment added; the payment is marked refunded.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import products
from app.billing.access import active_pass, extendable_pass
from app.db import utcnow
from app.models import CANTONS, ENTITLEMENT_STRIPE, Entitlement, Payment, User

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


def _id(value: Any) -> str | None:
    """A Stripe id from a field that holds either the id or the expanded object."""
    if isinstance(value, dict):
        return value.get("id")
    return value or None


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
    await handler(db, obj, _ts(event.get("created")) or utcnow())


async def _session_user(db: AsyncSession, session: dict[str, Any]) -> User | None:
    user = await _user_by_id(db, session.get("client_reference_id"))
    if user is None:
        user = await _user_by_customer(db, _id(session.get("customer")))
    if user is None:
        log.warning("Checkout session %s without a matching user", session.get("id"))
    return user


async def on_checkout_completed(db: AsyncSession, session: dict[str, Any], at: datetime) -> None:
    user = await _session_user(db, session)
    if user is None:
        return
    customer = _id(session.get("customer"))
    if customer and not user.stripe_customer_id:
        user.stripe_customer_id = customer
    if session.get("mode") != "payment":
        log.info("Ignoring checkout session %s in mode %s", session.get("id"), session.get("mode"))
        return
    if session.get("payment_status") != "paid":
        # A delayed method: `async_payment_succeeded` or `async_payment_failed` follows.
        log.info("Checkout session %s awaits payment", session.get("id"))
        return
    await fulfil(db, user, session)


async def on_async_payment_succeeded(
    db: AsyncSession, session: dict[str, Any], at: datetime
) -> None:
    user = await _session_user(db, session)
    if user is not None:
        await fulfil(db, user, session)


async def on_async_payment_failed(db: AsyncSession, session: dict[str, Any], at: datetime) -> None:
    log.info("Delayed payment failed for checkout session %s; nothing granted", session.get("id"))


def _months(meta: dict[str, Any], product: products.Product) -> int:
    try:
        months = int(meta.get("months") or product.months)
    except (TypeError, ValueError):
        months = product.months
    return months if 0 < months <= 24 else product.months


async def fulfil(db: AsyncSession, user: User, session: dict[str, Any]) -> Payment | None:
    """Grant what a paid Checkout Session bought. Once per session."""
    session_id = session.get("id")
    if not session_id:
        return None
    existing = await db.execute(
        select(Payment).where(Payment.stripe_checkout_session_id == session_id)
    )
    if existing.scalar_one_or_none() is not None:
        return None
    meta = session.get("metadata") or {}
    product = products.PRODUCTS.get(meta.get("product", ""))
    if product is None:
        log.warning("Checkout session %s for an unknown product", session_id)
        return None
    canton = (meta.get("canton") or product.canton or "").lower()
    if canton not in CANTONS:
        log.warning("Checkout session %s without a valid canton", session_id)
        return None
    months = _months(meta, product)
    now = utcnow()
    entitlement = await _grant(db, user, product, canton, months, now, session_id)
    payment = Payment(
        user_id=user.id,
        entitlement_id=entitlement.id,
        product=product.key,
        canton=canton,
        months=months,
        stripe_checkout_session_id=session_id,
        stripe_payment_intent_id=_id(session.get("payment_intent")),
        amount_cents=int(session.get("amount_total") or 0),
        currency=(session.get("currency") or "chf").lower(),
        paid_at=now,
    )
    db.add(payment)
    await db.flush()
    log.info("Granted %s (%d months) for checkout session %s", product.key, months, session_id)
    return payment


async def _grant(
    db: AsyncSession,
    user: User,
    product: products.Product,
    canton: str,
    months: int,
    now: datetime,
    session_id: str,
) -> Entitlement:
    """Extend an active pass from its expiry; for an extension, revive a pass that expired
    within the grace period, from now; otherwise start a new pass now. A second pass paid
    while one is active (two Checkouts opened at once) extends it instead of overlapping."""
    current = active_pass(user, canton, now)
    if current is not None:
        current.expires_at = products.add_months(current.expires_at, months)
        return current
    if product.kind == products.KIND_EXTENSION:
        lapsed = extendable_pass(user, canton, now)
        if lapsed is not None:
            lapsed.expires_at = products.add_months(now, months)
            return lapsed
        log.warning("Extension in session %s found no pass to extend; started anew", session_id)
    entitlement = Entitlement(
        user_id=user.id,
        canton=canton,
        starts_at=now,
        expires_at=products.add_months(now, months),
        source=ENTITLEMENT_STRIPE,
        stripe_checkout_session_id=session_id,
    )
    user.entitlements.append(entitlement)
    await db.flush()
    return entitlement


async def on_charge_refunded(db: AsyncSession, charge: dict[str, Any], at: datetime) -> None:
    intent = _id(charge.get("payment_intent"))
    if not intent:
        log.info("Refunded charge %s without a payment intent", charge.get("id"))
        return
    result = await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == intent))
    payment = result.scalar_one_or_none()
    if payment is None:
        log.warning("Refund for charge %s with no matching payment", charge.get("id"))
        return
    payment.amount_refunded_cents = int(charge.get("amount_refunded") or 0)
    if payment.refunded_at is not None:
        return
    if not charge.get("refunded"):
        log.info("Partial refund on payment %s; access unchanged", payment.id)
        return
    refunds = (charge.get("refunds") or {}).get("data") or []
    when = max((_ts(r.get("created")) for r in refunds if r.get("created")), default=None) or at
    payment.refunded_at = when
    entitlement = (
        await db.get(Entitlement, payment.entitlement_id) if payment.entitlement_id else None
    )
    if entitlement is not None:
        if entitlement.stripe_checkout_session_id == payment.stripe_checkout_session_id:
            # This payment started the entitlement: access ends at the refund.
            entitlement.expires_at = min(entitlement.expires_at, when)
        else:
            # This payment extended it: take its months off again, but not into the past.
            entitlement.expires_at = max(
                when, products.add_months(entitlement.expires_at, -payment.months)
            )
    log.info("Refund applied to payment %s", payment.id)


HANDLERS = {
    "checkout.session.completed": on_checkout_completed,
    "checkout.session.async_payment_succeeded": on_async_payment_succeeded,
    "checkout.session.async_payment_failed": on_async_payment_failed,
    "charge.refunded": on_charge_refunded,
}
