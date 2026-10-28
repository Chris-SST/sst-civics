"""Thin wrapper around the Stripe SDK. Everything that talks to Stripe goes through
these functions so tests can replace them and so the API version is pinned once."""

from __future__ import annotations

from typing import Any

import stripe

from app.config import get_settings


def _client() -> stripe.StripeClient:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set")
    return stripe.StripeClient(
        settings.stripe_secret_key,
        stripe_version=settings.stripe_api_version,
        max_network_retries=2,
    )


def create_customer(email: str, family_id: str, locale: str) -> dict[str, Any]:
    c = _client().customers.create(
        params={
            "email": email,
            "metadata": {"family_id": family_id},
            "preferred_locales": [locale],
        }
    )
    return c.to_dict_recursive()


def list_prices_by_lookup_keys(keys: list[str]) -> list[dict[str, Any]]:
    result = _client().prices.list(
        params={"lookup_keys": keys, "active": True, "expand": ["data.product"]}
    )
    return [p.to_dict_recursive() for p in result.data]


def create_checkout_session(params: dict[str, Any]) -> dict[str, Any]:
    s = _client().checkout.sessions.create(params=params)
    return s.to_dict_recursive()


def create_portal_session(customer_id: str, return_url: str, locale: str) -> dict[str, Any]:
    s = _client().billing_portal.sessions.create(
        params={"customer": customer_id, "return_url": return_url, "locale": locale}
    )
    return s.to_dict_recursive()


def retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    s = _client().subscriptions.retrieve(subscription_id)
    return s.to_dict_recursive()


def retrieve_checkout_line_items(session_id: str) -> list[dict[str, Any]]:
    result = _client().checkout.sessions.list_line_items(
        session_id, params={"expand": ["data.price"]}
    )
    return [li.to_dict_recursive() for li in result.data]


def construct_event(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify the webhook signature and return the event as a plain dict."""
    settings = get_settings()
    event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    return event.to_dict_recursive()
