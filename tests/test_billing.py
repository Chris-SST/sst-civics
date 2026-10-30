from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.billing import stripe_client
from app.db import SessionLocal, utcnow
from app.models import StripeEvent
from tests.conftest import admin_logged_in, learner_logged_in

PRICES = [
    {
        "id": "price_ai_m",
        "lookup_key": "ai_monthly",
        "unit_amount": 2400,
        "currency": "chf",
        "recurring": {"interval": "month"},
    },
    {
        "id": "price_ai_y",
        "lookup_key": "ai_annual",
        "unit_amount": 19900,
        "currency": "chf",
        "recurring": {"interval": "year"},
    },
    {
        "id": "price_hy",
        "lookup_key": "hybrid_monthly",
        "unit_amount": 14900,
        "currency": "chf",
        "recurring": {"interval": "month"},
    },
    {
        "id": "price_ask",
        "lookup_key": "ask_tutor_single",
        "unit_amount": 1900,
        "currency": "chf",
        "recurring": None,
    },
    {
        "id": "price_sprint",
        "lookup_key": "exam_sprint",
        "unit_amount": 34900,
        "currency": "chf",
        "recurring": None,
    },
]


@pytest.fixture(autouse=True)
def fake_stripe(monkeypatch):
    calls: dict[str, list] = {"checkout": [], "portal": [], "customers": []}

    def list_prices(keys):
        return [p for p in PRICES if p["lookup_key"] in keys]

    def create_customer(email, user_id, locale):
        calls["customers"].append((email, user_id, locale))
        return {"id": f"cus_{user_id[:8]}"}

    def create_checkout_session(params):
        calls["checkout"].append(params)
        return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}

    def create_portal_session(customer_id, return_url, locale):
        calls["portal"].append((customer_id, return_url, locale))
        return {"url": "https://billing.stripe.com/p/session/test"}

    def construct_event(payload, signature):
        if signature != "valid":
            raise ValueError("bad signature")
        return json.loads(payload)

    def retrieve_subscription(sub_id):
        raise RuntimeError("not available in tests")

    monkeypatch.setattr(stripe_client, "list_prices_by_lookup_keys", list_prices)
    monkeypatch.setattr(stripe_client, "create_customer", create_customer)
    monkeypatch.setattr(stripe_client, "create_checkout_session", create_checkout_session)
    monkeypatch.setattr(stripe_client, "create_portal_session", create_portal_session)
    monkeypatch.setattr(stripe_client, "construct_event", construct_event)
    monkeypatch.setattr(stripe_client, "retrieve_subscription", retrieve_subscription)
    return calls


async def webhook(api, event: dict, signature="valid"):
    return await api.client.post(
        "/api/billing/webhook",
        content=json.dumps(event),
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )


async def test_plans_listed_with_prices(api):
    r = await api.get("/api/billing/plans")
    assert r.status_code == 200
    plans = {p["key"]: p for p in r.json()}
    assert plans["ai_monthly"]["amount_cents"] == 2400
    assert plans["ai_monthly"]["interval"] == "month"
    assert plans["ai_monthly"]["monthly_message_limit"] == 300
    assert plans["hybrid_monthly"]["daily_message_limit"] == 80
    assert plans["ask_tutor_single"]["kind"] == "addon"


async def test_checkout_session_is_built_for_the_learner(api, fake_stripe):
    me = await learner_logged_in(api)
    r = await api.post("/api/billing/checkout", json={"plan_key": "ai_monthly"})
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://checkout.stripe.com/")
    params = fake_stripe["checkout"][0]
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_ai_m", "quantity": 1}]
    assert params["client_reference_id"] == me["user"]["id"]
    assert params["metadata"]["user_id"] == me["user"]["id"]
    assert params["customer"].startswith("cus_")
    assert fake_stripe["customers"][0][:2] == ("learner@example.ch", me["user"]["id"])
    assert (await api.get("/api/auth/me")).json()["access"]["has_stripe_customer"] is True

    r = await api.post("/api/billing/checkout", json={"plan_key": "nope"})
    assert r.status_code == 404


async def test_one_off_checkout_uses_payment_mode(api, fake_stripe):
    await learner_logged_in(api)
    r = await api.post(
        "/api/billing/checkout", json={"plan_key": "ask_tutor_single", "quantity": 2}
    )
    assert r.status_code == 200
    params = fake_stripe["checkout"][0]
    assert params["mode"] == "payment" and params["line_items"][0]["quantity"] == 2


async def test_webhook_signature_and_idempotency(api):
    await learner_logged_in(api)
    event = {"id": "evt_1", "type": "ping", "data": {"object": {}}}
    assert (await webhook(api, event, signature="bad")).status_code == 400
    r = await webhook(api, event)
    assert r.status_code == 200 and r.json() == {"received": True}
    r = await webhook(api, event)
    assert r.json()["duplicate"] is True
    async with SessionLocal() as db:
        rows = (await db.execute(select(StripeEvent))).scalars().all()
        assert len(rows) == 1 and rows[0].processed_at is not None


async def test_checkout_completed_links_customer_and_invoice_paid_records_payment(api):
    me = await learner_logged_in(api)
    uid = me["user"]["id"]
    await webhook(
        api,
        {
            "id": "evt_cs",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "mode": "payment",
                    "customer": "cus_1",
                    "client_reference_id": uid,
                    "metadata": {"user_id": uid, "plan_key": "exam_sprint"},
                }
            },
        },
    )
    me = (await api.get("/api/auth/me")).json()
    assert me["access"]["has_stripe_customer"] is True
    # TODO(task 0.7): a paid Civics Pass checkout grants the canton entitlement.
    assert me["access"]["access"] == "none"

    invoice = {
        "id": "evt_ip",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_2",
                "customer": "cus_1",
                "amount_paid": 2400,
                "currency": "chf",
                "status_transitions": {"paid_at": 1761600000},
            }
        },
    }
    await webhook(api, invoice)
    await webhook(api, {**invoice, "id": "evt_ip_again"})  # same invoice, new event id
    payments = (await api.get("/api/billing/payments")).json()
    assert len(payments) == 1
    assert payments[0]["amount_cents"] == 2400 and payments[0]["currency"] == "CHF"

    r = await api.post("/api/billing/portal")
    assert r.status_code == 200 and r.json()["url"].startswith("https://billing.stripe.com/")


async def test_portal_requires_customer(api):
    await learner_logged_in(api)
    r = await api.post("/api/billing/portal")
    assert r.status_code == 400 and r.json()["detail"] == "no_stripe_customer"


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
    assert me["access"]["access"] == "full"
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


async def test_webhook_payload_is_stored_without_contact_details(api):
    event = {
        "id": "evt_pii",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_pii",
                "customer": "cus_x",
                "customer_email": "someone@example.ch",
                "customer_name": "Some One",
                "customer_address": {"line1": "Street 1"},
                "lines": {"data": [{"price": {"lookup_key": "k"}, "billing_details": {"x": 1}}]},
            }
        },
    }
    assert (await webhook(api, event)).status_code == 200
    async with SessionLocal() as db:
        row = await db.get(StripeEvent, "evt_pii")
    stored = json.dumps(row.payload)
    assert "someone@example.ch" not in stored and "Some One" not in stored
    assert "Street 1" not in stored and "billing_details" not in stored
    assert row.payload["data"]["object"]["customer"] == "cus_x"
