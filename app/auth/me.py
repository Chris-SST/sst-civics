"""Serialise the signed-in person for the front end."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    AccessOut,
    EntitlementOut,
    MeOut,
    SessionOut,
    UserOut,
)
from app.auth.sessions import ensure_csrf_cookie
from app.billing.access import access_level, extendable_pass, is_active, is_free_tier
from app.config import get_settings
from app.db import utcnow
from app.deps import AuthContext
from app.models import CANTONS, Entitlement, Session, User

REAUTH_WINDOW = timedelta(minutes=10)


def reauth_seconds_left(session: Session) -> int:
    """Seconds left of the re-authentication window opened by an email link."""
    if session.email_link_at is None or session.impersonator_user_id is not None:
        return 0
    left = (session.email_link_at + REAUTH_WINDOW - utcnow()).total_seconds()
    return max(0, int(left))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def entitlement_out(e: Entitlement) -> EntitlementOut:
    return EntitlementOut(
        id=str(e.id),
        canton=e.canton,
        starts_at=e.starts_at.isoformat(),
        expires_at=e.expires_at.isoformat(),
        source=e.source,
        active=is_active(e),
    )


def access_out(user: User) -> AccessOut:
    now = utcnow()
    return AccessOut(
        access=access_level(user),  # type: ignore[arg-type]
        canton=user.canton,
        entitlements=[entitlement_out(e) for e in user.entitlements],
        has_stripe_customer=bool(user.stripe_customer_id),
        free_tier=is_free_tier(user),
        # The same rule the server applies when an extension is bought (extension_grace_days).
        can_extend={c: extendable_pass(user, c, now) is not None for c in CANTONS},
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        role=user.role,
        email=user.email,
        locale=user.locale,
        study_language=user.study_language,
        canton=user.canton,
        email_verified=user.email_verified_at is not None,
        totp_enabled=user.totp_enabled,
        has_password=user.password_hash is not None,
    )


async def build_me(
    db: AsyncSession, ctx: AuthContext, request: Request, response: Response
) -> MeOut:
    user = ctx.user
    csrf = ensure_csrf_cookie(response, request.cookies.get(get_settings().csrf_cookie_name))
    impersonated_by = None
    if ctx.session.impersonator_user_id:
        admin = await db.get(User, ctx.session.impersonator_user_id)
        impersonated_by = (admin.email or "admin") if admin else "admin"
    return MeOut(
        user=user_out(user),
        session=SessionOut(
            mfa_pending=ctx.session.mfa_pending,
            mfa_setup_required=user.is_staff
            and not user.totp_enabled
            and not ctx.session.impersonator_user_id,
            impersonated_by=impersonated_by,
            reauth_seconds_left=reauth_seconds_left(ctx.session),
        ),
        access=access_out(user),
        csrf_token=csrf,
    )
