from __future__ import annotations

from app.email.backend import memory_outbox
from tests.conftest import (
    last_email_link,
    login,
    parent_logged_in,
    signup_and_verify,
    token_from_link,
)


async def test_signup_requires_terms_and_guardian(api):
    base = {"email": "p@example.ch", "password": "Parent-pass-123", "locale": "en"}
    r = await api.post(
        "/api/auth/signup", json={**base, "accept_terms": False, "guardian_confirmed": True}
    )
    assert r.status_code == 400 and r.json()["detail"] == "terms_required"
    r = await api.post(
        "/api/auth/signup", json={**base, "accept_terms": True, "guardian_confirmed": False}
    )
    assert r.status_code == 400 and r.json()["detail"] == "guardian_confirmation_required"


async def test_signup_sends_verification_and_blocks_login_until_verified(api):
    r = await api.post(
        "/api/auth/signup",
        json={
            "email": "P@Example.ch",
            "password": "Parent-pass-123",
            "locale": "de",
            "account_type": "parent",
            "guardian_confirmed": True,
            "accept_terms": True,
        },
    )
    assert r.status_code == 201
    assert len(memory_outbox.messages) == 1
    assert memory_outbox.messages[0].to == "p@example.ch"
    assert "Bestätigen" in memory_outbox.messages[0].subject

    r = await login(api, "p@example.ch", "Parent-pass-123")
    assert r.status_code == 403 and r.json()["detail"] == "email_not_verified"

    token = token_from_link(last_email_link())
    assert (await api.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    # Single use
    assert (await api.post("/api/auth/verify-email", json={"token": token})).status_code == 400

    r = await login(api, "p@example.ch", "Parent-pass-123")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["me"]["user"]["role"] == "parent"
    assert body["me"]["family"]["access"] == "none"
    assert body["me"]["family"]["student_count"] == 0


async def test_duplicate_email_rejected(api):
    await signup_and_verify(api, "dup@example.ch")
    r = await api.post(
        "/api/auth/signup",
        json={
            "email": "dup@example.ch",
            "password": "Parent-pass-123",
            "locale": "en",
            "account_type": "parent",
            "guardian_confirmed": True,
            "accept_terms": True,
        },
    )
    assert r.status_code == 409


async def test_wrong_password_and_logout(api):
    await parent_logged_in(api)
    assert (await api.get("/api/auth/me")).status_code == 200
    r = await api.post("/api/auth/logout")
    assert r.status_code == 200
    assert (await api.get("/api/auth/me")).status_code == 401
    r = await login(api, "parent@example.ch", "wrong-password-1")
    assert r.status_code == 401


async def test_login_rate_limit(api):
    await signup_and_verify(api, "rl@example.ch")
    for _ in range(10):
        r = await login(api, "rl@example.ch", "nope-nope-nope")
        assert r.status_code == 401
    r = await login(api, "rl@example.ch", "nope-nope-nope")
    assert r.status_code == 429


async def test_password_reset_flow(api, api2):
    await parent_logged_in(api, "reset@example.ch")
    memory_outbox.clear()
    # Unknown address still returns 202 and sends nothing
    r = await api2.post("/api/auth/forgot-password", json={"email": "nobody@example.ch"})
    assert r.status_code == 202 and not memory_outbox.messages

    r = await api2.post("/api/auth/forgot-password", json={"email": "reset@example.ch"})
    assert r.status_code == 202 and len(memory_outbox.messages) == 1
    token = token_from_link(last_email_link())

    r = await api2.post("/api/auth/reset-password", json={"token": token, "password": "short"})
    assert r.status_code == 422 or r.status_code == 400
    r = await api2.post(
        "/api/auth/reset-password", json={"token": token, "password": "New-parent-pass-456"}
    )
    assert r.status_code == 200
    # Token is single use
    r = await api2.post(
        "/api/auth/reset-password", json={"token": token, "password": "New-parent-pass-789"}
    )
    assert r.status_code == 400
    # Existing sessions are revoked, old password fails, new password works
    assert (await api.get("/api/auth/me")).status_code == 401
    assert (await login(api2, "reset@example.ch", "Parent-pass-123")).status_code == 401
    assert (await login(api2, "reset@example.ch", "New-parent-pass-456")).status_code == 200


async def test_adult_learner_signup(api):
    await signup_and_verify(api, "adult@example.ch", account_type="adult")
    r = await login(api, "adult@example.ch", "Parent-pass-123")
    assert r.json()["me"]["user"]["role"] == "adult"
    r = await api.get("/api/student/home")
    assert r.status_code == 200
    assert r.json()["tutor_available"] is False


async def test_security_headers_present(api):
    r = await api.get("/api/health")
    assert r.status_code == 200
    assert "Content-Security-Policy" in r.headers
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
