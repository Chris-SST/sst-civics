"""The "Politics" section of the owner's daily digest (D-074): pages published yesterday,
weeks skipped, the next vote explainers, the current-affairs questions served, and every
page that needs action. Titles, keys, dates and states only."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles.constants import POLITICS_KINDS
from app.models import (
    ART_HELD,
    ART_NEEDS_ATTENTION,
    ART_PLANNED,
    ART_PUBLISH_FAILED,
    CA_OK,
    Article,
    CurrentAffairsQuestion,
)
from app.study.clock import ZURICH


def _title(a: Article) -> str:
    return (a.english or {}).get("title") or (a.plan or {}).get("title") or a.key


async def politics_figures(
    db: AsyncSession, start: datetime, end: datetime, now: datetime
) -> dict[str, Any]:
    rows = (
        (await db.execute(select(Article).where(Article.kind.in_(POLITICS_KINDS)))).scalars().all()
    )
    if not rows:
        return {"status": "none"}
    published = [
        {
            "key": a.key,
            "kind": a.kind,
            "title": _title(a),
            "languages": len(a.live_urls or {}),
            "url": (a.live_urls or {}).get("en", ""),
        }
        for a in rows
        if a.last_published_at is not None and start <= a.last_published_at < end
    ]
    skipped = [
        {"key": a.key, "reason": (a.last_error or "")[:200]}
        for a in rows
        if a.status == ART_HELD and a.kind == "roundup" and start <= a.updated_at < end
    ]
    upcoming = sorted(
        (a for a in rows if a.kind == "vote" and a.status == ART_PLANNED and a.publish_at > now),
        key=lambda a: a.publish_at,
    )[:3]
    action = [
        {"key": a.key, "title": _title(a), "status": a.status, "reason": (a.last_error or "")[:300]}
        for a in rows
        if a.status in (ART_NEEDS_ATTENTION, ART_PUBLISH_FAILED)
    ]
    served = await db.scalar(
        select(func.count())
        .select_from(CurrentAffairsQuestion)
        .where(CurrentAffairsQuestion.status == CA_OK, CurrentAffairsQuestion.expires_at > now)
    )
    return {
        "status": "ok",
        "published_yesterday": published,
        "skipped_yesterday": skipped,
        "next_votes": [
            {
                "key": a.key,
                "title": _title(a),
                "publishes": a.publish_at.astimezone(ZURICH).strftime("%a %d %b"),
            }
            for a in upcoming
        ],
        "current_affairs_questions": int(served or 0),
        "needs_action": action,
    }


def text_lines(section: dict[str, Any]) -> list[str]:
    if section.get("status") != "ok":
        return []
    lines = ["", "Politics:"]
    for p in section["published_yesterday"]:
        lines.append(
            f"- Published yesterday ({p['kind']}): {p['title']} ({p['languages']} languages) "
            f"{p['url']}".rstrip()
        )
    for s in section["skipped_yesterday"]:
        lines.append(f"- Round-up skipped: {s['key']}: {s['reason']}")
    for v in section["next_votes"]:
        lines.append(f"- Next vote explainer: {v['title']}, {v['publishes']}")
    lines.append(f"- Current-affairs questions in the app: {section['current_affairs_questions']}")
    for x in section["needs_action"]:
        lines.append(f"- ACTION ({x['status']}): {x['title']}: {x['reason']}")
    return lines


def html_block(section: dict[str, Any]) -> str:
    lines = text_lines(section)[2:]
    if not lines:
        return ""
    e = html.escape
    items = "".join(
        f"<li>{'<strong>' if line.startswith('- ACTION') else ''}{e(line[2:])}"
        f"{'</strong>' if line.startswith('- ACTION') else ''}</li>"
        for line in lines
    )
    return f"<p><strong>Politics</strong></p><ul>{items}</ul>"


def actions(section: dict[str, Any]) -> list[str]:
    if section.get("status") != "ok":
        return []
    return [
        f"Politics page {x['title']} is {x['status'].replace('_', ' ')}: see its email "
        f"or run python -m scripts.politics list."
        for x in section["needs_action"]
    ]
