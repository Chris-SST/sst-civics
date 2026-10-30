from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.billing import stripe_client
from app.billing.products import add_months
from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.llm.client import FakeProvider, set_provider
from app.models import (
    ENTITLEMENT_STRIPE,
    ENTITLEMENT_TRIAL,
    Attempt,
    AuditLog,
    Entitlement,
    Payment,
    Question,
    StripeEvent,
    User,
)
from tests.conftest import admin_logged_in, learner_logged_in

EMAIL = "learner@example.ch"

PRICES = [
    {
        "id": "price_zh",
        "lookup_key": "civics_pass_zh",
        "unit_amount": 2900,
        "currency": "chf",
        "recurring": None,
        "metadata": {"access_months": "6"},
    },
    {
        "id": "price_ag",
        "lookup_key": "civics_pass_ag",
        "unit_amount": 2900,
        "currency": "chf",
        "recurring": None,
        "metadata": {"access_months": "6"},
    },
    {
        "id": "price_ext",
        "lookup_key": "civics_extension",
        "unit_amount": 900,
        "currency": "chf",
        "recurring": None,
        "metadata": {"access_months": "3"},
    },
]


@pytest.fixture(autouse=True)
def fake_stripe(monkeypatch):
    calls: dict[str, list] = {"checkout": [], "customers": [], "refunds": [], "prices": []}

    def list_prices(keys):
        calls["prices"].append(keys)
        return [p for p in PRICES if p["lookup_key"] in keys]

    def create_customer(email):
        calls["customers"].append(email)
        return {"id": f"cus_{len(calls['customers'])}"}

    def create_checkout_session(params):
        calls["checkout"].append(params)
        return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}

    def create_refund(payment_intent_id, metadata, idempotency_key):
        calls["refunds"].append((payment_intent_id, metadata, idempotency_key))
        return {"id": "re_1", "status": "succeeded"}

    def construct_event(payload, signature):
        if signature != "valid":
            raise ValueError("bad signature")
        return json.loads(payload)

    monkeypatch.setattr(stripe_client, "list_prices_by_lookup_keys", list_prices)
    monkeypatch.setattr(stripe_client, "create_customer", create_customer)
    monkeypatch.setattr(stripe_client, "create_checkout_session", create_checkout_session)
    monkeypatch.setattr(stripe_client, "create_refund", create_refund)
    monkeypatch.setattr(stripe_client, "construct_event", construct_event)
    return calls


@pytest.fixture
def sale_cantons(monkeypatch):
    def set_(value: str) -> None:
        monkeypatch.setattr(get_settings(), "cantons_for_sale", value)

    return set_


async def webhook(api, event: dict, signature="valid"):
    return await api.client.post(
        "/api/billing/webhook",
        content=json.dumps(event),
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )


def session_event(
    event_id: str,
    uid: str,
    *,
    session_id: str = "cs_1",
    product: str = "civics_pass_zh",
    canton: str = "zh",
    amount: int = 2900,
    payment_status: str = "paid",
    etype: str = "checkout.session.completed",
    intent: str = "pi_1",
) -> dict:
    return {
        "id": event_id,
        "type": etype,
        "created": int(utcnow().timestamp()),
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "mode": "payment",
                "payment_status": payment_status,
                "customer": "cus_1",
                "client_reference_id": uid,
                "payment_intent": intent,
                "amount_total": amount,
                "currency": "chf",
                "metadata": {"product": product, "canton": canton},
                "customer_details": {"email": EMAIL, "name": "Someone"},
            }
        },
    }


def refund_event(event_id: str, intent: str = "pi_1", amount: int = 2900) -> dict:
    return {
        "id": event_id,
        "type": "charge.refunded",
        "created": int(utcnow().timestamp()),
        "data": {
            "object": {
                "id": "ch_1",
                "object": "charge",
                "payment_intent": intent,
                "amount": amount,
                "amount_refunded": amount,
                "refunded": True,
            }
        },
    }


async def _user(db, email: str = EMAIL) -> User:
    return (await db.execute(select(User).where(User.email == email))).scalar_one()


async def add_entitlement(
    email: str = EMAIL,
    *,
    canton: str = "zh",
    started_days_ago: int = 30,
    expires_in_days: int = 30,
    source: str = ENTITLEMENT_STRIPE,
) -> None:
    async with SessionLocal() as db:
        user = await _user(db, email)
        db.add(
            Entitlement(
                user_id=user.id,
                canton=canton,
                starts_at=utcnow() - timedelta(days=started_days_ago),
                expires_at=utcnow() + timedelta(days=expires_in_days),
                source=source,
            )
        )
        await db.commit()


