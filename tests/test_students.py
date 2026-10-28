from __future__ import annotations

from app.email.backend import memory_outbox
from tests.conftest import last_email_link, login, parent_logged_in, token_from_link

STUDENT = {
    "first_name": "Lina",
    "year_of_birth": 2011,
    "curriculum": "ib_dp",
    "courses": ["ib_maths_aa_sl", "ib_physics_sl"],
    "locale": "en",
}


async def test_parent_adds_student_with_username(api, api2):
    await parent_logged_in(api)
    r = await api.post(
        "/api/family/students",
        json={**STUDENT, "username": "Lina.2011", "password": "Lina-secret-99"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "lina.2011"
    assert r.json()["invite_pending"] is False

    me = (await api.get("/api/auth/me")).json()
    assert me["family"]["student_count"] == 1

    # Student signs in with username
    r = await login(api2, "lina.2011", "Lina-secret-99")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["me"]["user"]["role"] == "student"
    home = await api2.get("/api/student/home")
    assert home.status_code == 200
    assert home.json()["first_name"] == "Lina"
    assert home.json()["access"] == "none"

    # Student cannot manage the family or see admin
    assert (await api2.get("/api/family/students")).status_code == 403
    assert (await api2.get("/api/admin/overview")).status_code == 403


async def test_student_invite_by_email(api, api2):
    await parent_logged_in(api)
    memory_outbox.clear()
    r = await api.post("/api/family/students", json={**STUDENT, "invite_email": "kid@example.ch"})
    assert r.status_code == 201, r.text
    assert r.json()["invite_pending"] is True
    assert memory_outbox.messages[-1].to == "kid@example.ch"
    token = token_from_link(last_email_link())

    r = await api2.post(
        "/api/auth/accept-invite", json={"token": token, "password": "Kid-pass-2026"}
    )
    assert r.status_code == 200
    r = await login(api2, "kid@example.ch", "Kid-pass-2026")
    assert r.status_code == 200 and r.json()["me"]["user"]["role"] == "student"


async def test_student_validation(api):
    await parent_logged_in(api)
    r = await api.post(
        "/api/family/students",
        json={**STUDENT, "year_of_birth": 1980, "username": "old", "password": "x" * 12},
    )
    assert r.status_code == 400 and r.json()["detail"] == "invalid_year_of_birth"
    r = await api.post(
        "/api/family/students", json={**STUDENT, "username": "ab", "password": "x" * 12}
    )
    assert r.status_code == 400 and r.json()["detail"] == "invalid_username"
    r = await api.post("/api/family/students", json={**STUDENT})
    assert r.status_code == 400 and r.json()["detail"] == "login_method_required"
    r = await api.post(
        "/api/family/students",
        json={**STUDENT, "courses": ["not_a_course"], "username": "okname", "password": "x" * 12},
    )
    assert r.status_code == 400 and r.json()["detail"] == "invalid_course"


async def test_parent_resets_student_password_and_removes_student(api, api2):
    await parent_logged_in(api)
    r = await api.post(
        "/api/family/students", json={**STUDENT, "username": "lina", "password": "Lina-secret-99"}
    )
    sid = r.json()["id"]
    assert (await login(api2, "lina", "Lina-secret-99")).status_code == 200

    r = await api.patch(f"/api/family/students/{sid}", json={"password": "Lina-newpass-1"})
    assert r.status_code == 200
    # Student session revoked after the parent changed the password
    assert (await api2.get("/api/auth/me")).status_code == 401
    assert (await login(api2, "lina", "Lina-newpass-1")).status_code == 200

    r = await api.delete(f"/api/family/students/{sid}")
    assert r.status_code == 204
    assert (await api.get("/api/family/students")).json() == []
    assert (await login(api2, "lina", "Lina-newpass-1")).status_code == 401


async def test_other_parent_cannot_touch_student(api, api2):
    await parent_logged_in(api, "a@example.ch")
    r = await api.post(
        "/api/family/students", json={**STUDENT, "username": "kid.a", "password": "Kid-a-secret-1"}
    )
    sid = r.json()["id"]
    await parent_logged_in(api2, "b@example.ch")
    assert (await api2.delete(f"/api/family/students/{sid}")).status_code == 404
    assert (
        await api2.patch(f"/api/family/students/{sid}", json={"first_name": "X"})
    ).status_code == 404
