"""Single-use tokens sent by email: email verification and password reset."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import hash_token, new_token
from app.db import utcnow
from app.models import TOKEN_RESET_PASSWORD, TOKEN_VERIFY_EMAIL, OneTimeToken, User

TOKEN_LIFETIMES = {
    TOKEN_VERIFY_EMAIL: timedelta(hours=24),
    TOKEN_RESET_PASSWORD: timedelta(minutes=30),
}


async def issue_token(db: AsyncSession, user: User, kind: str) -> str:
    """Invalidate earlier tokens of the same kind and issue a fresh one."""
    now = utcnow()
    await db.execute(
        update(OneTimeToken)
        .where(
            OneTimeToken.user_id == user.id,
            OneTimeToken.kind == kind,
            OneTimeToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    token = new_token()
    db.add(
        OneTimeToken(
            user_id=user.id,
            kind=kind,
            token_hash=hash_token(token),
            expires_at=now + TOKEN_LIFETIMES[kind],
        )
    )
    await db.flush()
    return token


async def consume_token(db: AsyncSession, token: str, kind: str) -> User | None:
    """Return the user if the token is valid and unused, marking it used. Else None."""
    result = await db.execute(
        select(OneTimeToken).where(
            OneTimeToken.token_hash == hash_token(token), OneTimeToken.kind == kind
        )
    )
    row = result.scalar_one_or_none()
    now = utcnow()
    if row is None or row.used_at is not None or row.expires_at < now:
        return None
    row.used_at = now
    user = await db.get(User, row.user_id)
    await db.flush()
    return user
