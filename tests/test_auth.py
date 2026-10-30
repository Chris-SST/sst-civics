from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.email.backend import memory_outbox
from app.models import User
from tests.conftest import (
    LEARNER_PASSWORD,
    last_email_link,
    learner_logged_in,
    login,
    signup_and_verify,
    signup_body,
    token_from_link,
)


async def test_signup_requires_terms_and_age_confirmation(api):
    r = await api.post("/api/auth/signup", json=signup_body("p@example.ch", accept_terms=False))
    assert r.status_code == 400 and r.json()["detail"] == "terms_required"
    r = await api.post("/api/auth/signup", json=signup_body("p@example.ch", age_confirmed=False))
    assert r.status_code == 400 and r.json()["detail"] == "age_confirmation_required"
    body = signup_body("p@example.ch")
    del body["age_confirmed"]
    r = await api.post("/api/auth/signup", json=body)
    assert r.status_code == 400 and r.json()["detail"] == "age_confirmation_required"
    assert not memory_outbox.messages
    async with SessionLocal() as db:
        assert (await db.execute(select(User))).scalars().first() is None


async def test_signup_rejects_unknown_canton(api):
    r = await api.post("/api/auth/signup", json=signup_body("p@example.ch", canton="xx"))
    assert r.status_code == 400 and r.json()["detail"] == "invalid_canton"


async def test_learner_signup_stores_only_the_listed_fields(api):
    r = await api.post(
        "/api/auth/signup",
        json=signup_body(
            "Learner@Example.ch", locale="de", study_language="fr", canton="AG", first_name="X"
        ),
    )
    assert r.status_code == 201
    async with SessionLocal() as db:
        user = (await db.execute(select(User))).scalars().one()
        assert user.role == "learner"
        assert user.email == "learner@example.ch"
        assert (user.locale, user.study_language, user.canton) == ("de", "fr", "ag")
        assert user.age_confirmed_at is not None and user.terms_accepted_at is not None
        assert not hasattr(user, "first_name")


async def test_signup_defaults_study_language_and_canton(api):
    body = signup_body("d@example.ch")
    del body["study_language"], body["canton"]
    assert (await api.post("/api/auth/signup", json=body)).status_code == 201
    async with SessionLocal() as db:
        user = (await db.execute(select(User))).scalars().one()
        assert (user.study_language, user.canton) == ("en", "zh")


async def test_signup_sends_verification_and_blocks_login_until_verified(api):
    r = await api.post("/api/auth/signup", json=signup_body("P@Example.ch", locale="de"))
    assert r.status_code == 201
    assert len(memory_outbox.messages) == 1
    assert memory_outbox.messages[0].to == "p@example.ch"
    assert "Bestätigen" in memory_outbox.messages[0].subject

    r = await login(api, "p@example.ch", LEARNER_PASSWORD)
    assert r.status_code == 403 and r.json()["detail"] == "email_not_verified"

    token = token_from_link(last_email_link())
    assert (await api.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    # Single use
    assert (await api.post("/api/auth/verify-email", json={"token": token})).status_code == 400

    r = await login(api, "p@example.ch", LEARNER_PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    me = body["me"]
    assert me["user"]["role"] == "learner"
    assert me["user"]["canton"] == "zh" and me["user"]["study_language"] == "en"
    assert me["access"] == {
        "access": "none",
        "canton": "zh",
        "entitlements": [],
        "has_stripe_customer": False,
    }
    assert "family" not in me


async def test_duplicate_email_rejected(api):
    await signup_and_verify(api, "dup@example.ch")
    r = await api.post("/api/auth/signup", json=signup_body("dup@example.ch"))
    assert r.status_code == 409


async def test_wrong_password_and_logout(api):
    await learner_logged_in(api)
    assert (await api.get("/api/auth/me")).status_code == 200
    r = await api.post("/api/auth/logout")
    assert r.status_code == 200
    assert (await api.get("/api/auth/me")).status_code == 401
    r = await login(api, "learner@example.ch", "wrong-password-1")
    assert r.status_code == 401


async def test_login_rate_limit(api):
    await signup_and_verify(api, "rl@example.ch")
    for _ in range(10):
        r = await login(api, "rl@example.ch", "nope-nope-nope")
        assert r.status_code == 401
    r = await login(api, "rl@example.ch", "nope-nope-nope")
    assert r.status_code == 429


async def test_password_reset_flow(api, api2):
    await learner_logged_in(api, "reset@example.ch")
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
        "/api/auth/reset-password", json={"token": token, "password": "New-learner-pass-456"}
    )
    assert r.status_code == 200
    # Token is single use
    r = await api2.post(
        "/api/auth/reset-password", json={"token": token, "password": "New-learner-pass-789"}
    )
    assert r.status_code == 400
    # Existing sessions are revoked, old password fails, new password works
    assert (await api.get("/api/auth/me")).status_code == 401
    assert (await login(api2, "reset@example.ch", LEARNER_PASSWORD)).status_code == 401
    assert (await login(api2, "reset@example.ch", "New-learner-pass-456")).status_code == 200


async def test_learner_has_no_second_factor_requirement(api):
    me = await learner_logged_in(api)
    assert me["session"]["mfa_setup_required"] is False
    r = await api.get("/api/tutor/overview")
    assert r.status_code == 200
    assert r.json()["tutor_enabled"] is False
    assert r.json()["access"] == "none"


async def test_removed_family_and_invite_routes_are_gone(api):
    await learner_logged_in(api)
    r = await api.post("/api/family/students", json={})
    assert r.status_code in (404, 405)
    r = await api.post("/api/auth/accept-invite", json={"token": "x" * 20, "password": "y" * 12})
    assert r.status_code in (404, 405)


async def test_security_headers_present(api):
    r = await api.get("/api/health")
    assert r.status_code == 200
    assert "Content-Security-Policy" in r.headers
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
