from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.billing import stripe_client
from app.db import SessionLocal, utcnow
from app.email.backend import memory_outbox
from app.models import Family, StripeEvent
from tests.conftest import admin_logged_in, parent_logged_in

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

    def create_customer(email, family_id, locale):
        calls["customers"].append((email, family_id, locale))
        return {"id": f"cus_{family_id[:8]}"}

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


async def add_student(api, username="kid1"):
    r = await api.post(
        "/api/family/students",
        json={
            "first_name": "Kid",
            "year_of_birth": 2010,
            "curriculum": "ib_dp",
            "courses": ["ib_maths_aa_hl"],
            "locale": "en",
            "username": username,
            "password": "Kid-password-1",
        },
    )
    assert r.status_code == 201, r.text


async def webhook(api, event: dict, signature="valid"):
    return await api.client.post(
        "/api/billing/webhook",
        content=json.dumps(event),
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )


def sub_event(
    event_id,
    sub_id,
    customer,
    family_id,
    status,
    plan="ai_monthly",
    quantity=1,
    etype="customer.subscription.updated",
):
    return {
        "id": event_id,
        "type": etype,
        "data": {
            "object": {
                "id": sub_id,
                "object": "subscription",
                "customer": customer,
                "status": status,
                "cancel_at_period_end": False,
                "trial_end": None,
                "metadata": {"family_id": family_id, "plan_key": plan},
                "items": {
                    "data": [
                        {
                            "quantity": quantity,
                            "current_period_end": 1800000000,
                            "price": {"id": "price_x", "lookup_key": plan},
                        }
                    ]
                },
            }
        },
    }


async def test_plans_listed_with_prices(api):
    r = await api.get("/api/billing/plans")
    assert r.status_code == 200
    plans = {p["key"]: p for p in r.json()}
    assert plans["ai_monthly"]["amount_cents"] == 2400
    assert plans["ai_monthly"]["interval"] == "month"
    assert plans["ai_monthly"]["monthly_message_limit"] == 300
    assert plans["hybrid_monthly"]["daily_message_limit"] == 80
    assert plans["ask_tutor_single"]["kind"] == "addon"


async def test_checkout_requires_student_then_builds_subscription_session(api, fake_stripe):
    me = await parent_logged_in(api)
    r = await api.post("/api/billing/checkout", json={"plan_key": "ai_monthly"})
    assert r.status_code == 400 and r.json()["detail"] == "add_student_first"

    await add_student(api, "kid1")
    await add_student(api, "kid2")
    r = await api.post("/api/billing/checkout", json={"plan_key": "ai_monthly"})
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://checkout.stripe.com/")
    params = fake_stripe["checkout"][0]
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_ai_m", "quantity": 2}]
    assert params["subscription_data"]["trial_period_days"] == 7
    assert params["payment_method_collection"] == "always"
    assert params["client_reference_id"] == me["family"]["id"]
    assert params["customer"].startswith("cus_")
    assert fake_stripe["customers"][0][0] == "parent@example.ch"

    r = await api.post("/api/billing/checkout", json={"plan_key": "nope"})
    assert r.status_code == 404


async def test_webhook_signature_and_idempotency(api):
    await parent_logged_in(api)
    event = {"id": "evt_1", "type": "ping", "data": {"object": {}}}
    assert (await webhook(api, event, signature="bad")).status_code == 400
    r = await webhook(api, event)
    assert r.status_code == 200 and r.json() == {"received": True}
    r = await webhook(api, event)
    assert r.json()["duplicate"] is True
    async with SessionLocal() as db:
        rows = (await db.execute(select(StripeEvent))).scalars().all()
        assert len(rows) == 1 and rows[0].processed_at is not None


