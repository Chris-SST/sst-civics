from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.me import entitlement_out
from app.auth.schemas import EntitlementOut
from app.auth.sessions import create_session, destroy_all_sessions, set_session_cookie
from app.billing import refunds, stripe_client
from app.billing.access import access_level
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import AuthContext, current_auth, require_admin
from app.models import (
    CANTONS,
    ENTITLEMENT_ADMIN,
    ROLE_ADMIN,
    ROLE_LEARNER,
    AuditLog,
    Entitlement,
    Payment,
    StripeEvent,
    User,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


def _aware(v: datetime) -> datetime:
    """A date sent without a time zone is taken as UTC."""
    return v if v.tzinfo is not None else v.replace(tzinfo=UTC)


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found") from None


async def _audit(
    db: AsyncSession,
    actor: User,
    action: str,
    target_type: str,
    target_id: str,
    meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
        )
    )


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    learners = await db.scalar(
        select(func.count()).select_from(User).where(User.role == ROLE_LEARNER)
    )
    roles = await db.execute(select(User.role, func.count()).group_by(User.role))
    now = utcnow()
    active = await db.scalar(
        select(func.count())
        .select_from(Entitlement)
        .where(Entitlement.starts_at <= now, Entitlement.expires_at > now)
    )
    events = (
        (await db.execute(select(StripeEvent).order_by(StripeEvent.received_at.desc()).limit(20)))
        .scalars()
        .all()
    )
    return {
        "learners": learners or 0,
        "users_by_role": {r: c for r, c in roles.all()},
        "active_entitlements": active or 0,
        "recent_stripe_events": [
            {
                "id": e.id,
                "type": e.type,
                "received_at": _iso(e.received_at),
                "processed_at": _iso(e.processed_at),
                "error": e.error,
            }
            for e in events
        ],
    }


def _learner_out(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "email_verified": u.email_verified_at is not None,
        "is_active": u.is_active,
        "locale": u.locale,
        "study_language": u.study_language,
        "canton": u.canton,
        "created_at": _iso(u.created_at),
        "last_login_at": _iso(u.last_login_at),
        "access": access_level(u),
        "entitlements": [entitlement_out(e).model_dump() for e in u.entitlements],
    }


async def _learner(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, _parse_uuid(user_id))
    if user is None or user.role != ROLE_LEARNER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return user


@router.get("/learners")
async def list_learners(q: str = "", db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(User).where(User.role == ROLE_LEARNER)
    if q:
        stmt = stmt.where(User.email.contains(q.lower().strip()))
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).limit(200))).scalars().all()
    return [_learner_out(u) for u in rows]


