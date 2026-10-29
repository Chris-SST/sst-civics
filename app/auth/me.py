"""Serialise the signed-in person for the front end."""

from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import FamilyOut, MeOut, SessionOut, UserOut
from app.auth.sessions import ensure_csrf_cookie
from app.billing.access import compute_access
from app.config import get_settings
from app.deps import AuthContext
from app.models import ROLE_STUDENT, Family, User


def _iso(value) -> str | None:
    return value.isoformat() if value else None


async def family_out(db: AsyncSession, family: Family | None) -> FamilyOut | None:
    if family is None:
        return None
    count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.family_id == family.id, User.role == ROLE_STUDENT, User.is_active.is_(True))
    )
    return FamilyOut(
        id=str(family.id),
        locale=family.locale,
        plan_key=family.plan_key,
        subscription_status=family.subscription_status,
        quantity=family.quantity,
        current_period_end=_iso(family.current_period_end),
        trial_end=_iso(family.trial_end),
        cancel_at_period_end=family.cancel_at_period_end,
        payment_warning=family.payment_warning,
        free_access_until=_iso(family.free_access_until),
        tutor_credits=family.tutor_credits,
        access=compute_access(family),
        has_stripe_customer=bool(family.stripe_customer_id),
        student_count=int(count or 0),
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        role=user.role,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        locale=user.locale,
        email_verified=user.email_verified_at is not None,
        totp_enabled=user.totp_enabled,
    )


async def build_me(
    db: AsyncSession, ctx: AuthContext, request: Request, response: Response
) -> MeOut:
    user = ctx.user
    family = await db.get(Family, user.family_id) if user.family_id else None
    csrf = ensure_csrf_cookie(response, request.cookies.get(get_settings().csrf_cookie_name))
    impersonated_by = None
    if ctx.session.impersonator_user_id:
        admin = await db.get(User, ctx.session.impersonator_user_id)
        impersonated_by = (admin.first_name or admin.email) if admin else "admin"
    return MeOut(
        user=user_out(user),
        session=SessionOut(
            mfa_pending=ctx.session.mfa_pending,
            mfa_setup_required=user.is_staff
            and not user.totp_enabled
            and not ctx.session.impersonator_user_id,
            impersonated_by=impersonated_by,
        ),
        family=await family_out(db, family),
        csrf_token=csrf,
    )
