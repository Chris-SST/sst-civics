"""Research: fetch the plan's seed sources and keep what was readable.

Only the seed sources of the plan entry are used (decision recorded in the runbook): the
planner picks pages that are fetchable as text, and every source the article cites must be
one of the pages read here, so the fact review can check each claim against the same text.
A page counts as read when its text is at least MIN_TEXT_CHARS long. The text kept per page
is capped at PAGE_CHARS; the model gets an excerpt focused on the brief."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.content import fetch

PAGE_CHARS = 40_000  # stored per page
EXCERPT_CHARS = 9_000  # sent to the model per page


async def fetch_sources(plan: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    seeds = plan.get("sources") or []
    async with fetch.new_client() as client:
        pages = await fetch.gather_limited([fetch.fetch_page(client, s["url"]) for s in seeds], 4)
    out = []
    for seed, page in zip(seeds, pages, strict=True):
        out.append(
            {
                "url": seed["url"],
                "title": seed["title"],
                "fetched_at": now.isoformat(),
                "ok": page.readable,
                "error": None if page.readable else (page.error or "too little readable text"),
                "text": page.text[:PAGE_CHARS] if page.readable else "",
            }
        )
    return out


def readable(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in sources if s.get("ok")]


def read_urls(sources: list[dict[str, Any]]) -> set[str]:
    return {s["url"] for s in readable(sources)}


def focus_of(plan: dict[str, Any]) -> str:
    return " ".join(
        [plan.get("title", ""), plan.get("brief", "")]
        + list(plan.get("must_cover") or [])
        + list(plan.get("outline") or [])
    )


def excerpts(sources: list[dict[str, Any]], focus: str) -> list[dict[str, str]]:
    """The readable pages for the model: number, title, URL and a focused excerpt."""
    return [
        {
            "n": str(i),
            "title": s["title"],
            "url": s["url"],
            "text": fetch.excerpt(s.get("text", ""), focus, EXCERPT_CHARS),
        }
        for i, s in enumerate(readable(sources), 1)
    ]


def public_list(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The sources without their text (emails, CLI)."""
    return [{k: v for k, v in s.items() if k != "text"} for s in sources]
