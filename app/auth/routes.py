"""Sign-up, sign-in (email link or password), email verification, password reset and
two-factor authentication."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import one_time, totp
from app.auth.email_link import normalise_email, user_by_email
from app.auth.me import build_me
from app.auth.passwords import hash_password, password_is_acceptable, verify_password
from app.auth.ratelimit import hit
from app.auth.schemas import (
    EmailIn,
    LinkRequestIn,
    LoginIn,
    LoginOut,
    MeOut,
    ResetPasswordIn,
    SignupIn,
    TokenIn,
    TotpCodeIn,
    TotpSetupOut,
)
from app.auth.sessions import (
    clear_session_cookie,
    create_session,
    destroy_all_sessions,
    destroy_session,
    ensure_csrf_cookie,
    load_session,
    set_session_cookie,
)
from app.auth.tokens import hash_token
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import AuthContext, auth_any_state, client_ip
from app.email.messages import app_link
from app.jobs import enqueue, send_email_job
from app.models import (
    CANTONS,
    ROLE_LEARNER,
    TOKEN_RESET_PASSWORD,
    TOKEN_SIGN_IN,
    TOKEN_VERIFY_EMAIL,
    AuditLog,
    User,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _start_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
    *,
    via_email_link: bool,
) -> LoginOut:
    """Open a session after a password or an email link. Whoever has TOTP switched on (every
    admin, once set up) lands in `mfa_pending`, whichever way they signed in."""
    # Replace any session this browser already had.
    await destroy_session(db, request.cookies.get(get_settings().session_cookie_name))
    mfa_pending = user.totp_enabled
    token = await create_session(db, user, mfa_pending=mfa_pending, via_email_link=via_email_link)
    user.last_login_at = utcnow()
    await db.commit()
    set_session_cookie(response, token, user)

    session = await load_session(db, token)
    assert session is not None
    ctx = AuthContext(user=user, session=session)
    me_out = await build_me(db, ctx, request, response)
    if mfa_pending:
        return LoginOut(status="mfa_required", me=me_out)
    if user.is_staff and not user.totp_enabled:
        return LoginOut(status="mfa_setup_required", me=me_out)
    return LoginOut(status="ok", me=me_out)


async def _consume_allowed(request: Request) -> bool:
    limit = get_settings().link_consume_rate_limit
    return await hit(f"link:consume:{client_ip(request)}", limit, 900)


async def _send_verification(user: User, db: AsyncSession) -> None:
    token = await one_time.issue_token(db, user, TOKEN_VERIFY_EMAIL)
    await send_email_job(
        "verify_email",
        user.locale,
        user.email or "",
        link=app_link(f"/verify-email?token={token}"),
    )


@router.get("/csrf")
async def csrf(request: Request, response: Response) -> dict[str, str]:
    token = ensure_csrf_cookie(response, request.cookies.get(get_settings().csrf_cookie_name))
    return {"csrf_token": token}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupIn, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not await hit(f"signup:{client_ip(request)}", 20, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    if not body.accept_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "terms_required")
    if not body.age_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "age_confirmation_required")
    canton = body.canton.lower()
    if canton not in CANTONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_canton")
    # The password is optional: without one, the learner signs in by email link.
    if body.password is not None and not password_is_acceptable(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
    email = normalise_email(body.email)
    if await user_by_email(db, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email_in_use")

    now = utcnow()
    user = User(
        role=ROLE_LEARNER,
        email=email,
        password_hash=hash_password(body.password) if body.password is not None else None,
        locale=body.locale,
        study_language=body.study_language,
        canton=canton,
        age_confirmed_at=now,
        terms_version=get_settings().terms_version,
        terms_accepted_at=now,
    )
    db.add(user)
    await db.flush()
    await _send_verification(user, db)
    await db.commit()
    return {"status": "check_email"}


@router.post("/verify-email", response_model=LoginOut)
async def verify_email(
    body: TokenIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginOut:
    """Confirm the address. The verification email doubles as the first sign-in link."""
    if not await _consume_allowed(request):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    user = await one_time.consume_token(db, body.token, TOKEN_VERIFY_EMAIL)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_token")
    user.email_verified_at = user.email_verified_at or utcnow()
    return await _start_session(db, user, request, response, via_email_link=True)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    body: EmailIn, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not await hit(f"resend:{client_ip(request)}", 10, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    user = await user_by_email(db, body.email)
    if user is not None and user.email_verified_at is None:
        await _send_verification(user, db)
        await db.commit()
    return {"status": "check_email"}


@router.post("/link", status_code=status.HTTP_202_ACCEPTED)
async def request_link(body: LinkRequestIn, request: Request) -> dict[str, str]:
    """Send a one-time sign-in link (single use, 15 minutes). The answer, and the work done
    in this request, are the same whether or not the address has an account: the lookup and
    the email happen in the background job. An unknown address gets no account and no email;
    sign-up is a separate step."""
    settings = get_settings()
    email = normalise_email(body.email)
    ok_ip = await hit(f"link:ip:{client_ip(request)}", settings.link_rate_limit_per_ip, 3600)
    # The address is hashed so the rate-limit store never holds it.
    ok_email = await hit(
        f"link:email:{hash_token(email)}", settings.link_rate_limit_per_email, 3600
    )
    if not (ok_ip and ok_email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    await enqueue("send_sign_in_link", email=email, locale=body.locale, next_path=body.next)
    return {"status": "check_email"}


@router.post("/link/consume", response_model=LoginOut)
async def consume_link(
    body: TokenIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginOut:
    if not await _consume_allowed(request):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    user = await one_time.consume_token(db, body.token, TOKEN_SIGN_IN)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_token")
    # Opening the link proves the address, so it also confirms it.
    user.email_verified_at = user.email_verified_at or utcnow()
    return await _start_session(db, user, request, response, via_email_link=True)


@router.post("/login", response_model=LoginOut)
async def login(
    body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginOut:
    settings = get_settings()
    ident = normalise_email(body.email)
    ip = client_ip(request)
    window = settings.login_rate_window_seconds
    ok_ip = await hit(f"login:ip:{ip}", settings.login_rate_limit * 3, window)
    ok_id = await hit(f"login:id:{ident}", settings.login_rate_limit, window)
    if not (ok_ip and ok_id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    user = await user_by_email(db, ident)
    # A learner without a password fails here like a wrong password.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")
    return await _start_session(db, user, request, response, via_email_link=False)


@router.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    await destroy_session(db, request.cookies.get(get_settings().session_cookie_name))
    await db.commit()
    clear_session_cookie(response)
    return {"status": "logged_out"}


@router.get("/me", response_model=MeOut)
async def me(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(auth_any_state),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    return await build_me(db, ctx, request, response)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: EmailIn, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not await hit(f"forgot:{client_ip(request)}", 10, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    user = await user_by_email(db, body.email)
    if user is not None and user.is_active:
        token = await one_time.issue_token(db, user, TOKEN_RESET_PASSWORD)
        await send_email_job(
            "reset_password",
            user.locale,
            user.email or "",
            link=app_link(f"/reset-password?token={token}"),
        )
        await db.commit()
    return {"status": "check_email"}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordIn, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not password_is_acceptable(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
    user = await one_time.consume_token(db, body.token, TOKEN_RESET_PASSWORD)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_token")
    user.password_hash = hash_password(body.password)
    user.email_verified_at = user.email_verified_at or utcnow()
    await destroy_all_sessions(db, user.id)
    await db.commit()
    return {"status": "password_reset"}


@router.post("/totp/setup", response_model=TotpSetupOut)
async def totp_setup(
    ctx: AuthContext = Depends(auth_any_state), db: AsyncSession = Depends(get_db)
) -> TotpSetupOut:
    user = ctx.user
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "totp_already_enabled")
    secret = totp.new_secret()
    user.totp_secret = secret  # encrypted by the column type
    await db.commit()
    label = user.email or str(user.id)
    return TotpSetupOut(secret=secret, otpauth_uri=totp.provisioning_uri(secret, label))


@router.post("/totp/enable")
async def totp_enable(
    body: TotpCodeIn,
    ctx: AuthContext = Depends(auth_any_state),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user = ctx.user
    if user.totp_enabled or not user.totp_secret:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "totp_not_in_setup")
    if not totp.verify_code(user.totp_secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_code")
    user.totp_enabled = True
    ctx.session.mfa_pending = False
    await db.commit()
    return {"status": "totp_enabled"}


@router.post("/totp/verify")
async def totp_verify(
    body: TotpCodeIn,
    ctx: AuthContext = Depends(auth_any_state),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user = ctx.user
    if not ctx.session.mfa_pending:
        return {"status": "ok"}
    if not await hit(f"totp:{user.id}", 10, 900):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    if not user.totp_secret or not totp.verify_code(user.totp_secret, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_code")
    ctx.session.mfa_pending = False
    await db.commit()
    return {"status": "ok"}


@router.post("/stop-impersonation")
async def stop_impersonation(
    response: Response,
    ctx: AuthContext = Depends(auth_any_state),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Return from an admin "view as" session to the admin's own account."""
    admin_id = ctx.session.impersonator_user_id
    if not admin_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not_impersonating")
    admin = await db.get(User, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not_impersonating")
    await db.delete(ctx.session)
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="user.impersonate.stop",
            target_type="user",
            target_id=str(ctx.user.id),
        )
    )
    # The admin passed 2FA before impersonating, so the restored session is complete.
    token = await create_session(db, admin, mfa_pending=False)
    await db.commit()
    set_session_cookie(response, token, admin)
    return {"status": "ok"}
