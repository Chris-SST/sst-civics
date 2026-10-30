"""Email-link sign-in (D-006): request, consume, expiry, reuse, enumeration, limits, admins."""

from __future__ import annotations

from datetime import timedelta

import pyotp
from sqlalchemy import select, text, update

from app.auth.email_link import send_sign_in_link
from app.db import SessionLocal, utcnow
from app.email.backend import memory_outbox
from app.models import TOKEN_SIGN_IN, OneTimeToken, User
from tests.conftest import (
    ADMIN_PASSWORD,
    create_admin,
    last_email_link,
    link_sign_in,
    login,
    signup_and_verify,
    signup_body,
    token_from_link,
)


async def _request(api, email: str, **extra):
    return await api.post("/api/auth/link", json={"email": email, "locale": "en", **extra})


async def test_link_signs_in_a_learner(api):
    await signup_and_verify(api, "link@example.ch")
    await api.post("/api/auth/logout")
    memory_outbox.clear()
    r = await _request(api, "Link@Example.ch", locale="de")
    assert r.status_code == 202 and r.json() == {"status": "check_email"}
    assert len(memory_outbox.messages) == 1
    msg = memory_outbox.messages[0]
    assert msg.to == "link@example.ch" and msg.subject == "Ihr Anmeldelink"
    link = last_email_link()
    assert "/auth/link?token=" in link

    r = await api.post("/api/auth/link/consume", json={"token": token_from_link(link)})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["email"] == "link@example.ch"
    assert me["session"]["mfa_pending"] is False
    assert 0 < me["session"]["reauth_seconds_left"] <= 600
    # The token is stored only as a hash.
    async with SessionLocal() as db:
        hashes = (await db.execute(select(OneTimeToken.token_hash))).scalars().all()
    assert token_from_link(link) not in hashes


async def test_link_is_single_use(api, api2):
    await signup_and_verify(api, "once@example.ch")
    await _request(api, "once@example.ch")
    token = token_from_link(last_email_link())
    assert (await api.post("/api/auth/link/consume", json={"token": token})).status_code == 200
    r = await api2.post("/api/auth/link/consume", json={"token": token})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_token"
    assert (await api2.get("/api/auth/me")).status_code == 401


async def test_expired_link_is_refused(api):
    await signup_and_verify(api, "late@example.ch")
    await _request(api, "late@example.ch")
    token = token_from_link(last_email_link())
    async with SessionLocal() as db:
        await db.execute(
            update(OneTimeToken)
            .where(OneTimeToken.kind == TOKEN_SIGN_IN)
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )
        await db.commit()
    r = await api.post("/api/auth/link/consume", json={"token": token})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_token"


async def test_link_lasts_fifteen_minutes_and_new_link_replaces_old(api):
    await signup_and_verify(api, "two@example.ch")
    await _request(api, "two@example.ch")
    first = token_from_link(last_email_link())
    await _request(api, "two@example.ch")
    second = token_from_link(last_email_link())
    async with SessionLocal() as db:
        rows = (
            (await db.execute(select(OneTimeToken).where(OneTimeToken.kind == TOKEN_SIGN_IN)))
            .scalars()
            .all()
        )
    live = [t for t in rows if t.used_at is None]
    assert len(rows) == 2 and len(live) == 1
    lifetime = live[0].expires_at - live[0].created_at
    assert timedelta(minutes=14) < lifetime <= timedelta(minutes=15, seconds=1)
    assert (await api.post("/api/auth/link/consume", json={"token": first})).status_code == 400
    assert (await api.post("/api/auth/link/consume", json={"token": second})).status_code == 200


async def test_unknown_email_gets_the_same_answer_and_no_account(api):
    await signup_and_verify(api, "known@example.ch")
    memory_outbox.clear()
    known = await _request(api, "known@example.ch")
    unknown = await _request(api, "nobody@example.ch")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(memory_outbox.messages) == 1  # only the known address gets mail
    async with SessionLocal() as db:
        emails = (await db.execute(select(User.email))).scalars().all()
        assert emails == ["known@example.ch"]
        assert await send_sign_in_link(db, "nobody@example.ch", "en") is False


async def test_link_confirms_an_unverified_address(api):
    r = await api.post("/api/auth/signup", json=signup_body("new@example.ch", password=None))
    assert r.status_code == 201
    r = await link_sign_in(api, "new@example.ch")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["me"]["user"]["email_verified"] is True


