"""The signed-in person's own account: profile choices, password, deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deletion import delete_account
from app.auth.me import build_me, reauth_seconds_left
from app.auth.passwords import hash_password, password_is_acceptable, verify_password
from app.auth.ratelimit import hit
from app.auth.schemas import DeleteAccountIn, MeOut, ProfileIn, RemovePasswordIn, SetPasswordIn
from app.auth.sessions import clear_session_cookie, destroy_other_sessions
from app.db import get_db
from app.deps import AuthContext, current_auth
from app.jobs import send_email_job
from app.models import CANTONS

router = APIRouter(prefix="/api/me", tags=["account"])


async def _check_password(ctx: AuthContext, password: str | None) -> bool:
    """Verify the person's password, rate-limited per account."""
    if not await hit(f"password:{ctx.user.id}", 10, 900):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    return bool(password) and verify_password(password or "", ctx.user.password_hash)


@router.patch("", response_model=MeOut)
async def update_profile(
    body: ProfileIn,
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(current_auth),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    user = ctx.user
    if body.canton is not None:
        canton = body.canton.lower()
        if canton not in CANTONS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_canton")
        user.canton = canton
    if body.locale is not None:
        user.locale = body.locale
    if body.study_language is not None:
        user.study_language = body.study_language
    await db.commit()
    return await build_me(db, ctx, request, response)


@router.post("/password")
async def set_password(
    body: SetPasswordIn,
    ctx: AuthContext = Depends(current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Set a first password, or change it (the current one is then required). Changing it
    signs out the person's other sessions."""
    user = ctx.user
    if not password_is_acceptable(body.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
    had_password = user.password_hash is not None
    if had_password and not await _check_password(ctx, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    user.password_hash = hash_password(body.new_password)
    if had_password:
        await destroy_other_sessions(db, user.id, ctx.session.id)
    await db.commit()
    return {"status": "password_set"}


@router.post("/password/remove")
async def remove_password(
    body: RemovePasswordIn,
    ctx: AuthContext = Depends(current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Learners only: sign in by email link from now on. Admins keep a password."""
    user = ctx.user
    if user.is_staff:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password_required_for_admins")
    if user.password_hash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no_password")
    if not await _check_password(ctx, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    user.password_hash = None
    await destroy_other_sessions(db, user.id, ctx.session.id)
    await db.commit()
    return {"status": "password_removed"}


@router.delete("")
async def delete_me(
    body: DeleteAccountIn,
    response: Response,
    ctx: AuthContext = Depends(current_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete the learner's own account. Re-authentication: the password, or a sign-in link
    consumed in the last 10 minutes."""
    user = ctx.user
    if ctx.session.impersonator_user_id is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_while_impersonating")
    if not user.is_learner:
        # Admin accounts are removed by another admin, so the app is never left without one.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    fresh_link = reauth_seconds_left(ctx.session) > 0
    if body.password is not None and user.password_hash is not None:
        if not await _check_password(ctx, body.password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    elif not fresh_link:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "reauth_required")

    email, locale = user.email, user.locale
    await delete_account(db, user)
    # The confirmation goes out before the deletion is committed, so the data is not gone
    # until the email has been handed over (or queued).
    if email:
        await send_email_job("account_deleted", locale, email)
    await db.commit()
    clear_session_cookie(response)
    return {"status": "deleted"}
