from __future__ import annotations

import stripe

from app.billing.stripe_client import _plain


def test_plain_converts_nested_stripe_objects():
    obj = stripe.StripeObject.construct_from(
        {
            "id": "price_1",
            "unit_amount": 2400,
            "lookup_key": "ai_monthly",
            "recurring": {"interval": "month"},
            "items": {"data": [{"quantity": 2, "price": {"id": "price_1"}}]},
        },
        "sk_test_dummy",
    )
    d = _plain(obj)
    assert type(d) is dict
    assert d["recurring"]["interval"] == "month"
    assert type(d["recurring"]) is dict
    assert d["items"]["data"][0]["price"]["id"] == "price_1"
    assert type(d["items"]["data"][0]) is dict
    assert _plain([obj])[0]["unit_amount"] == 2400