async def test_subscription_lifecycle_through_webhooks(api):
    me = await parent_logged_in(api)
    fid = me["family"]["id"]
    await add_student(api)

    # Checkout completed links customer and subscription
    await webhook(
        api,
        {
            "id": "evt_cs",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "mode": "subscription",
                    "customer": "cus_1",
                    "subscription": "sub_1",
                    "client_reference_id": fid,
                    "metadata": {"family_id": fid, "plan_key": "ai_monthly"},
                }
            },
        },
    )
    me = (await api.get("/api/auth/me")).json()
    assert me["family"]["has_stripe_customer"] is True
    assert me["family"]["access"] == "none"  # status unknown until the subscription event

    await webhook(
        api,
        sub_event(
            "evt_s1", "sub_1", "cus_1", fid, "trialing", etype="customer.subscription.created"
        ),
    )
    me = (await api.get("/api/auth/me")).json()["family"]
    assert me["subscription_status"] == "trialing"
    assert me["plan_key"] == "ai_monthly"
    assert me["access"] == "full"
    assert me["current_period_end"].startswith("2027-01-15")

    # Payment failed: warning email, still full access within the grace period
    memory_outbox.clear()
    await webhook(
        api,
        {
            "id": "evt_pf",
            "type": "invoice.payment_failed",
            "data": {"object": {"id": "in_1", "customer": "cus_1"}},
        },
    )
    me = (await api.get("/api/auth/me")).json()["family"]
    assert me["payment_warning"] is True
    assert memory_outbox.messages[-1].to == "parent@example.ch"
    assert "payment" in memory_outbox.messages[-1].subject.lower()

    await webhook(api, sub_event("evt_s2", "sub_1", "cus_1", fid, "past_due"))
    assert (await api.get("/api/auth/me")).json()["family"]["access"] == "full"

    # After seven days past due, read-only
    async with SessionLocal() as db:
        fam = await db.get(Family, uuid.UUID(fid))
        fam.past_due_since = utcnow() - timedelta(days=8)
        await db.commit()
    assert (await api.get("/api/auth/me")).json()["family"]["access"] == "read_only"

    # Invoice paid clears the warning; subscription active again
    await webhook(
        api,
        {
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
        },
    )
    await webhook(api, sub_event("evt_s3", "sub_1", "cus_1", fid, "active"))
    me = (await api.get("/api/auth/me")).json()["family"]
    assert me["payment_warning"] is False and me["access"] == "full"
    payments = (await api.get("/api/billing/payments")).json()
    assert payments[0]["amount_cents"] == 2400 and payments[0]["currency"] == "CHF"

    # Second checkout is refused while subscribed; portal works
    r = await api.post("/api/billing/checkout", json={"plan_key": "hybrid_monthly"})
    assert r.status_code == 409
    r = await api.post("/api/billing/portal")
    assert r.status_code == 200 and r.json()["url"].startswith("https://billing.stripe.com/")

    # Cancelled: read-only
    await webhook(
        api,
        {
            "id": "evt_del",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_1",
                    "customer": "cus_1",
                    "status": "canceled",
                    "ended_at": 1800000000,
                }
            },
        },
    )
    me = (await api.get("/api/auth/me")).json()["family"]
    assert me["subscription_status"] == "canceled" and me["access"] == "read_only"


async def test_trial_will_end_emails_parent(api):
    me = await parent_logged_in(api)
    fid = me["family"]["id"]
    await webhook(
        api,
        sub_event(
            "evt_a", "sub_9", "cus_9", fid, "trialing", etype="customer.subscription.created"
        ),
    )
    memory_outbox.clear()
    await webhook(
        api,
        {
            "id": "evt_t",
            "type": "customer.subscription.trial_will_end",
            "data": {"object": {"id": "sub_9", "customer": "cus_9"}},
        },
    )
    assert memory_outbox.messages and "trial" in memory_outbox.messages[-1].subject.lower()


async def test_addon_checkout_adds_tutor_credit(api, fake_stripe):
    me = await parent_logged_in(api)
    fid = me["family"]["id"]
    r = await api.post(
        "/api/billing/checkout", json={"plan_key": "ask_tutor_single", "quantity": 2}
    )
    assert r.status_code == 200
    params = fake_stripe["checkout"][0]
    assert params["mode"] == "payment" and params["line_items"][0]["quantity"] == 2
    await webhook(
        api,
        {
            "id": "evt_addon",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_2",
                    "mode": "payment",
                    "customer": params["customer"],
                    "client_reference_id": fid,
                    "metadata": {"family_id": fid, "plan_key": "ask_tutor_single", "quantity": "2"},
                }
            },
        },
    )
    assert (await api.get("/api/auth/me")).json()["family"]["tutor_credits"] == 2


async def test_portal_requires_customer(api):
    await parent_logged_in(api)
    r = await api.post("/api/billing/portal")
    assert r.status_code == 400 and r.json()["detail"] == "no_stripe_customer"


async def test_admin_sees_family_and_grants_free_access(api, api2):
    me = await parent_logged_in(api2, "fam@example.ch")
    fid = me["family"]["id"]
    await admin_logged_in(api)
    r = await api.get("/api/admin/families?q=fam@")
    assert r.status_code == 200 and r.json()[0]["payer_email"] == "fam@example.ch"
    r = await api.get(f"/api/admin/families/{fid}")
    assert r.status_code == 200 and r.json()["access"] == "none"
    until = (utcnow() + timedelta(days=30)).isoformat()
    r = await api.post(
        f"/api/admin/families/{fid}/free-access",
        json={"until": until, "reason": "SST lesson family"},
    )
    assert r.status_code == 200 and r.json()["access"] == "full"
    assert (await api2.get("/api/auth/me")).json()["family"]["access"] == "full"
    audit = (await api.get("/api/admin/audit")).json()
    assert {a["action"] for a in audit} >= {"family.view", "family.free_access"}
    overview = (await api.get("/api/admin/overview")).json()
    assert overview["families"] == 1
