from __future__ import annotations

import uuid
from datetime import timedelta

from app.billing.access import compute_access, has_access
from app.db import utcnow
from app.email import messages
from app.models import ROLE_ADMIN, ROLE_LEARNER, Entitlement, User
from tests.conftest import learner_logged_in


def learner(*entitlements: Entitlement, role: str = ROLE_LEARNER) -> User:
    user = User(id=uuid.uuid4(), role=role, email="l@example.ch", canton="zh", is_active=True)
    for e in entitlements:
        e.user_id = user.id
        user.entitlements.append(e)
    return user


def ent(canton: str = "zh", start_days: float = -1, end_days: float = 30, **kw) -> Entitlement:
    now = utcnow()
    return Entitlement(
        id=uuid.uuid4(),
        canton=canton,
        starts_at=now + timedelta(days=start_days),
        expires_at=now + timedelta(days=end_days),
        source=kw.get("source", "admin"),
    )


def test_has_access_with_active_entitlement():
    user = learner(ent("zh"))
    assert has_access(user, "zh", utcnow()) is True
    assert has_access(user, "ag", utcnow()) is False


def test_has_access_with_expired_entitlement():
    user = learner(ent("zh", start_days=-200, end_days=-1))
    assert has_access(user, "zh", utcnow()) is False
    # It was valid while it ran
    assert has_access(user, "zh", utcnow() - timedelta(days=100)) is True
    # Not yet started
    assert has_access(learner(ent("zh", start_days=1, end_days=10)), "zh", utcnow()) is False


def test_has_access_with_missing_entitlement():
    assert has_access(learner(), "zh", utcnow()) is False
    assert has_access(None, "zh", utcnow()) is False
    inactive = learner(ent("zh"))
    inactive.is_active = False
    assert has_access(inactive, "zh", utcnow()) is False
    # Admins see every canton
    assert has_access(learner(role=ROLE_ADMIN), "ag", utcnow()) is True


def test_compute_access_per_canton_takes_the_longest_entitlement():
    short, long_, expired = ent("zh", end_days=10), ent("zh", end_days=90), ent("ag", end_days=-1)
    user = learner(short, long_, expired, ent("ag", end_days=5, source="trial"))
    access = compute_access(user, user.entitlements)
    assert set(access) == {"zh", "ag"}
    assert access["zh"].expires_at == long_.expires_at
    assert access["ag"].source == "trial"
    # Entitlements of other users are ignored
    assert compute_access(learner(), [ent("zh")]) == {}


def test_all_email_messages_render_in_every_language():
    params = {
        "link": "https://x",
        "scope": "learner",
        "amount": "1.00",
        "threshold": "8.00",
        "period": "2026-10",
    }
    assert set(messages.TEXTS) == {
        "verify_email",
        "reset_password",
        "sign_in_link",
        "account_deleted",
        "cost_alert",
    }
    for kind in messages.TEXTS:
        for locale in ("en", "de", "fr", "it", "sq"):
            m = messages.build(kind, locale, "a@b.ch", **params)
            assert m.subject
            assert kind == "account_deleted" or "https://x" in m.text
            assert "{" not in m.text


async def test_csrf_required_for_authenticated_writes(api):
    await learner_logged_in(api)
    body = {"course_key": "ib_maths_aa_hl", "topic_code": "AA-1.1"}
    r = await api.post("/api/tutor/conversations", json=body, csrf=False)
    assert r.status_code == 403 and r.json()["detail"] == "csrf_failed"
    r = await api.client.post(
        "/api/tutor/conversations", json=body, headers={"X-CSRF-Token": "wrong"}
    )
    assert r.status_code == 403 and r.json()["detail"] == "csrf_failed"
    # With the token the request reaches the route, which refuses it for lack of access
    r = await api.post("/api/tutor/conversations", json=body)
    assert r.status_code == 403 and r.json()["detail"] == "no_access"
