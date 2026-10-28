from __future__ import annotations

import pyotp

from app.email.backend import memory_outbox
from tests.conftest import admin_logged_in, create_staff, last_email_link, login, token_from_link


async def test_admin_must_set_up_2fa_before_using_admin_area(api):
    await create_staff("admin@sst-example.ch")
    r = await login(api, "admin@sst-example.ch", "Staff-pass-123")
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
    r = await login(api, "admin@sst-example.ch", "Staff-pass-123")
    assert r.json()["status"] == "mfa_required"
    assert (await api.get("/api/admin/overview")).status_code == 403
    r = await api.post("/api/auth/totp/verify", json={"code": "123456"})
    assert r.status_code == 400
    r = await api.post("/api/auth/totp/verify", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    assert (await api.get("/api/admin/overview")).status_code == 200


async def test_admin_invites_tutor_who_accepts_and_sets_up_2fa(api, api2):
    await admin_logged_in(api)
    memory_outbox.clear()
    r = await api.post(
        "/api/admin/users",
        json={
            "email": "tutor@sst-example.ch",
            "role": "tutor",
            "first_name": "Tamsin",
            "locale": "fr",
            "tagged_courses": ["ib_physics_hl"],
        },
    )
    assert r.status_code == 201, r.text
    assert memory_outbox.messages[-1].to == "tutor@sst-example.ch"
    assert "collaborateur" in memory_outbox.messages[-1].subject
    token = token_from_link(last_email_link())

    r = await api2.post(
        "/api/auth/accept-invite", json={"token": token, "password": "Tutor-pass-123"}
    )
    assert r.status_code == 200
    r = await login(api2, "tutor@sst-example.ch", "Tutor-pass-123")
    assert r.json()["status"] == "mfa_setup_required"
    assert (await api2.get("/api/tutor/dashboard")).status_code == 403
    secret = (await api2.post("/api/auth/totp/setup")).json()["secret"]
    r = await api2.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    r = await api2.get("/api/tutor/dashboard")
    assert r.status_code == 200
    assert r.json()["tagged_courses"] == ["ib_physics_hl"]
    # Tutors are not admins
    assert (await api2.get("/api/admin/overview")).status_code == 403

    staff = (await api.get("/api/admin/users?role=tutor")).json()
    assert staff[0]["email"] == "tutor@sst-example.ch" and staff[0]["totp_enabled"] is True


async def test_admin_can_reset_2fa(api, api2):
    await admin_logged_in(api)
    tutor = await create_staff("t2@sst-example.ch", "tutor", totp=True)
    r = await api.post(f"/api/admin/users/{tutor.id}/reset-2fa")
    assert r.status_code == 200
    r = await login(api2, "t2@sst-example.ch", "Staff-pass-123")
    assert r.json()["status"] == "mfa_setup_required"


async def test_parent_cannot_use_admin_endpoints(api):
    from tests.conftest import parent_logged_in

    await parent_logged_in(api)
    assert (await api.get("/api/admin/overview")).status_code == 403
    assert (await api.get("/api/admin/families")).status_code == 403
    assert (await api.get("/api/tutor/dashboard")).status_code == 403