async def test_link_next_is_limited_to_known_pages(api):
    await signup_and_verify(api, "next@example.ch")
    await _request(api, "next@example.ch", next="/account")
    assert "/auth/link?next=%2Faccount&token=" in last_email_link()
    r = await _request(api, "next@example.ch", next="https://evil.example")
    assert r.status_code == 422


async def test_link_rate_limit_per_email_and_per_ip(api):
    for _ in range(5):
        assert (await _request(api, "flood@example.ch")).status_code == 202
    r = await _request(api, "flood@example.ch")
    assert r.status_code == 429 and r.json()["detail"] == "rate_limited"
    # Other addresses from the same IP still work until the per-IP limit (20 an hour).
    for i in range(14):  # 6 hits so far from this IP
        assert (await _request(api, f"other{i}@example.ch")).status_code == 202
    assert (await _request(api, "fresh@example.ch")).status_code == 429


async def test_consume_rate_limit(api):
    for _ in range(30):
        r = await api.post("/api/auth/link/consume", json={"token": "x" * 43})
        assert r.status_code == 400
    r = await api.post("/api/auth/link/consume", json={"token": "x" * 43})
    assert r.status_code == 429


async def test_admin_via_link_lands_in_mfa_pending(api):
    admin = await create_admin("admin@sst-example.ch", totp=True)
    r = await link_sign_in(api, "admin@sst-example.ch")
    assert r.status_code == 200 and r.json()["status"] == "mfa_required"
    assert r.json()["me"]["session"]["mfa_pending"] is True
    assert (await api.get("/api/admin/overview")).status_code == 403
    r = await api.post("/api/auth/totp/verify", json={"code": pyotp.TOTP(admin.totp_secret).now()})
    assert r.status_code == 200
    assert (await api.get("/api/admin/overview")).status_code == 200


async def test_admin_without_totp_via_link_must_set_it_up(api):
    await create_admin("admin@sst-example.ch")
    r = await link_sign_in(api, "admin@sst-example.ch")
    assert r.json()["status"] == "mfa_setup_required"
    assert (await api.get("/api/admin/overview")).status_code == 403
    # Password login behaves the same way.
    r = await login(api, "admin@sst-example.ch", ADMIN_PASSWORD)
    assert r.json()["status"] == "mfa_setup_required"


async def test_inactive_account_gets_no_link(api):
    await signup_and_verify(api, "off@example.ch")
    async with SessionLocal() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()
    memory_outbox.clear()
    assert (await _request(api, "off@example.ch")).status_code == 202
    assert not memory_outbox.messages


async def test_verification_link_signs_in(api, api2):
    r = await api.post("/api/auth/signup", json=signup_body("first@example.ch", password=None))
    assert r.status_code == 201
    token = token_from_link(last_email_link())
    r = await api2.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    me = (await api2.get("/api/auth/me")).json()
    assert me["user"]["email_verified"] is True and me["user"]["has_password"] is False


async def test_totp_secret_is_encrypted_at_rest(api):
    await create_admin("admin@sst-example.ch")
    await login(api, "admin@sst-example.ch", ADMIN_PASSWORD)
    secret = (await api.post("/api/auth/totp/setup")).json()["secret"]
    async with SessionLocal() as db:
        raw = (await db.execute(text("SELECT totp_secret FROM users"))).scalar_one()
        user = (await db.execute(select(User))).scalar_one()
    assert raw != secret and secret not in raw
    assert raw.startswith("f1:")
    assert user.totp_secret == secret
    r = await api.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200


async def test_old_tokens_are_purged(api):
    from worker.tasks import purge_sessions

    await signup_and_verify(api, "purge@example.ch")
    await _request(api, "purge@example.ch")
    async with SessionLocal() as db:
        await db.execute(
            update(OneTimeToken)
            .where(OneTimeToken.kind == TOKEN_SIGN_IN)
            .values(expires_at=utcnow() - timedelta(days=2))
        )
        await db.commit()
    assert await purge_sessions({}) >= 1
    async with SessionLocal() as db:
        kinds = (await db.execute(select(OneTimeToken.kind))).scalars().all()
    assert TOKEN_SIGN_IN not in kinds