async def entitlements(email: str = EMAIL) -> list[Entitlement]:
    async with SessionLocal() as db:
        user = await _user(db, email)
        rows = await db.execute(select(Entitlement).where(Entitlement.user_id == user.id))
        return list(rows.scalars().all())


async def payments() -> list[Payment]:
    async with SessionLocal() as db:
        return list((await db.execute(select(Payment))).scalars().all())


def close(a, b, seconds: int = 120) -> bool:
    return abs((a - b).total_seconds()) < seconds


# --- Products -------------------------------------------------------------------------------


async def test_products_read_prices_from_stripe_and_are_cached(api, fake_stripe):
    r = await api.get("/api/billing/products")
    assert r.status_code == 200
    out = {p["key"]: p for p in r.json()}
    assert set(out) == {"civics_pass_zh", "civics_extension"}  # Aargau not on sale yet
    assert out["civics_pass_zh"] == {
        "key": "civics_pass_zh",
        "kind": "pass",
        "canton": "zh",
        "amount_cents": 2900,
        "currency": "CHF",
        "months": 6,
        "available": True,
    }
    assert out["civics_extension"]["amount_cents"] == 900
    assert out["civics_extension"]["months"] == 3 and out["civics_extension"]["canton"] is None
    await api.get("/api/billing/products")
    assert len(fake_stripe["prices"]) == 1  # the second call came from the cache


async def test_products_show_period_and_price_as_stripe_has_them(api, monkeypatch):
    changed = [dict(p) for p in PRICES]
    changed[0] = {**changed[0], "unit_amount": 3400, "metadata": {"access_months": "12"}}
    monkeypatch.setattr(stripe_client, "list_prices_by_lookup_keys", lambda keys: changed)
    out = {p["key"]: p for p in (await api.get("/api/billing/products")).json()}
    assert out["civics_pass_zh"]["amount_cents"] == 3400 and out["civics_pass_zh"]["months"] == 12


async def test_cantons_for_sale_hides_and_shows_aargau(api, sale_cantons):
    await learner_logged_in(api)
    r = await api.post("/api/billing/checkout", json={"product": "civics_pass_ag"})
    assert r.status_code == 404 and r.json()["detail"] == "not_for_sale"
    sale_cantons("zh,ag")
    keys = {p["key"] for p in (await api.get("/api/billing/products")).json()}
    assert keys == {"civics_pass_zh", "civics_pass_ag", "civics_extension"}
    r = await api.post("/api/billing/checkout", json={"product": "civics_pass_ag"})
    assert r.status_code == 200, r.text


# --- Checkout -------------------------------------------------------------------------------


async def test_checkout_session_for_a_pass(api, fake_stripe):
    me = await learner_logged_in(api)
    assert me["access"]["free_tier"] is True and me["access"]["latest_payment"] is None
    r = await api.post("/api/billing/checkout", json={"product": "civics_pass_zh"})
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://checkout.stripe.com/")
    params = fake_stripe["checkout"][0]
    assert params["mode"] == "payment"
    assert "payment_method_types" not in params  # card and TWINT come from the Dashboard
    assert params["line_items"] == [{"price": "price_zh", "quantity": 1}]
    assert params["client_reference_id"] == me["user"]["id"]
    assert params["metadata"]["product"] == "civics_pass_zh"
    assert params["metadata"]["canton"] == "zh"
    assert params["customer"] == "cus_1"
    assert params["success_url"].startswith("http://localhost:5173/billing/return?status=success")
    assert "{CHECKOUT_SESSION_ID}" in params["success_url"]
    assert params["cancel_url"] == "http://localhost:5173/billing/return?status=cancelled"
    assert fake_stripe["customers"] == [EMAIL]  # only the email address is sent
    assert (await api.get("/api/auth/me")).json()["access"]["has_stripe_customer"] is True

    await api.post("/api/billing/checkout", json={"product": "civics_pass_zh"})
    assert fake_stripe["customers"] == [EMAIL]  # the customer is reused
    r = await api.post("/api/billing/checkout", json={"product": "nope"})
    assert r.status_code == 422


