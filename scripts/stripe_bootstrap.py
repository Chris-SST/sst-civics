"""Create or update the Civics Pass products and prices in the Stripe account, test mode
only, with the lookup keys the app expects (D-015). Safe to re-run.

The app never reads an amount from code: it looks prices up in Stripe by lookup key. The
amounts below are only what this script writes into the test account; change them with
`--amount KEY=RAPPEN` or in the Dashboard. Prices are immutable in Stripe, so a different
amount creates a new price and moves the lookup key to it.

Usage:
  STRIPE_SECRET_KEY=sk_test_... python -m scripts.stripe_bootstrap [--amount civics_pass_zh=2900]
"""

from __future__ import annotations

import argparse

import stripe

from app.billing.products import PRODUCTS
from app.config import get_settings

# Test-mode amounts in rappen, VAT included (D-015: pass CHF 29, extension CHF 9).
DEFAULT_AMOUNTS = {"civics_pass_zh": 2900, "civics_pass_ag": 2900, "civics_extension": 900}
CURRENCY = "chf"


def _amounts(overrides: list[str]) -> dict[str, int]:
    amounts = dict(DEFAULT_AMOUNTS)
    for item in overrides:
        key, _, value = item.partition("=")
        if key not in PRODUCTS or not value.isdigit():
            raise SystemExit(f"Bad --amount {item!r}: use KEY=RAPPEN with a known key")
        amounts[key] = int(value)
    return amounts


def _product_id(client: stripe.StripeClient, key: str, name: str, existing_price) -> str:
    """The product for `key`: the one behind its current price, else one tagged with the
    key in its metadata, else a new one. Its name is brought up to date."""
    product_id = None
    if existing_price is not None:
        product = existing_price.product
        product_id = product if isinstance(product, str) else product.id
    if product_id is None:
        found = client.products.search(params={"query": f"metadata['civics_key']:'{key}'"}).data
        product_id = found[0].id if found else None
    if product_id is None:
        created = client.products.create(params={"name": name, "metadata": {"civics_key": key}})
        print(f"{key}: product created {created.id}")
        return created.id
    client.products.update(product_id, params={"name": name, "metadata": {"civics_key": key}})
    return product_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--amount", action="append", default=[], metavar="KEY=RAPPEN")
    args = parser.parse_args()
    amounts = _amounts(args.amount)

    settings = get_settings()
    if not settings.stripe_secret_key:
        raise SystemExit("Set STRIPE_SECRET_KEY first")
    if not settings.stripe_secret_key.startswith("sk_test_"):
        raise SystemExit("Refusing to run against a live key before go-live approval")
    client = stripe.StripeClient(
        settings.stripe_secret_key, stripe_version=settings.stripe_api_version
    )

    prices = {
        p.lookup_key: p
        for p in client.prices.list(
            params={"lookup_keys": list(PRODUCTS), "active": True, "limit": 100}
        ).data
        if p.lookup_key
    }
    for key, product in PRODUCTS.items():
        price = prices.get(key)
        product_id = _product_id(client, key, product.name, price)
        metadata = {"access_months": str(product.months), "kind": product.kind}
        if product.canton:
            metadata["canton"] = product.canton
        same = (
            price is not None
            and price.unit_amount == amounts[key]
            and price.currency == CURRENCY
            and price.tax_behavior == "inclusive"
            and price.recurring is None
        )
        if same:
            client.prices.update(price.id, params={"metadata": metadata})
            print(f"{key}: up to date ({price.id})")
            continue
        created = client.prices.create(
            params={
                "product": product_id,
                "currency": CURRENCY,
                "unit_amount": amounts[key],
                "tax_behavior": "inclusive",
                "lookup_key": key,
                "transfer_lookup_key": True,
                "metadata": metadata,
            }
        )
        if price is not None:
            client.prices.update(price.id, params={"active": False})
        print(f"{key}: price created {created.id} ({amounts[key] / 100:.2f} {CURRENCY.upper()})")
    print(
        "Done. Enable cards and TWINT under Settings > Payment methods in the Stripe Dashboard,"
        " and subscribe the webhook to checkout.session.completed,"
        " checkout.session.async_payment_succeeded, checkout.session.async_payment_failed"
        " and charge.refunded."
    )


if __name__ == "__main__":
    main()
