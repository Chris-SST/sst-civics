"""One-time sign-in links sent by email (D-006).

The request handler only rate-limits and enqueues `send_sign_in_link`; the lookup, the token
and the email happen in the background job, so the answer and its timing are the same
whether or not the address has an account."""

from __future__ import annotations

from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import one_time
from app.email.messages import app_link
from app.jobs import send_email_job
from app.models import LANGUAGES, TOKEN_SIGN_IN, User

# Pages a link may return to; mirrors `LinkNext` in the schemas.
ALLOWED_NEXT = ("/account",)


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalise_email(email)))
    return result.scalar_one_or_none()


def link_path(token: str, next_path: str | None = None) -> str:
    # The token goes last so a mail client that truncates query strings breaks the link
    # visibly rather than silently dropping the destination.
    prefix = f"next={quote(next_path, safe='')}&" if next_path in ALLOWED_NEXT else ""
    return f"/auth/link?{prefix}token={token}"


async def send_sign_in_link(
    db: AsyncSession, email: str, locale: str, next_path: str | None = None
) -> bool:
    """Issue a link and email it if the address belongs to an active account. Returns
    whether an email was sent (for tests; the API never reveals it)."""
    user = await user_by_email(db, email)
    if user is None or not user.is_active or not user.email:
        return False
    token = await one_time.issue_token(db, user, TOKEN_SIGN_IN)
    await db.commit()
    language = locale if locale in LANGUAGES else user.locale
    await send_email_job(
        "sign_in_link", language, user.email, link=app_link(link_path(token, next_path))
    )
    return True
