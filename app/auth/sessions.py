"""Server-side sessions carried by an HttpOnly cookie."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import hash_token, new_token
from app.config import get_settings
from app.db import utcnow
from app.models import Session, User


def session_ttl(user: User) -> timedelta:
    settings = get_settings()
    hours = settings.staff_session_ttl_hours if user.is_staff else settings.session_ttl_hours
    return timedelta(hours=hours)


async def create_session(db: AsyncSession, user: User, *, mfa_pending: bool) -> str:
    token = new_token()
    row = Session(
        id=hash_token(token),
        user_id=user.id,
        expires_at=utcnow() + session_ttl(user),
        mfa_pending=mfa_pending,
    )
    db.add(row)
    await db.flush()
    return token


async def load_session(db: AsyncSession, token: str | None) -> Session | None:
    if not token:
        return None
    row = await db.get(Session, hash_token(token))
    if row is None:
        return None
    now = utcnow()
    if row.expires_at < now:
        await db.delete(row)
        await db.commit()
        return None
    # Rolling expiry, written at most once an hour to limit writes.
    if now - row.last_seen_at > timedelta(hours=1):
        row.last_seen_at = now
        user = await db.get(User, row.user_id)
        if user is not None:
            row.expires_at = now + session_ttl(user)
        await db.commit()
    return row


async def destroy_session(db: AsyncSession, token: str | None) -> None:
    if token:
        await db.execute(delete(Session).where(Session.id == hash_token(token)))


async def destroy_all_sessions(db: AsyncSession, user_id) -> None:
    await db.execute(delete(Session).where(Session.user_id == user_id))


async def purge_expired_sessions(db: AsyncSession) -> int:
    result = await db.execute(delete(Session).where(Session.expires_at < utcnow()))
    return result.rowcount or 0


def set_session_cookie(response: Response, token: str, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=int(session_ttl(user).total_seconds()),
        httponly=True,
        secure=settings.cookies_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")


def ensure_csrf_cookie(response: Response, existing: str | None) -> str:
    """Double-submit CSRF cookie. Readable by the SPA, which echoes it in a header."""
    settings = get_settings()
    token = existing or new_token(24)
    if not existing:
        response.set_cookie(
            settings.csrf_cookie_name,
            token,
            max_age=60 * 60 * 24 * 30,
            httponly=False,
            secure=settings.cookies_secure,
            samesite="lax",
            path="/",
        )
    return token


async def count_sessions(db: AsyncSession, user_id) -> int:
    result = await db.execute(select(Session.id).where(Session.user_id == user_id))
    return len(result.all())
