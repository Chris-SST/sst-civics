from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import one_time, totp
from app.auth.me import build_me
from app.auth.passwords import hash_password, password_is_acceptable, verify_password
from app.auth.ratelimit import hit
from app.auth.schemas import (
    AcceptInviteIn,
    EmailIn,
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
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import AuthContext, auth_any_state, client_ip
from app.email.messages import app_link
from app.jobs import send_email_job
from app.models import (
    ROLE_ADULT,
    ROLE_PARENT,
    TOKEN_RESET_PASSWORD,
    TOKEN_STAFF_INVITE,
    TOKEN_STUDENT_INVITE,
    TOKEN_VERIFY_EMAIL,
    Family,
    User,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def _user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username.lower().strip()))
    return result.scalar_one_or_none()


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
    if body.account_type == "parent" and not body.guardian_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "guardian_confirmation_required")
    if not password_is_acceptable(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
    email = body.email.lower().strip()
    if await _user_by_email(db, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email_in_use")

    now = utcnow()
    family = Family(
        locale=body.locale,
        terms_version=get_settings().terms_version,
        terms_accepted_at=now,
        guardian_confirmed_at=now if body.account_type == "parent" else None,
    )
    db.add(family)
    await db.flush()
    user = User(
        family_id=family.id,
        role=ROLE_PARENT if body.account_type == "parent" else ROLE_ADULT,
        email=email,
        password_hash=hash_password(body.password),
        locale=body.locale,
    )
    db.add(user)
    await db.flush()
    await _send_verification(user, db)
    await db.commit()
    return {"status": "check_email"}


@router.post("/verify-email")
async def verify_email(body: TokenIn, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    user = await one_time.consume_token(db, body.token, TOKEN_VERIFY_EMAIL)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_token")
    user.email_verified_at = user.email_verified_at or utcnow()
    await db.commit()
    return {"status": "verified"}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    body: EmailIn, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not await hit(f"resend:{client_ip(request)}", 10, 3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")
    user = await _user_by_email(db, body.email)
    if user is not None and user.email_verified_at is None:
        await _send_verification(user, db)
        await db.commit()
    return {"status": "check_email"}


@router.post("/login", response_model=LoginOut)
async def login(
    body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginOut:
    settings = get_settings()
    ident = body.identifier.lower().strip()
    ip = client_ip(request)
    window = settings.login_rate_window_seconds
    ok_ip = await hit(f"login:ip:{ip}", settings.login_rate_limit * 3, window)
    ok_id = await hit(f"login:id:{ident}", settings.login_rate_limit, window)
    if not (ok_ip and ok_id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    if "@" in ident:
        user = await _user_by_email(db, ident)
    else:
        user = await _user_by_username(db, ident)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user.email and user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")

    mfa_pending = user.totp_enabled
    token = await create_session(db, user, mfa_pending=mfa_pending)
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
    user = await _user_by_email(db, body.email)
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


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteIn, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    if not password_is_acceptable(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "weak_password")
    user = await one_time.consume_token(db, body.token, TOKEN_STUDENT_INVITE)
    if user is None:
        user = await one_time.consume_token(db, body.token, TOKEN_STAFF_INVITE)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_token")
    user.password_hash = hash_password(body.password)
    user.email_verified_at = user.email_verified_at or utcnow()
    user.is_active = True
    await db.commit()
    return {"status": "invite_accepted"}


@router.post("/totp/setup", response_model=TotpSetupOut)
async def totp_setup(
    ctx: AuthContext = Depends(auth_any_state), db: AsyncSession = Depends(get_db)
) -> TotpSetupOut:
    user = ctx.user
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "totp_already_enabled")
    secret = totp.new_secret()
    user.totp_secret = secret
    await db.commit()
    label = user.email or user.username or str(user.id)
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
