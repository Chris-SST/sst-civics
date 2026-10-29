from __future__ import annotations

from datetime import timedelta

from app.billing.access import FULL, NONE, READ_ONLY, compute_access
from app.db import utcnow
from app.email import messages
from app.models import Family
from tests.conftest import parent_logged_in


def fam(**kw) -> Family:
    f = Family(
        locale="en", quantity=1, cancel_at_period_end=False, payment_warning=False, tutor_credits=0
    )
    for k, v in kw.items():
        setattr(f, k, v)
    return f


def test_compute_access_matrix():
    assert compute_access(None) == NONE
    assert compute_access(fam()) == NONE
    assert compute_access(fam(subscription_status="trialing")) == FULL
    assert compute_access(fam(subscription_status="active")) == FULL
    assert compute_access(fam(subscription_status="past_due", past_due_since=utcnow())) == FULL
    assert (
        compute_access(
            fam(
                subscription_status="past_due",
                past_due_since=utcnow() - timedelta(days=7, minutes=1),
            )
        )
        == READ_ONLY
    )
    for s in ("canceled", "unpaid", "incomplete_expired"):
        assert compute_access(fam(subscription_status=s)) == READ_ONLY
    assert compute_access(fam(subscription_status="incomplete")) == NONE
    assert compute_access(fam(free_access_until=utcnow() + timedelta(days=1))) == FULL
    assert compute_access(fam(free_access_until=utcnow() - timedelta(days=1))) == NONE
    assert (
        compute_access(
            fam(subscription_status="canceled", free_access_until=utcnow() + timedelta(days=1))
        )
        == FULL
    )


def test_all_email_messages_render_in_every_language():
    params = {
        "link": "https://x",
        "first_name": "A",
        "role": "tutor",
        "scope": "student",
        "reason": "self_harm",
        "amount": "1.00",
        "threshold": "8.00",
        "period": "2026-10",
    }
    for kind in messages.TEXTS:
        for locale in ("en", "de", "fr", "it"):
            m = messages.build(kind, locale, "a@b.ch", **params)
            assert m.subject and "https://x" in m.text
            assert "{" not in m.text


async def test_csrf_required_for_authenticated_writes(api):
    await parent_logged_in(api)
    r = await api.post("/api/family/settings", json={"locale": "fr"}, csrf=False)
    assert r.status_code == 405 or r.status_code == 403  # PATCH route; POST hits CSRF first
    r = await api.client.patch("/api/family/settings", json={"locale": "fr"})
    assert r.status_code == 403 and r.json()["detail"] == "csrf_failed"
    r = await api.client.patch(
        "/api/family/settings", json={"locale": "fr"}, headers={"X-CSRF-Token": "wrong"}
    )
    assert r.status_code == 403
    r = await api.patch("/api/family/settings", json={"locale": "fr"})
    assert r.status_code == 200
    assert (await api.get("/api/auth/me")).json()["user"]["locale"] == "fr"
