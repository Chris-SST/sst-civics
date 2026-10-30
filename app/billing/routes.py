"""Civics Pass billing: products and prices from Stripe, one-off Checkout, payments, refund
eligibility and the Stripe webhook."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import events, products, refunds, stripe_client
from app.billing.access import access_level, active_pass, compute_access, extendable_pass
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, require_learner
from app.jobs import enqueue
from app.models import CANTONS, Payment, StripeEvent, User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

_price_cache: dict[str, Any] = {"at": 0.0, "prices": {}}
PRICE_CACHE_SECONDS = 600


class ProductOut(BaseModel):
    key: str
    kind: Literal["pass", "extension"]
    canton: str | None
    amount_cents: int | None
    currency: str
    months: int
    available: bool  # a price exists in Stripe


class CheckoutIn(BaseModel):
    product: Literal["civics_pass_zh", "civics_pass_ag", "civics_extension"]
    # Which pass an extension is for; by default the learner's extendable pass or canton.
    canton: str | None = Field(default=None, min_length=2, max_length=2)


class UrlOut(BaseModel):
    url: str


class PaymentOut(BaseModel):
    id: str
    product: str
    canton: str
    amount_cents: int
    currency: str
    paid_at: str
    refunded_at: str | None


def _prices() -> dict[str, dict[str, Any]]:
    """Active Stripe prices by lookup key, cached for ten minutes."""
    now = time.monotonic()
    if _price_cache["prices"] and now - _price_cache["at"] < PRICE_CACHE_SECONDS:
        return _price_cache["prices"]
    if not get_settings().stripe_secret_key:
        return {}
    try:
        found = stripe_client.list_prices_by_lookup_keys(list(products.ALL_KEYS))
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load Stripe prices: %s", exc.__class__.__name__)
        return _price_cache["prices"] or {}
    by_key = {p["lookup_key"]: p for p in found if p.get("lookup_key")}
    _price_cache.update(at=now, prices=by_key)
    return by_key


def clear_price_cache() -> None:
    _price_cache.update(at=0.0, prices={})


def price_months(price: dict[str, Any], product: products.Product) -> int:
    """The access period from the price's `access_months` metadata, else the product's."""
    try:
        months = int((price.get("metadata") or {}).get("access_months") or product.months)
    except (TypeError, ValueError):
        return product.months
    return months if 0 < months <= 24 else product.months


def products_for_sale() -> list[products.Product]:
    on_sale = get_settings().cantons_on_sale
    return [
        p
        for p in products.PRODUCTS.values()
        if p.kind == products.KIND_EXTENSION or p.canton in on_sale
    ]


@router.get("/products", response_model=list[ProductOut])
async def list_products() -> list[ProductOut]:
    """The passes for the cantons on sale and the extension, priced from Stripe."""
    prices = _prices()
    out = []
    for p in products_for_sale():
        price = prices.get(p.key) or {}
        out.append(
            ProductOut(
                key=p.key,
                kind=p.kind,  # type: ignore[arg-type]
                canton=p.canton,
                amount_cents=price.get("unit_amount"),
                currency=(price.get("currency") or "chf").upper(),
                months=price_months(price, p),
                available=bool(price.get("id")),
            )
        )
    return out


async def _ensure_customer(db: AsyncSession, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe_client.create_customer(user.email or "")
    user.stripe_customer_id = customer["id"]
    await db.commit()
    return customer["id"]


def _extension_canton(user: User, requested: str | None) -> str:
    if requested:
        return requested.lower()
    for canton in sorted({e.canton for e in user.entitlements}):
        if extendable_pass(user, canton) is not None:
            return canton
    return user.canton


@router.post("/checkout", response_model=UrlOut)
async def create_checkout(
    body: CheckoutIn, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> UrlOut:
    """A Stripe Checkout Session in payment mode for one pass or an extension. Payment
    methods (card, TWINT) come from the Dashboard settings."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "billing_not_configured")
    product = products.PRODUCTS[body.product]
    if product.kind == products.KIND_PASS:
        canton = product.canton or ""
        if canton not in settings.cantons_on_sale:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_for_sale")
        if active_pass(user, canton) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "pass_active")
    else:
        canton = _extension_canton(user, body.canton)
        if canton not in CANTONS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_canton")
        if extendable_pass(user, canton) is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "no_pass_to_extend")
    price = _prices().get(product.key)
    if price is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "price_not_found")

    base = settings.app_base_url.rstrip("/")
    customer_id = await _ensure_customer(db, user)
    meta = {"product": product.key, "canton": canton, "months": str(price_months(price, product))}
    session = stripe_client.create_checkout_session(
        {
            "mode": "payment",
            "customer": customer_id,
            "client_reference_id": str(user.id),
            "line_items": [{"price": price["id"], "quantity": 1}],
            "metadata": meta,
            "payment_intent_data": {"metadata": meta},
            "success_url": (
                f"{base}/billing/return?status=success&canton={canton}"
                "&session_id={CHECKOUT_SESSION_ID}"
            ),
            "cancel_url": f"{base}/billing/return?status=cancelled",
            "locale": stripe_client.stripe_locale(user.locale),
        }
    )
    return UrlOut(url=session["url"])


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> list[PaymentOut]:
    rows = (
        (
            await db.execute(
                select(Payment).where(Payment.user_id == user.id).order_by(Payment.paid_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        PaymentOut(
            id=str(p.id),
            product=p.product,
            canton=p.canton,
            amount_cents=p.amount_cents,
            currency=p.currency.upper(),
            paid_at=p.paid_at.isoformat(),
            refunded_at=p.refunded_at.isoformat() if p.refunded_at else None,
        )
        for p in rows
    ]


@router.get("/refund-eligibility")
async def refund_eligibility(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Whether the learner's latest payment may still be refunded. There is no self-service
    refund: the learner writes to support and an admin refunds."""
    payment = await refunds.latest_payment(db, user)
    return (await refunds.eligibility(db, payment)).to_dict()


@router.get("/access")
async def my_access(user: User = Depends(current_user)) -> dict[str, Any]:
    cantons = compute_access(user, user.entitlements)
    return {
        "access": access_level(user),
        "canton": user.canton,
        "cantons": {
            c.canton: {"expires_at": c.expires_at.isoformat(), "source": c.source}
            for c in cantons.values()
        },
    }


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook_not_configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_client.construct_event(payload, signature)
    except Exception as exc:  # noqa: BLE001
        log.warning("Rejected Stripe webhook: %s", exc.__class__.__name__)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_signature") from None

    event_id = event["id"]
    if await db.get(StripeEvent, event_id) is not None:
        return {"received": True, "duplicate": True}
    # Stored without the customer's contact and address details (task 0.6).
    stored = events.scrub_personal_fields(dict(event))
    db.add(StripeEvent(id=event_id, type=event.get("type", ""), payload=stored))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"received": True, "duplicate": True}
    await enqueue("process_stripe_event", event_id=event_id)
    return {"received": True}
