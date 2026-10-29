"""Provider list prices used for cost logging. USD per million tokens.

Checked against Anthropic's pricing page on 28 October 2026 (PLAN.md). Update here when
prices change; the figure only feeds the cost log and alerts, never billing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write: float


PRICES_USD_PER_MTOK: dict[str, Price] = {
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_read=0.20, cache_write=2.50),
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_read=0.20, cache_write=5.00),
}

# Used for a model that is not in the table, so a new model never logs zero cost.
FALLBACK_PRICE = PRICES_USD_PER_MTOK["claude-sonnet-5-5"]


def price_for(model: str) -> Price:
    return PRICES_USD_PER_MTOK.get(model, FALLBACK_PRICE)


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    p = price_for(model)
    total = (
        input_tokens * p.input
        + output_tokens * p.output
        + cache_read_tokens * p.cache_read
        + cache_write_tokens * p.cache_write
    )
    return total / 1_000_000