@router.get("/learners/{user_id}")
async def learner_detail(
    user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    user = await _learner(db, user_id)
    payments = (
        (
            await db.execute(
                select(Payment).where(Payment.user_id == user.id).order_by(Payment.paid_at.desc())
            )
        )
        .scalars()
        .all()
    )
    await _audit(db, admin, "learner.view", "user", str(user.id))
    await db.commit()
    return {
        **_learner_out(user),
        "age_confirmed_at": _iso(user.age_confirmed_at),
        "terms_version": user.terms_version,
        "terms_accepted_at": _iso(user.terms_accepted_at),
        "has_stripe_customer": bool(user.stripe_customer_id),
        "payments": [
            {
                "id": str(p.id),
                "product": p.product,
                "canton": p.canton,
                "amount_cents": p.amount_cents,
                "currency": p.currency,
                "paid_at": _iso(p.paid_at),
                "refunded_at": _iso(p.refunded_at),
                "refund": (await refunds.eligibility(db, p)).to_dict(),
            }
            for p in payments
        ],
    }


class EntitlementIn(BaseModel):
    canton: str = Field(min_length=2, max_length=2)
    expires_at: datetime
    starts_at: datetime | None = None
    source: Literal["admin", "trial"] = ENTITLEMENT_ADMIN


@router.post(
    "/users/{user_id}/entitlements",
    response_model=EntitlementOut,
    status_code=status.HTTP_201_CREATED,
)
async def grant_entitlement(
    user_id: str,
    body: EntitlementIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> EntitlementOut:
    """Give a learner access to one canton, for support, testing or a trial."""
    user = await _learner(db, user_id)
    canton = body.canton.lower()
    if canton not in CANTONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_canton")
    starts_at = _aware(body.starts_at) if body.starts_at else utcnow()
    expires_at = _aware(body.expires_at)
    if expires_at <= starts_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_period")
    entitlement = Entitlement(
        user_id=user.id,
        canton=canton,
        starts_at=starts_at,
        expires_at=expires_at,
        source=body.source,
    )
    user.entitlements.append(entitlement)
    await db.flush()
    await _audit(
        db,
        admin,
        "entitlement.grant",
        "user",
        str(user.id),
        {"canton": canton, "expires_at": _iso(expires_at), "source": body.source},
    )
    await db.commit()
    return entitlement_out(entitlement)


@router.get("/users")
async def list_admins(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(User).where(User.role == ROLE_ADMIN).order_by(User.created_at)
    users = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(u.id),
            "role": u.role,
            "email": u.email,
            "locale": u.locale,
            "is_active": u.is_active,
            "totp_enabled": u.totp_enabled,
            "last_login_at": _iso(u.last_login_at),
        }
        for u in users
    ]


class UserPatch(BaseModel):
    is_active: bool | None = None


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user = await db.get(User, _parse_uuid(user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.is_active is not None:
        if user.id == admin.id and not body.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_deactivate_self")
        user.is_active = body.is_active
        if not body.is_active:
            await destroy_all_sessions(db, user.id)
    await _audit(db, admin, "user.update", "user", str(user.id), body.model_dump(exclude_none=True))
    await db.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/reset-2fa")
async def reset_2fa(
    user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    user = await db.get(User, _parse_uuid(user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    user.totp_enabled = False
    user.totp_secret = None
    await destroy_all_sessions(db, user.id)
    await _audit(db, admin, "user.reset_2fa", "user", str(user.id))
    await db.commit()
    return {"status": "ok"}


class RefundIn(BaseModel):
    # Refund although the rule (14 days, fewer than 50 questions) says no: goodwill cases.
    override: bool = False


@router.post("/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    body: RefundIn | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Refund a payment in full through Stripe. Access is shortened when the
    `charge.refunded` webhook arrives, not here."""
    body = body or RefundIn()
    payment = await db.get(Payment, _parse_uuid(payment_id))
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if payment.refunded_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_refunded")
    if not payment.stripe_payment_intent_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_payment_intent")
    if not get_settings().stripe_secret_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "billing_not_configured")
    rule = await refunds.eligibility(db, payment)
    if not rule.eligible and not body.override:
        raise HTTPException(status.HTTP_409_CONFLICT, f"refund_{rule.reason}")
    try:
        refund = stripe_client.create_refund(
            payment.stripe_payment_intent_id,
            metadata={"payment_id": str(payment.id)},
            idempotency_key=f"civics-refund-{payment.id}",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Stripe refund failed for payment %s: %s", payment.id, exc.__class__.__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "refund_failed") from None
    await _audit(
        db,
        admin,
        "payment.refund",
        "payment",
        str(payment.id),
        {
            "refund_id": refund.get("id"),
            "amount_cents": payment.amount_cents,
            "product": payment.product,
            "override": body.override,
            "eligible": rule.eligible,
            "reason": rule.reason,
            "questions_studied": rule.questions_studied,
        },
    )
    await db.commit()
    return {"status": refund.get("status") or "pending", "refund_id": refund.get("id")}


@router.get("/audit")
async def audit_log(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(a.id),
            "actor_user_id": str(a.actor_user_id) if a.actor_user_id else None,
            "action": a.action,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "meta": a.meta,
            "created_at": _iso(a.created_at),
        }
        for a in rows
    ]


@router.post("/impersonate/{user_id}")
async def impersonate(
    user_id: str,
    response: Response,
    ctx: AuthContext = Depends(current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Open the app as a learner. Staging and development only; always logged."""
    admin = ctx.user
    if admin.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    if not get_settings().impersonation_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "impersonation_disabled")
    target = await db.get(User, _parse_uuid(user_id))
    if target is None or not target.is_active or target.role != ROLE_LEARNER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_impersonate")
    # The admin's own session is removed so one browser holds one identity at a time.
    await db.delete(ctx.session)
    token = await create_session(db, target, mfa_pending=False, impersonator_id=admin.id)
    await _audit(db, admin, "user.impersonate", "user", str(target.id), {"role": target.role})
    await db.commit()
    set_session_cookie(response, token, target)
    return {"status": "impersonating", "role": target.role}
