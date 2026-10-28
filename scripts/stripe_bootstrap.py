"""Create the products and prices in the Stripe account (test mode) with the lookup keys
the app expects. Safe to re-run: existing lookup keys are left alone.

Usage: STRIPE_SECRET_KEY=sk_test_... python -m scripts.stripe_bootstrap
"""

from __future__ import annotations

import stripe

from app.config import get_settings

PRICES = [
    # key, product name, amount in rappen, recurring interval or None
    ("ai_monthly", "SST Virtual Tutor: AI-only", 2400, "month"),
    ("ai_annual", "SST Virtual Tutor: AI-only", 19900, "year"),
    ("hybrid_monthly", "SST Virtual Tutor: Hybrid", 14900, "month"),
    ("ask_tutor_single", "SST Virtual Tutor: Ask a tutor", 1900, None),
    ("exam_sprint", "SST Virtual Tutor: IB exam sprint", 34900, None),
]


def main() -> None:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise SystemExit("Set STRIPE_SECRET_KEY first")
    if not settings.stripe_secret_key.startswith("sk_test_"):
        raise SystemExit("Refusing to run against a live key before go-live approval")
    client = stripe.StripeClient(
        settings.stripe_secret_key, stripe_version=settings.stripe_api_version
    )

    existing = {
        p.lookup_key
        for p in client.prices.list(params={"lookup_keys": [k for k, *_ in PRICES]}).data
        if p.lookup_key
    }
    products: dict[str, str] = {}
    for key, name, amount, interval in PRICES:
        if key in existing:
            print(f"{key}: exists")
            continue
        if name not in products:
            found = [p for p in client.products.search(params={"query": f"name:'{name}'"}).data]
            products[name] = (
                found[0].id if found else client.products.create(params={"name": name}).id
            )
        params = {
            "product": products[name],
            "currency": "chf",
            "unit_amount": amount,
            "lookup_key": key,
            "tax_behavior": "inclusive",
        }
        if interval:
            params["recurring"] = {"interval": interval}
        price = client.prices.create(params=params)
        print(f"{key}: created {price.id}")
    print("Done. Enable TWINT and cards under Settings > Payment methods in the Stripe Dashboard.")


if __name__ == "__main__":
    main()
