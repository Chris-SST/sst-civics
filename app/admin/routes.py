from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import one_time
from app.auth.sessions import destroy_all_sessions
from app.billing.access import compute_access
from app.db import get_db
from app.deps import require_admin
from app.email.messages import app_link
from app.jobs import send_email_job
from app.models import (
    PAYER_ROLES,
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TUTOR,
    STAFF_ROLES,
    TOKEN_STAFF_INVITE,
    AuditLog,
    Family,
    Payment,
    Plan,
    StripeEvent,
    User,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


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
    families = await db.scalar(select(func.count()).select_from(Family))
    roles = await db.execute(select(User.role, func.count()).group_by(User.role))
    statuses = await db.execute(
        select(Family.subscription_status, func.count()).group_by(Family.subscription_status)
    )
    events = (
        (await db.execute(select(StripeEvent).order_by(StripeEvent.received_at.desc()).limit(20)))
        .scalars()
        .all()
    )
    return {
        "families": families or 0,
        "users_by_role": {r: c for r, c in roles.all()},
        "subscriptions_by_status": {(s or "none"): c for s, c in statuses.all()},
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


@router.get("/families")
async def list_families(q: str = "", db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    stmt = select(Family).order_by(Family.created_at.desc()).limit(200)
    families = (await db.execute(stmt)).scalars().all()
    out = []
    for f in families:
        users = (await db.execute(select(User).where(User.family_id == f.id))).scalars().all()
        payer = next((u for u in users if u.role in PAYER_ROLES), None)
        if q and not (payer and payer.email and q.lower() in payer.email):
            continue
        out.append(
            {
                "id": str(f.id),
                "created_at": _iso(f.created_at),
                "payer_email": payer.email if payer else None,
                "payer_verified": bool(payer and payer.email_verified_at),
                "plan_key": f.plan_key,
                "subscription_status": f.subscription_status,
                "quantity": f.quantity,
                "access": compute_access(f),
                "student_count": sum(1 for u in users if u.role == ROLE_STUDENT and u.is_active),
                "free_access_until": _iso(f.free_access_until),
                "payment_warning": f.payment_warning,
            }
        )
    return out


@router.get("/families/{family_id}")
async def family_detail(
    family_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    family = await db.get(Family, _parse_uuid(family_id))
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    users = (await db.execute(select(User).where(User.family_id == family.id))).scalars().all()
    payments = (
        (await db.execute(select(Payment).where(Payment.family_id == family.id))).scalars().all()
    )
    await _audit(db, admin, "family.view", "family", str(family.id))
    await db.commit()
    return {
        "id": str(family.id),
        "locale": family.locale,
        "created_at": _iso(family.created_at),
        "terms_version": family.terms_version,
        "terms_accepted_at": _iso(family.terms_accepted_at),
        "guardian_confirmed_at": _iso(family.guardian_confirmed_at),
        "stripe_customer_id": family.stripe_customer_id,
        "stripe_subscription_id": family.stripe_subscription_id,
        "plan_key": family.plan_key,
        "subscription_status": family.subscription_status,
        "quantity": family.quantity,
        "current_period_end": _iso(family.current_period_end),
        "trial_end": _iso(family.trial_end),
        "cancel_at_period_end": family.cancel_at_period_end,
        "past_due_since": _iso(family.past_due_since),
        "payment_warning": family.payment_warning,
        "free_access_until": _iso(family.free_access_until),
        "free_access_reason": family.free_access_reason,
        "tutor_credits": family.tutor_credits,
        "access": compute_access(family),
        "users": [
            {
                "id": str(u.id),
                "role": u.role,
                "email": u.email,
                "username": u.username,
                "first_name": u.first_name,
                "email_verified": u.email_verified_at is not None,
                "is_active": u.is_active,
                "totp_enabled": u.totp_enabled,
                "last_login_at": _iso(u.last_login_at),
            }
            for u in users
        ],
        "payments": [
            {
                "id": str(p.id),
                "amount_cents": p.amount_cents,
                "currency": p.currency,
                "paid_at": _iso(p.paid_at),
            }
            for p in payments
        ],
    }


class FreeAccessIn(BaseModel):
    until: datetime | None
    reason: str = Field(default="", max_length=200)


@router.post("/families/{family_id}/free-access")
async def grant_free_access(
    family_id: str,
    body: FreeAccessIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    family = await db.get(Family, _parse_uuid(family_id))
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    family.free_access_until = body.until
    family.free_access_reason = body.reason or None
    await _audit(
        db,
        admin,
        "family.free_access",
        "family",
        str(family.id),
        {"until": _iso(body.until), "reason": body.reason},
    )
    await db.commit()
    return {"free_access_until": _iso(family.free_access_until), "access": compute_access(family)}


@router.get("/users")
async def list_staff(
    role: Literal["tutor", "admin", "all"] = "all", db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    stmt = select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.created_at)
    if role != "all":
        stmt = select(User).where(User.role == role).order_by(User.created_at)
    users = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(u.id),
            "role": u.role,
            "email": u.email,
            "first_name": u.first_name,
            "locale": u.locale,
            "is_active": u.is_active,
            "totp_enabled": u.totp_enabled,
            "invite_pending": u.password_hash is None,
            "tagged_courses": u.tagged_courses or [],
            "available": u.available,
            "last_login_at": _iso(u.last_login_at),
        }
        for u in users
    ]


class StaffIn(BaseModel):
    email: EmailStr
    role: Literal["tutor", "admin"]
    first_name: str = Field(min_length=1, max_length=80)
    locale: Literal["en", "de", "fr"] = "en"
    tagged_courses: list[str] = Field(default_factory=list)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: StaffIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    email = body.email.lower().strip()
    exists = await db.execute(select(User.id).where(User.email == email))
    if exists.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email_in_use")
    user = User(
        role=ROLE_TUTOR if body.role == "tutor" else ROLE_ADMIN,
        email=email,
        first_name=body.first_name.strip(),
        locale=body.locale,
        tagged_courses=body.tagged_courses,
    )
    db.add(user)
    await db.flush()
    token = await one_time.issue_token(db, user, TOKEN_STAFF_INVITE)
    await send_email_job(
        "staff_invite",
        user.locale,
        email,
        first_name=user.first_name,
        role=user.role,
        link=app_link(f"/accept-invite?token={token}"),
    )
    await _audit(db, admin, "staff.create", "user", str(user.id), {"role": user.role})
    await db.commit()
    return {"id": str(user.id), "status": "invited"}


class StaffPatch(BaseModel):
    is_active: bool | None = None
    tagged_courses: list[str] | None = None
    available: bool | None = None


@router.patch("/users/{user_id}")
async def update_staff(
    user_id: str,
    body: StaffPatch,
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
    if body.tagged_courses is not None:
        user.tagged_courses = body.tagged_courses
    if body.available is not None:
        user.available = body.available
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


@router.post("/users/{user_id}/resend-invite")
async def resend_invite(
    user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    user = await db.get(User, _parse_uuid(user_id))
    if user is None or not user.is_staff or user.password_hash is not None or not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not_invitable")
    token = await one_time.issue_token(db, user, TOKEN_STAFF_INVITE)
    await send_email_job(
        "staff_invite",
        user.locale,
        user.email,
        first_name=user.first_name,
        role=user.role,
        link=app_link(f"/accept-invite?token={token}"),
    )
    await db.commit()
    return {"status": "invited"}


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Plan).order_by(Plan.sort_order))).scalars().all()
    return [
        {
            "key": p.key,
            "kind": p.kind,
            "monthly_message_limit": p.monthly_message_limit,
            "daily_message_limit": p.daily_message_limit,
            "is_active": p.is_active,
        }
        for p in rows
    ]


class PlanPatch(BaseModel):
    monthly_message_limit: int | None = Field(default=None, ge=0)
    daily_message_limit: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.patch("/plans/{key}")
async def update_plan(
    key: str,
    body: PlanPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    plan = await db.get(Plan, key)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.monthly_message_limit is not None:
        plan.monthly_message_limit = body.monthly_message_limit
    if body.daily_message_limit is not None:
        plan.daily_message_limit = body.daily_message_limit
    if body.is_active is not None:
        plan.is_active = body.is_active
    await _audit(db, admin, "plan.update", "plan", key, body.model_dump(exclude_none=True))
    await db.commit()
    return {"status": "ok"}


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
