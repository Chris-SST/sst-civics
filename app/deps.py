"""Request dependencies: current user, role checks, client address."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.sessions import load_session
from app.config import get_settings
from app.db import get_db
from app.models import ROLE_ADMIN, ROLE_LEARNER, Session, User


@dataclass
class AuthContext:
    user: User
    session: Session


def client_ip(request: Request) -> str:
    # Caddy sets X-Forwarded-For; only trust the first hop it added.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def optional_auth(request: Request, db: AsyncSession = Depends(get_db)) -> AuthContext | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    session = await load_session(db, token)
    if session is None:
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return AuthContext(user=user, session=session)


async def auth_any_state(ctx: AuthContext | None = Depends(optional_auth)) -> AuthContext:
    """Logged in, possibly still waiting for the second factor."""
    if ctx is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return ctx


async def current_auth(ctx: AuthContext = Depends(auth_any_state)) -> AuthContext:
    """Fully authenticated: password plus second factor where required (admins only;
    learners have no second factor)."""
    if ctx.session.mfa_pending:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "mfa_required")
    if ctx.user.is_staff and not ctx.user.totp_enabled and not ctx.session.impersonator_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "mfa_setup_required")
    return ctx


async def current_user(ctx: AuthContext = Depends(current_auth)) -> User:
    return ctx.user


def require_roles(*roles: str) -> Callable:
    async def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
        return user

    return _dep


require_admin = require_roles(ROLE_ADMIN)
require_learner = require_roles(ROLE_LEARNER)