async def test_checkout_refuses_a_second_pass_but_offers_the_extension(api, fake_stripe):
    await learner_logged_in(api)
    await add_entitlement()
    r = await api.post("/api/billing/checkout", json={"product": "civics_pass_zh"})
    assert r.status_code == 409 and r.json()["detail"] == "pass_active"
    r = await api.post("/api/billing/checkout", json={"product": "civics_extension"})
    assert r.status_code == 200, r.text
    params = fake_stripe["checkout"][0]
    assert params["line_items"] == [{"price": "price_ext", "quantity": 1}]
    assert params["metadata"]["product"] == "civics_extension"
    assert params["metadata"]["canton"] == "zh"


async def test_extension_needs_an_active_or_recently_expired_pass(api):
    await learner_logged_in(api)
    body = {"product": "civics_extension"}
    r = await api.post("/api/billing/checkout", json=body)
    assert r.status_code == 409 and r.json()["detail"] == "no_pass_to_extend"
    await add_entitlement(source=ENTITLEMENT_TRIAL)  # a trial is not a pass
    r = await api.post("/api/billing/checkout", json=body)
    assert r.status_code == 409
    await add_entitlement(started_days_ago=300, expires_in_days=-100)
    r = await api.post("/api/billing/checkout", json=body)
    assert r.status_code == 409  # expired more than 90 days ago
    await add_entitlement(started_days_ago=200, expires_in_days=-30)
    r = await api.post("/api/billing/checkout", json=body)
    assert r.status_code == 200, r.text
    r = await api.post("/api/billing/checkout", json={**body, "canton": "ag"})
    assert r.status_code == 409  # no pass for Aargau


async def test_checkout_is_for_learners_only(api):
    await admin_logged_in(api)
    r = await api.post("/api/billing/checkout", json={"product": "civics_pass_zh"})
    assert r.status_code == 403


# --- Webhooks -------------------------------------------------------------------------------


async def test_webhook_signature_and_idempotency(api):
    event = {"id": "evt_1", "type": "ping", "data": {"object": {}}}
    assert (await webhook(api, event, signature="bad")).status_code == 400
    r = await webhook(api, event)
    assert r.status_code == 200 and r.json() == {"received": True}
    r = await webhook(api, event)
    assert r.json()["duplicate"] is True
    async with SessionLocal() as db:
        rows = (await db.execute(select(StripeEvent))).scalars().all()
        assert len(rows) == 1 and rows[0].processed_at is not None


async def test_paid_checkout_grants_the_pass_once(api):
    me = await learner_logged_in(api)
    uid = me["user"]["id"]
    assert (await webhook(api, session_event("evt_a", uid))).status_code == 200
    await webhook(api, session_event("evt_a", uid))  # same event again
    await webhook(api, session_event("evt_b", uid))  # same session, new event id
    await webhook(
        api, session_event("evt_c", uid, etype="checkout.session.async_payment_succeeded")
    )

    [ent] = await entitlements()
    assert ent.canton == "zh" and ent.source == "stripe"
    assert ent.stripe_checkout_session_id == "cs_1"
    assert close(ent.starts_at, utcnow())
    assert close(ent.expires_at, add_months(ent.starts_at, 6))
    [payment] = await payments()
    assert payment.user_id is not None and payment.entitlement_id == ent.id
    assert payment.product == "civics_pass_zh" and payment.canton == "zh" and payment.months == 6
    assert payment.amount_cents == 2900 and payment.currency == "chf"
    assert payment.stripe_payment_intent_id == "pi_1"

    me = (await api.get("/api/auth/me")).json()
    assert me["access"]["access"] == "full" and me["access"]["free_tier"] is False
    assert me["access"]["has_stripe_customer"] is True
    assert me["access"]["latest_payment"]["checkout_session_id"] == "cs_1"
    listed = (await api.get("/api/billing/payments")).json()
    assert len(listed) == 1 and listed[0]["currency"] == "CHF" and listed[0]["refunded_at"] is None


async def test_delayed_payment_is_granted_only_when_it_succeeds(api):
    me = await learner_logged_in(api)
    uid = me["user"]["id"]
    await webhook(api, session_event("evt_1", uid, payment_status="unpaid"))
    await webhook(api, session_event("evt_2", uid, etype="checkout.session.async_payment_failed"))
    assert await entitlements() == [] and await payments() == []
    await webhook(
        api, session_event("evt_3", uid, etype="checkout.session.async_payment_succeeded")
    )
    assert len(await entitlements()) == 1 and len(await payments()) == 1


