"""Thin wrapper around the Stripe SDK. Everything that talks to Stripe goes through
these functions so tests can replace them and so the API version is pinned once."""

from __future__ import annotations

from typing import Any

import stripe

from app.config import get_settings


def _plain(value: Any) -> Any:
    """Convert Stripe SDK objects (any version) into plain dicts and lists, recursively."""
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _client() -> stripe.StripeClient:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set")
    return stripe.StripeClient(
        settings.stripe_secret_key,
        stripe_version=settings.stripe_api_version,
        max_network_retries=2,
    )


def create_customer(email: str, user_id: str, locale: str) -> dict[str, Any]:
    c = _client().customers.create(
        params={
            "email": email,
            "metadata": {"user_id": user_id},
            "preferred_locales": [locale],
        }
    )
    return _plain(c)


def list_prices_by_lookup_keys(keys: list[str]) -> list[dict[str, Any]]:
    result = _client().prices.list(
        params={"lookup_keys": keys, "active": True, "expand": ["data.product"]}
    )
    return [_plain(p) for p in result.data]


def create_checkout_session(params: dict[str, Any]) -> dict[str, Any]:
    s = _client().checkout.sessions.create(params=params)
    return _plain(s)


def create_portal_session(customer_id: str, return_url: str, locale: str) -> dict[str, Any]:
    s = _client().billing_portal.sessions.create(
        params={"customer": customer_id, "return_url": return_url, "locale": locale}
    )
    return _plain(s)


def retrieve_subscription(subscription_id: str) -> dict[str, Any]:
    s = _client().subscriptions.retrieve(subscription_id)
    return _plain(s)


def retrieve_checkout_line_items(session_id: str) -> list[dict[str, Any]]:
    result = _client().checkout.sessions.list_line_items(
        session_id, params={"expand": ["data.price"]}
    )
    return [_plain(li) for li in result.data]


def construct_event(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify the webhook signature and return the event as a plain dict."""
    settings = get_settings()
    event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    return _plain(event)
