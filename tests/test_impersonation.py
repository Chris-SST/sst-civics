from __future__ import annotations

from app.config import get_settings
from tests.conftest import admin_logged_in, create_staff, parent_logged_in


async def _parent_and_student(api2):
    me = await parent_logged_in(api2, "fam@example.ch")
    r = await api2.post(
        "/api/family/students",
        json={
            "first_name": "Lina",
            "year_of_birth": 2011,
            "curriculum": "ib_dp",
            "courses": ["ib_maths_aa_sl"],
            "locale": "en",
            "username": "lina",
            "password": "Lina-secret-99",
        },
    )
    return me["user"]["id"], r.json()["id"]


async def test_admin_views_as_parent_then_student_then_returns(api, api2):
    parent_id, student_id = await _parent_and_student(api2)
    await admin_logged_in(api)

    r = await api.post(f"/api/admin/impersonate/{parent_id}")
    assert r.status_code == 200 and r.json()["role"] == "parent"
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["role"] == "parent"
    assert me["session"]["impersonated_by"] == "Staff"
    assert (await api.get("/api/family/students")).status_code == 200
    # No admin powers while viewing as the parent
    assert (await api.get("/api/admin/overview")).status_code == 403

    r = await api.post("/api/auth/stop-impersonation")
    assert r.status_code == 200
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["role"] == "admin" and me["session"]["impersonated_by"] is None
    assert (await api.get("/api/admin/overview")).status_code == 200

    r = await api.post(f"/api/admin/impersonate/{student_id}")
    assert r.status_code == 200 and r.json()["role"] == "student"
    assert (await api.get("/api/student/home")).status_code == 200
    await api.post("/api/auth/stop-impersonation")

    actions = [a["action"] for a in (await api.get("/api/admin/audit")).json()]
    assert actions.count("user.impersonate") == 2
    assert actions.count("user.impersonate.stop") == 2


async def test_admin_views_as_tutor_without_2fa_setup(api):
    tutor = await create_staff("t@sst-example.ch", "tutor")
    admin = await admin_logged_in(api)
    r = await api.post(f"/api/admin/impersonate/{tutor.id}")
    assert r.status_code == 200
    assert (await api.get("/api/tutor/dashboard")).status_code == 200
    assert (await api.get("/api/auth/me")).json()["session"]["mfa_setup_required"] is False
    await api.post("/api/auth/stop-impersonation")
    # Cannot impersonate another admin
    assert (await api.post(f"/api/admin/impersonate/{admin.id}")).status_code == 400


async def test_impersonation_refused_in_production_and_for_non_admins(api, api2, monkeypatch):
    parent_id, _ = await _parent_and_student(api2)
    # A parent cannot use the endpoint at all
    assert (await api2.post(f"/api/admin/impersonate/{parent_id}")).status_code == 403
    await admin_logged_in(api)
    monkeypatch.setattr(get_settings(), "app_env", "production")
    r = await api.post(f"/api/admin/impersonate/{parent_id}")
    assert r.status_code == 403 and r.json()["detail"] == "impersonation_disabled"
    # Stop without impersonating is a clean error
    assert (await api.post("/api/auth/stop-impersonation")).status_code == 400
