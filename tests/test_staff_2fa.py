from __future__ import annotations

import pyotp

from tests.conftest import ADMIN_PASSWORD, admin_logged_in, create_admin, learner_logged_in, login


async def test_admin_must_set_up_2fa_before_using_admin_area(api):
    await create_admin("admin@sst-example.ch")
    r = await login(api, "admin@sst-example.ch", ADMIN_PASSWORD)
    assert r.status_code == 200 and r.json()["status"] == "mfa_setup_required"
    assert (await api.get("/api/admin/overview")).status_code == 403
    assert (await api.get("/api/auth/me")).json()["session"]["mfa_setup_required"] is True

    r = await api.post("/api/auth/totp/setup")
    assert r.status_code == 200
    secret = r.json()["secret"]
    assert r.json()["otpauth_uri"].startswith("otpauth://totp/")

    r = await api.post("/api/auth/totp/enable", json={"code": "000000"})
    assert r.status_code == 400
    r = await api.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    assert (await api.get("/api/admin/overview")).status_code == 200

    # Next login asks for the code
    await api.post("/api/auth/logout")
    r = await login(api, "admin@sst-example.ch", ADMIN_PASSWORD)
    assert r.json()["status"] == "mfa_required"
    assert (await api.get("/api/admin/overview")).status_code == 403
    r = await api.post("/api/auth/totp/verify", json={"code": "123456"})
    assert r.status_code == 400
    r = await api.post("/api/auth/totp/verify", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    assert (await api.get("/api/admin/overview")).status_code == 200


async def test_admin_lists_admins_and_can_reset_2fa(api, api2):
    await admin_logged_in(api)
    other = await create_admin("a2@sst-example.ch", totp=True)
    admins = (await api.get("/api/admin/users")).json()
    assert {a["email"] for a in admins} == {"admin@sst-example.ch", "a2@sst-example.ch"}
    assert all(a["role"] == "admin" for a in admins)
    r = await api.post(f"/api/admin/users/{other.id}/reset-2fa")
    assert r.status_code == 200
    r = await login(api2, "a2@sst-example.ch", ADMIN_PASSWORD)
    assert r.json()["status"] == "mfa_setup_required"


async def test_staff_invites_are_gone(api):
    await admin_logged_in(api)
    r = await api.post("/api/admin/users", json={"email": "x@sst-example.ch", "role": "admin"})
    assert r.status_code == 405


async def test_learner_cannot_use_admin_or_review_endpoints(api):
    await learner_logged_in(api)
    assert (await api.get("/api/admin/overview")).status_code == 403
    assert (await api.get("/api/admin/learners")).status_code == 403
    assert (await api.get("/api/review/meta")).status_code == 403
    assert (await api.get("/api/review/translations")).status_code == 403