async def test_extension_extends_an_active_pass_from_its_expiry(api):
    me = await learner_logged_in(api)
    await add_entitlement(expires_in_days=10)
    [before] = await entitlements()
    await webhook(
        api,
        session_event("evt_x", me["user"]["id"], product="civics_extension", amount=900),
    )
    [after] = await entitlements()
    assert after.id == before.id
    assert after.expires_at == add_months(before.expires_at, 3)
    [payment] = await payments()
    assert payment.entitlement_id == before.id and payment.months == 3


async def test_extension_of_an_expired_pass_runs_from_now(api):
    me = await learner_logged_in(api)
    await add_entitlement(started_days_ago=200, expires_in_days=-20)
    await webhook(
        api,
        session_event("evt_x", me["user"]["id"], product="civics_extension", amount=900),
    )
    [after] = await entitlements()
    assert close(after.expires_at, add_months(utcnow(), 3))
    assert (await api.get("/api/auth/me")).json()["access"]["access"] == "full"


async def test_refund_webhook_ends_the_pass_and_marks_the_payment(api):
    me = await learner_logged_in(api)
    await webhook(api, session_event("evt_a", me["user"]["id"]))
    assert (await api.get("/api/auth/me")).json()["access"]["access"] == "full"
    await webhook(api, refund_event("evt_r"))
    await webhook(api, refund_event("evt_r2"))  # repeated delivery changes nothing
    [payment] = await payments()
    assert payment.refunded_at is not None and payment.amount_refunded_cents == 2900
    [ent] = await entitlements()
    assert ent.expires_at <= utcnow()
    me = (await api.get("/api/auth/me")).json()
    assert me["access"]["access"] == "none" and me["access"]["free_tier"] is True
    assert me["access"]["latest_payment"]["refunded"] is True


async def test_refund_of_an_extension_takes_its_months_off_again(api):
    me = await learner_logged_in(api)
    await add_entitlement(expires_in_days=40)
    [before] = await entitlements()
    await webhook(
        api,
        session_event(
            "evt_x", me["user"]["id"], product="civics_extension", amount=900, intent="pi_ext"
        ),
    )
    await webhook(api, refund_event("evt_r", intent="pi_ext", amount=900))
    [after] = await entitlements()
    assert close(after.expires_at, before.expires_at, seconds=5)
    assert (await api.get("/api/auth/me")).json()["access"]["access"] == "full"


async def test_partial_refund_leaves_access_alone(api):
    me = await learner_logged_in(api)
    await webhook(api, session_event("evt_a", me["user"]["id"]))
    event = refund_event("evt_r")
    event["data"]["object"].update(amount_refunded=1000, refunded=False)
    await webhook(api, event)
    [payment] = await payments()
    assert payment.refunded_at is None and payment.amount_refunded_cents == 1000
    assert (await api.get("/api/auth/me")).json()["access"]["access"] == "full"


async def test_webhook_payload_is_stored_without_contact_details(api):
    me = await learner_logged_in(api)
    event = session_event("evt_pii", me["user"]["id"])
    event["data"]["object"]["customer_email"] = "someone@example.ch"
    event["data"]["object"]["customer_address"] = {"line1": "Street 1"}
    assert (await webhook(api, event)).status_code == 200
    async with SessionLocal() as db:
        row = await db.get(StripeEvent, "evt_pii")
    stored = json.dumps(row.payload)
    assert "someone@example.ch" not in stored and EMAIL not in stored
    assert "Street 1" not in stored and "customer_details" not in stored
    assert row.payload["data"]["object"]["customer"] == "cus_1"


# --- Refunds --------------------------------------------------------------------------------


async def _study(n: int, email: str = EMAIL) -> None:
    async with SessionLocal() as db:
        user = await _user(db, email)
        for i in range(n):
            q = Question(module_key="m", topic_code="t", question_text=f"Q{i}?", answer="A")
            db.add(q)
            await db.flush()
            db.add(Attempt(user_id=user.id, question_id=q.id, course_key="c", topic_code="t"))
        await db.commit()


async def _age_payment(days: int) -> None:
    async with SessionLocal() as db:
        payment = (await db.execute(select(Payment))).scalar_one()
        payment.paid_at = utcnow() - timedelta(days=days)
        await db.commit()


