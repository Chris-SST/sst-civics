"""Create or update the Viapunt Pass products and prices in the Stripe account, with the
lookup keys the app expects (D-015). Safe to re-run. Test mode by default; a live key
(sk_live_ or rk_live_) needs --live, and then only the passes on sale (CANTONS_FOR_SALE) and
the extension are created.

The app never reads an amount from code: it looks prices up in Stripe by lookup key. The
amounts below are only what this script writes into the test account; change them with
`--amount KEY=RAPPEN` or in the Dashboard. Prices are immutable in Stripe, so a different
amount creates a new price and moves the lookup key to it.

Usage:
  STRIPE_SECRET_KEY=sk_test_... python -m scripts.stripe_bootstrap [--amount civics_pass_zh=2900]
  python -m scripts.stripe_bootstrap --live      (production, after go-live approval)
"""

from __future__ import annotations

import argparse

import stripe

from app.billing.products import PRODUCTS
from app.config import get_settings

# Test-mode amounts in rappen, VAT included (D-015: pass CHF 29, extension CHF 9).
DEFAULT_AMOUNTS = {
    "civics_pass_zh": 2900,
    "civics_pass_ch": 2900,
    "civics_pass_ag": 2900,
    "civics_extension": 900,
}
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
    parser.add_argument("--live", action="store_true", help="allow a live key (go-live approved)")
    args = parser.parse_args()
    amounts = _amounts(args.amount)

    settings = get_settings()
    if not settings.stripe_secret_key:
        raise SystemExit("Set STRIPE_SECRET_KEY first")
    live = settings.stripe_secret_key.startswith(("sk_live_", "rk_live_"))
    if live and not args.live:
        raise SystemExit(
            "Live key: run with --live to write products and prices to the live account"
        )
    if not live and not settings.stripe_secret_key.startswith(("sk_test_", "rk_test_")):
        raise SystemExit("STRIPE_SECRET_KEY is neither a test nor a live key")
    wanted = {
        k: p
        for k, p in PRODUCTS.items()
        if not live or p.canton is None or p.canton in settings.cantons_on_sale
    }
    client = stripe.StripeClient(
        settings.stripe_secret_key, stripe_version=settings.stripe_api_version
    )

    prices = {
        p.lookup_key: p
        for p in client.prices.list(
            params={"lookup_keys": list(wanted), "active": True, "limit": 100}
        ).data
        if p.lookup_key
    }
    for key, product in wanted.items():
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
