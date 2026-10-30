from __future__ import annotations

from app.config import get_settings
from tests.conftest import admin_logged_in, create_admin, learner_logged_in


async def test_admin_views_as_learner_then_returns(api, api2):
    me = await learner_logged_in(api2, "lina@example.ch")
    learner_id = me["user"]["id"]
    await admin_logged_in(api)

    r = await api.post(f"/api/admin/impersonate/{learner_id}")
    assert r.status_code == 200 and r.json()["role"] == "learner"
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["role"] == "learner"
    assert me["session"]["impersonated_by"] == "admin@sst-example.ch"
    assert (await api.get("/api/tutor/overview")).status_code == 200
    # No admin powers while viewing as the learner
    assert (await api.get("/api/admin/overview")).status_code == 403

    r = await api.post("/api/auth/stop-impersonation")
    assert r.status_code == 200
    me = (await api.get("/api/auth/me")).json()
    assert me["user"]["role"] == "admin" and me["session"]["impersonated_by"] is None
    assert (await api.get("/api/admin/overview")).status_code == 200

    actions = [a["action"] for a in (await api.get("/api/admin/audit")).json()]
    assert actions.count("user.impersonate") == 1
    assert actions.count("user.impersonate.stop") == 1


async def test_admin_cannot_view_as_another_admin(api):
    other = await create_admin("a2@sst-example.ch")
    admin = await admin_logged_in(api)
    assert (await api.post(f"/api/admin/impersonate/{other.id}")).status_code == 400
    assert (await api.post(f"/api/admin/impersonate/{admin.id}")).status_code == 400


async def test_impersonation_refused_in_production_and_for_non_admins(api, api2, monkeypatch):
    me = await learner_logged_in(api2, "lina@example.ch")
    learner_id = me["user"]["id"]
    # A learner cannot use the endpoint at all
    assert (await api2.post(f"/api/admin/impersonate/{learner_id}")).status_code == 403
    await admin_logged_in(api)
    monkeypatch.setattr(get_settings(), "app_env", "production")
    r = await api.post(f"/api/admin/impersonate/{learner_id}")
    assert r.status_code == 403 and r.json()["detail"] == "impersonation_disabled"
    # Stop without impersonating is a clean error
    assert (await api.post("/api/auth/stop-impersonation")).status_code == 400