async def test_refund_eligibility(api):
    me = await learner_logged_in(api)
    r = await api.get("/api/billing/refund-eligibility")
    assert r.json()["eligible"] is False and r.json()["reason"] == "no_payment"

    await _study(10)  # free practice before buying does not count
    await webhook(api, session_event("evt_a", me["user"]["id"]))
    await _study(49)
    out = (await api.get("/api/billing/refund-eligibility")).json()
    assert out["eligible"] is True and out["reason"] is None
    assert out["questions_studied"] == 49 and out["max_questions"] == 50
    assert out["product"] == "civics_pass_zh" and out["window_days"] == 14

    await _study(1)
    out = (await api.get("/api/billing/refund-eligibility")).json()
    assert out["eligible"] is False and out["reason"] == "too_many_questions"


async def test_refund_eligibility_ends_after_14_days(api):
    me = await learner_logged_in(api)
    await webhook(api, session_event("evt_a", me["user"]["id"]))
    await _age_payment(13)
    assert (await api.get("/api/billing/refund-eligibility")).json()["eligible"] is True
    await _age_payment(15)
    out = (await api.get("/api/billing/refund-eligibility")).json()
    assert out["eligible"] is False and out["reason"] == "too_late"


async def test_admin_refund_calls_stripe_and_is_audited(api, api2, fake_stripe):
    me = await learner_logged_in(api2)
    await webhook(api2, session_event("evt_a", me["user"]["id"]))
    [payment] = await payments()
    admin = await admin_logged_in(api)

    detail = (await api.get(f"/api/admin/learners/{me['user']['id']}")).json()
    assert detail["payments"][0]["refund"]["eligible"] is True

    r = await api.post(f"/api/admin/payments/{payment.id}/refund")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "succeeded", "refund_id": "re_1"}
    assert fake_stripe["refunds"] == [
        ("pi_1", {"payment_id": str(payment.id)}, f"civics-refund-{payment.id}")
    ]
    async with SessionLocal() as db:
        audit = (
            (await db.execute(select(AuditLog).where(AuditLog.action == "payment.refund")))
            .scalars()
            .one()
        )
    assert audit.actor_user_id == admin.id and audit.target_id == str(payment.id)
    assert audit.meta["refund_id"] == "re_1" and audit.meta["override"] is False
    # Access changes only when Stripe confirms with charge.refunded.
    assert (await api2.get("/api/auth/me")).json()["access"]["access"] == "full"
    await webhook(api2, refund_event("evt_r"))
    assert (await api2.get("/api/auth/me")).json()["access"]["access"] == "none"
    r = await api.post(f"/api/admin/payments/{payment.id}/refund")
    assert r.status_code == 409 and r.json()["detail"] == "already_refunded"


async def test_admin_refund_outside_the_rule_needs_an_override(api, api2, fake_stripe):
    me = await learner_logged_in(api2)
    await webhook(api2, session_event("evt_a", me["user"]["id"]))
    [payment] = await payments()
    await _age_payment(20)
    await admin_logged_in(api)
    r = await api.post(f"/api/admin/payments/{payment.id}/refund")
    assert r.status_code == 409 and r.json()["detail"] == "refund_too_late"
    assert fake_stripe["refunds"] == []
    r = await api.post(f"/api/admin/payments/{payment.id}/refund", json={"override": True})
    assert r.status_code == 200
    r = await api.post("/api/admin/payments/not-a-uuid/refund")
    assert r.status_code == 404
    r = await api2.post(f"/api/admin/payments/{payment.id}/refund")
    assert r.status_code == 403


# --- Chat limit and free tier ---------------------------------------------------------------


async def test_chat_needs_an_entitlement_and_has_a_daily_limit(api, monkeypatch):
    provider = FakeProvider()
    set_provider(provider)
    try:
        me = await learner_logged_in(api)
        body = {"course_key": "ib_physics_sl", "topic_code": "PH-A.1"}
        r = await api.post("/api/tutor/conversations", json=body)
        assert r.status_code == 403 and r.json()["detail"] == "no_access"

        await webhook(api, session_event("evt_a", me["user"]["id"]))
        overview = (await api.get("/api/tutor/overview")).json()
        assert overview["access"] == "full" and overview["usage"]["daily_limit"] == 20
        monkeypatch.setattr(get_settings(), "ai_daily_message_limit", 1)
        r = await api.post("/api/tutor/conversations", json=body)
        assert r.status_code == 201, r.text
        url = f"/api/tutor/conversations/{r.json()['id']}/messages"
        assert (await api.post(url, json={"content": "Hi"})).status_code == 200
        r = await api.post(url, json={"content": "More?"})
        assert r.status_code == 429 and r.json()["detail"] == "daily_limit_reached"
    finally:
        set_provider(None)


