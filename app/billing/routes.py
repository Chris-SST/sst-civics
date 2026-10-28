from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import plans, stripe_client
from app.billing.access import compute_access
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, require_roles
from app.jobs import enqueue
from app.models import (
    PAYER_ROLES,
    ROLE_ADULT,
    ROLE_STUDENT,
    Family,
    Payment,
    Plan,
    StripeEvent,
    User,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])
require_payer = require_roles(*PAYER_ROLES)

_price_cache: dict[str, Any] = {"at": 0.0, "prices": {}}
PRICE_CACHE_SECONDS = 600


class PlanOut(BaseModel):
    key: str
    kind: str
    amount_cents: int | None
    currency: str
    interval: str | None
    monthly_message_limit: int | None
    daily_message_limit: int | None
    price_id: str | None


class CheckoutIn(BaseModel):
    plan_key: str
    quantity: int = Field(default=1, ge=1, le=10)


class UrlOut(BaseModel):
    url: str


class PaymentOut(BaseModel):
    id: str
    amount_cents: int
    currency: str
    paid_at: str


def _prices() -> dict[str, dict[str, Any]]:
    """Active Stripe prices by lookup key, cached for ten minutes."""
    now = time.monotonic()
    if _price_cache["prices"] and now - _price_cache["at"] < PRICE_CACHE_SECONDS:
        return _price_cache["prices"]
    if not get_settings().stripe_secret_key:
        return {}
    try:
        found = stripe_client.list_prices_by_lookup_keys(list(plans.ALL_PLANS))
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load Stripe prices: %s", exc.__class__.__name__)
        return _price_cache["prices"] or {}
    by_key = {p["lookup_key"]: p for p in found if p.get("lookup_key")}
    _price_cache.update(at=now, prices=by_key)
    return by_key


def clear_price_cache() -> None:
    _price_cache.update(at=0.0, prices={})


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanOut]:
    rows = (
        (await db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order)))
        .scalars()
        .all()
    )
    prices = _prices()
    out = []
    for p in rows:
        price = prices.get(p.key) or {}
        recurring = price.get("recurring") or {}
        out.append(
            PlanOut(
                key=p.key,
                kind=p.kind,
                amount_cents=price.get("unit_amount"),
                currency=(price.get("currency") or "chf").upper(),
                interval=recurring.get("interval"),
                monthly_message_limit=p.monthly_message_limit,
                daily_message_limit=p.daily_message_limit,
                price_id=price.get("id"),
            )
        )
    return out


async def _ensure_customer(db: AsyncSession, family: Family, user: User) -> str:
    if family.stripe_customer_id:
        return family.stripe_customer_id
    customer = stripe_client.create_customer(user.email or "", str(family.id), family.locale)
    family.stripe_customer_id = customer["id"]
    await db.commit()
    return customer["id"]


@router.post("/checkout", response_model=UrlOut)
async def create_checkout(
    body: CheckoutIn, user: User = Depends(require_payer), db: AsyncSession = Depends(get_db)
) -> UrlOut:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "billing_not_configured")
    plan = await db.get(Plan, body.plan_key)
    if plan is None or not plan.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_plan")
    family = await db.get(Family, user.family_id)
    if family is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_family")
    price = _prices().get(plan.key)
    if price is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "price_not_found")

    base = settings.app_base_url.rstrip("/")
    customer_id = await _ensure_customer(db, family, user)
    params: dict[str, Any] = {
        "customer": customer_id,
        "client_reference_id": str(family.id),
        "success_url": f"{base}/billing/return?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/billing/return?status=cancelled",
        "locale": family.locale,
        "allow_promotion_codes": True,
    }

    if plan.kind == "subscription":
        if family.subscription_status in ("trialing", "active", "past_due"):
            raise HTTPException(status.HTTP_409_CONFLICT, "already_subscribed")
        if user.role == ROLE_ADULT:
            quantity = 1
        else:
            quantity = int(
                await db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(
                        User.family_id == family.id,
                        User.role == ROLE_STUDENT,
                        User.is_active.is_(True),
                    )
                )
                or 0
            )
            if quantity == 0:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "add_student_first")
        params.update(
            {
                "mode": "subscription",
                "line_items": [{"price": price["id"], "quantity": quantity}],
                "payment_method_collection": "always",
                "subscription_data": {
                    "trial_period_days": settings.stripe_trial_days,
                    "metadata": {"family_id": str(family.id), "plan_key": plan.key},
                },
                "metadata": {
                    "family_id": str(family.id),
                    "plan_key": plan.key,
                    "quantity": str(quantity),
                },
            }
        )
    else:
        params.update(
            {
                "mode": "payment",
                "line_items": [{"price": price["id"], "quantity": body.quantity}],
                "metadata": {
                    "family_id": str(family.id),
                    "plan_key": plan.key,
                    "quantity": str(body.quantity),
                },
            }
        )

    session = stripe_client.create_checkout_session(params)
    return UrlOut(url=session["url"])


@router.post("/portal", response_model=UrlOut)
async def create_portal(
    user: User = Depends(require_payer), db: AsyncSession = Depends(get_db)
) -> UrlOut:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "billing_not_configured")
    family = await db.get(Family, user.family_id)
    if family is None or not family.stripe_customer_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_stripe_customer")
    session = stripe_client.create_portal_session(
        family.stripe_customer_id, f"{settings.app_base_url.rstrip('/')}/parent", family.locale
    )
    return UrlOut(url=session["url"])


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    user: User = Depends(require_payer), db: AsyncSession = Depends(get_db)
) -> list[PaymentOut]:
    rows = (
        (
            await db.execute(
                select(Payment)
                .where(Payment.family_id == user.family_id)
                .order_by(Payment.paid_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        PaymentOut(
            id=str(p.id),
            amount_cents=p.amount_cents,
            currency=p.currency.upper(),
            paid_at=p.paid_at.isoformat(),
        )
        for p in rows
    ]


@router.get("/access")
async def my_access(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    family = await db.get(Family, user.family_id) if user.family_id else None
    return {"access": compute_access(family), "plan_key": family.plan_key if family else None}


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
    db.add(StripeEvent(id=event_id, type=event.get("type", ""), payload=event))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return {"received": True, "duplicate": True}
    await enqueue("process_stripe_event", event_id=event_id)
    return {"received": True}
