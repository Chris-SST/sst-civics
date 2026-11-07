"""The "Articles" section of the owner's daily digest (D-072, D-073): what was published
yesterday, what is scheduled next, what waits on Chris, and what needs action. Titles, keys,
dates and states only."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ART_HELD,
    ART_NEEDS_ATTENTION,
    ART_PROPOSED,
    ART_PUBLISH_FAILED,
    ART_PUBLISHED,
    Article,
)
from app.study.clock import ZURICH


def _title(a: Article) -> str:
    return (a.english or {}).get("title") or (a.plan or {}).get("title") or a.key


def _when(moment: datetime) -> str:
    return moment.astimezone(ZURICH).strftime("%a %d %b %H:%M")


async def article_figures(
    db: AsyncSession, start: datetime, end: datetime, now: datetime
) -> dict[str, Any]:
    from app.articles.workflow import planned_publication

    rows = (await db.execute(select(Article).order_by(Article.publish_at))).scalars().all()
    if not rows:
        return {"status": "none"}
    published = [
        {"key": a.key, "title": _title(a), "languages": len(a.live_urls or {})}
        for a in rows
        if a.last_published_at is not None and start <= a.last_published_at < end
    ]
    upcoming = [a for a in rows if a.status not in (ART_PUBLISHED, ART_HELD)]
    upcoming.sort(key=lambda a: planned_publication(a, now))
    nxt = upcoming[0] if upcoming else None
    waiting = [
        {"key": a.key, "title": _title(a), "publishes": _when(planned_publication(a, now))}
        for a in rows
        if a.status == ART_PROPOSED
    ]
    held = [{"key": a.key, "title": _title(a)} for a in rows if a.status == ART_HELD]
    action = [
        {"key": a.key, "title": _title(a), "status": a.status, "reason": (a.last_error or "")[:300]}
        for a in rows
        if a.status in (ART_NEEDS_ATTENTION, ART_PUBLISH_FAILED)
    ]
    return {
        "status": "ok",
        "published_yesterday": published,
        "next_scheduled": (
            {
                "key": nxt.key,
                "title": _title(nxt),
                "status": nxt.status,
                "publishes": _when(planned_publication(nxt, now)),
            }
            if nxt
            else None
        ),
        "waiting_on_owner": waiting,
        "held": held,
        "needs_action": action,
    }


def text_lines(section: dict[str, Any]) -> list[str]:
    if section.get("status") != "ok":
        return []
    lines = ["", "Articles:"]
    for p in section["published_yesterday"]:
        lines.append(f"- Published yesterday: {p['title']} ({p['languages']} languages)")
    n = section["next_scheduled"]
    if n:
        lines.append(f"- Next: {n['title']}, {n['publishes']} (Zurich), now {n['status']}")
    for w in section["waiting_on_owner"]:
        lines.append(
            f"- Proposed to you, publishes {w['publishes']} if you do nothing: {w['title']}"
        )
    for h in section["held"]:
        lines.append(f"- On hold: {h['title']}")
    for x in section["needs_action"]:
        lines.append(f"- ACTION ({x['status']}): {x['title']}: {x['reason']}")
    if len(lines) == 2:
        lines.append("- Nothing scheduled.")
    return lines


def html_block(section: dict[str, Any]) -> str:
    import html

    lines = text_lines(section)[2:]
    if not lines:
        return ""
    e = html.escape
    items = "".join(
        f"<li>{'<strong>' if line.startswith('- ACTION') else ''}{e(line[2:])}"
        f"{'</strong>' if line.startswith('- ACTION') else ''}</li>"
        for line in lines
    )
    return f"<p><strong>Articles</strong></p><ul>{items}</ul>"


def actions(section: dict[str, Any]) -> list[str]:
    if section.get("status") != "ok":
        return []
    return [
        f"Article {x['title']} is {x['status'].replace('_', ' ')}: open the review link "
        "from its email."
        for x in section["needs_action"]
    ]