# --- Admin grants ---------------------------------------------------------------------------


async def test_admin_grants_entitlement_and_learner_gains_access(api, api2):
    me = await learner_logged_in(api2, "pass@example.ch")
    uid = me["user"]["id"]
    assert (await api2.get("/api/billing/access")).json()["access"] == "none"
    await admin_logged_in(api)

    r = await api.get("/api/admin/learners?q=pass@")
    assert r.status_code == 200 and r.json()[0]["email"] == "pass@example.ch"
    assert r.json()[0]["access"] == "none" and r.json()[0]["entitlements"] == []

    until = (utcnow() + timedelta(days=30)).isoformat()
    r = await api.post(
        f"/api/admin/users/{uid}/entitlements", json={"canton": "ZH", "expires_at": until}
    )
    assert r.status_code == 201, r.text
    ent = r.json()
    assert ent["canton"] == "zh" and ent["source"] == "admin" and ent["active"] is True

    me = (await api2.get("/api/auth/me")).json()
    assert me["access"]["access"] == "full" and me["access"]["free_tier"] is False
    assert [e["canton"] for e in me["access"]["entitlements"]] == ["zh"]
    access = (await api2.get("/api/billing/access")).json()
    assert access["access"] == "full" and set(access["cantons"]) == {"zh"}

    # Access to another canton is separate
    r = await api.post(
        f"/api/admin/users/{uid}/entitlements",
        json={"canton": "ag", "expires_at": until, "source": "trial"},
    )
    assert r.status_code == 201 and r.json()["source"] == "trial"

    detail = (await api.get(f"/api/admin/learners/{uid}")).json()
    assert {e["canton"] for e in detail["entitlements"]} == {"zh", "ag"}
    assert detail["age_confirmed_at"] and detail["payments"] == []
    audit = (await api.get("/api/admin/audit")).json()
    assert [a["action"] for a in audit].count("entitlement.grant") == 2
    assert "learner.view" in {a["action"] for a in audit}
    overview = (await api.get("/api/admin/overview")).json()
    assert overview["learners"] == 1 and overview["active_entitlements"] == 2
    from app.main import app

    assert not [r for r in app.routes if "/plans" in getattr(r, "path", "")]  # no plans any more


async def test_admin_entitlement_validation(api, api2):
    me = await learner_logged_in(api2)
    uid = me["user"]["id"]
    admin = await admin_logged_in(api)
    until = (utcnow() + timedelta(days=30)).isoformat()
    past = (utcnow() - timedelta(days=1)).isoformat()
    url = f"/api/admin/users/{uid}/entitlements"
    r = await api.post(url, json={"canton": "xx", "expires_at": until})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_canton"
    r = await api.post(url, json={"canton": "zh", "expires_at": past})
    assert r.status_code == 400 and r.json()["detail"] == "invalid_period"
    r = await api.post(url, json={"canton": "zh", "expires_at": until, "source": "stripe"})
    assert r.status_code == 422
    r = await api.post(
        f"/api/admin/users/{admin.id}/entitlements", json={"canton": "zh", "expires_at": until}
    )
    assert r.status_code == 404
    # Learners cannot grant themselves access
    r = await api2.post(url, json={"canton": "zh", "expires_at": until})
    assert r.status_code == 403


# --- Worker and helpers ---------------------------------------------------------------------


async def test_nightly_job_counts_entitlements_ending_within_a_week(api):
    from worker.tasks import log_expiring_entitlements

    await learner_logged_in(api)
    await add_entitlement(expires_in_days=3)
    await add_entitlement(canton="ag", expires_in_days=30)
    await add_entitlement(expires_in_days=-1)
    assert await log_expiring_entitlements({}) == 1
    assert len(await entitlements()) == 3  # nothing is changed


def test_add_months_clamps_to_the_end_of_the_month():
    start = utcnow().replace(year=2026, month=8, day=31, hour=12)
    assert add_months(start, 6) == start.replace(year=2027, month=2, day=28)
    assert add_months(start, 3) == start.replace(month=11, day=30)
    assert add_months(start.replace(month=11, day=30), -3) == start.replace(day=30)
