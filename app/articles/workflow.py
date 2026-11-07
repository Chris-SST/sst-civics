"""States, timing and the actions of the article pipeline (contract section 4).

    planned -> researching -> drafting -> reviewing -> translating -> ready -> proposed
      -> (changes_requested -> ... -> proposed) -> approved -> publishing -> published
    plus held, needs_attention and publish_failed.

Timing: production starts ARTICLES_LEAD_DAYS before `publish_at`. The proposal email goes
out at `publish_at - ARTICLES_PROPOSAL_HOURS`, or as soon as the article is ready if that is
later. Publication is due at `max(publish_at, proposal_sent_at + ARTICLES_PROPOSAL_HOURS)`
unless the article is held or changes were requested; every new proposal restarts the clock.

State changes that two processes could race on (claiming a production, starting a
publication, finishing it) are conditional UPDATEs, so a second worker or a late tick never
runs the same step twice. Files are written only by the worker, which has ARTICLES_DIR."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import emails, files
from app.articles.constants import INDEXNOW_ENDPOINT, INDEXNOW_KEY, KINDS, POLITICS_KINDS
from app.articles.plan import import_plan
from app.articles.produce import pending_feedback
from app.articles.validate import (
    validate_article,
    validate_politics_frontmatter,
    validate_translation,
)
from app.config import get_settings
from app.db import utcnow
from app.models import (
    ART_APPROVED,
    ART_CHANGES_REQUESTED,
    ART_DRAFTING,
    ART_HELD,
    ART_NEEDS_ATTENTION,
    ART_PLANNED,
    ART_PRODUCING,
    ART_PROPOSED,
    ART_PUBLISH_FAILED,
    ART_PUBLISHED,
    ART_PUBLISHING,
    ART_READY,
    ART_RESEARCHING,
    Article,
)
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

STALE_PRODUCTION = timedelta(hours=2)  # a claimed run older than this has died
MAX_ATTEMPTS = 3
BUILD_POLL_SECONDS = 15.0
LIVE_CHECK_TRIES = 3
LIVE_CHECK_PAUSE = 10.0

# Where Chris's three actions are allowed.
CAN_PUBLISH_NOW = (
    ART_READY,
    ART_PROPOSED,
    ART_HELD,
    ART_APPROVED,
    ART_PUBLISH_FAILED,
    ART_NEEDS_ATTENTION,
)
CAN_HOLD = (ART_READY, ART_PROPOSED, ART_APPROVED, ART_PUBLISH_FAILED, ART_NEEDS_ATTENTION)
CAN_SUGGEST = (
    ART_READY,
    ART_PROPOSED,
    ART_HELD,
    ART_APPROVED,
    ART_PUBLISH_FAILED,
    ART_NEEDS_ATTENTION,
    ART_PUBLISHED,
    ART_CHANGES_REQUESTED,
    *ART_PRODUCING,
)


# --- timing ----------------------------------------------------------------------------------


def hours(n: int) -> timedelta:
    return timedelta(hours=n)


def production_due_at(a: Article) -> datetime:
    return a.publish_at - timedelta(days=get_settings().articles_lead_days)


def proposal_due_at(a: Article) -> datetime:
    return a.publish_at - hours(get_settings().articles_proposal_hours)


def publish_due_at(a: Article) -> datetime | None:
    if a.proposal_sent_at is None:
        return None
    return max(a.publish_at, a.proposal_sent_at + hours(get_settings().articles_proposal_hours))


def planned_publication(a: Article, now: datetime) -> datetime:
    """When the article will go out if Chris says nothing (for the email and page)."""
    due = publish_due_at(a)
    if due is not None:
        return due
    sent = max(now, proposal_due_at(a))
    return max(a.publish_at, sent + hours(get_settings().articles_proposal_hours))


def zurich_time(moment: datetime) -> str:
    return moment.astimezone(ZURICH).strftime("%A %d %B %Y, %H:%M")


# --- small transitions -----------------------------------------------------------------------


async def claim(
    db: AsyncSession, a: Article, from_states: tuple[str, ...], to: str, **values: Any
) -> bool:
    """Conditional state change: only one caller wins."""
    result = await db.execute(
        update(Article)
        .where(Article.id == a.id, Article.status.in_(from_states))
        .values(status=to, updated_at=utcnow(), **values)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    if result.rowcount != 1:
        return False
    await db.refresh(a)
    return True


async def mark_needs_attention(
    db: AsyncSession, a: Article, reason: str, findings: list[dict[str, Any]], now: datetime
) -> None:
    a.status = ART_NEEDS_ATTENTION
    a.last_error = reason[:4000]
    a.production_started_at = None
    a.attempts = (a.attempts or 0) + 1
    a.reviews = [
        *(a.reviews or []),
        {"at": now.isoformat(), "kind": "stopped", "reason": reason, "findings": findings},
    ]
    await db.commit()
    log.warning("Article %s needs attention: %s", a.key, reason)
    await emails.send_needs_attention(db, a, reason, findings, now)


async def recover_stale(db: AsyncSession, a: Article, now: datetime) -> bool:
    """A production claimed long ago has died (worker restart, timeout): try again, or stop
    after MAX_ATTEMPTS."""
    if a.status not in ART_PRODUCING or a.production_started_at is None:
        return False
    if now - a.production_started_at < STALE_PRODUCTION:
        return False
    a.attempts = (a.attempts or 0) + 1
    a.production_started_at = None
    if a.attempts >= MAX_ATTEMPTS:
        await mark_needs_attention(db, a, "production did not finish (worker stopped)", [], now)
        return True
    a.status = ART_CHANGES_REQUESTED if a.english else ART_PLANNED
    await db.commit()
    return True


# --- production ------------------------------------------------------------------------------


PRODUCIBLE = (ART_PLANNED, ART_CHANGES_REQUESTED)


async def start_production(db: AsyncSession, a: Article, now: datetime, *, force: bool = False):
    """Claim the article for a production run. With `force`, from any state but publishing."""
    from_states = PRODUCIBLE
    if force:
        from_states = tuple(
            s
            for s in (
                ART_PLANNED,
                ART_CHANGES_REQUESTED,
                ART_READY,
                ART_PROPOSED,
                ART_HELD,
                ART_APPROVED,
                ART_NEEDS_ATTENTION,
                ART_PUBLISH_FAILED,
                ART_PUBLISHED,
            )
        )
    first = ART_DRAFTING if (a.english and pending_feedback(a)) else ART_RESEARCHING
    return await claim(db, a, from_states, first, production_started_at=now)


async def run_production(
    db: AsyncSession, a: Article, now: datetime | None = None, *, force: bool = False
) -> str | None:
    """Claim and produce. Returns the new status, or None if another run holds it."""
    from app.articles.produce import produce

    now = now or utcnow()
    if not await start_production(db, a, now, force=force):
        return None
    if a.kind in POLITICS_KINDS:
        from app.politics.produce import produce as produce_politics

        return await produce_politics(db, a, now)
    return await produce(db, a, now)


# --- Chris's actions -------------------------------------------------------------------------


class ActionRefused(Exception):
    """The action does not apply in the article's current state."""


async def suggest_changes(db: AsyncSession, a: Article, text: str, now: datetime) -> None:
    from app.articles.produce import new_feedback

    text = text.strip()
    if not text:
        raise ActionRefused("empty")
    if a.status not in CAN_SUGGEST:
        raise ActionRefused(a.status)
    a.feedback = [*(a.feedback or []), new_feedback(text[:8000], a.revision, now)]
    if a.status not in ART_PRODUCING:  # a running production picks it up when it ends
        a.status = ART_CHANGES_REQUESTED
        a.approved_at = None
    await db.commit()


async def hold(db: AsyncSession, a: Article) -> None:
    if a.status == ART_HELD:
        return
    if not await claim(db, a, CAN_HOLD, ART_HELD, approved_at=None):
        raise ActionRefused(a.status)


async def publish_now(db: AsyncSession, a: Article, now: datetime) -> None:
    if a.english is None:
        raise ActionRefused("no text yet")
    if not await claim(db, a, CAN_PUBLISH_NOW, ART_APPROVED, approved_at=now):
        raise ActionRefused(a.status)


# --- proposal --------------------------------------------------------------------------------


async def propose(db: AsyncSession, a: Article, now: datetime, *, send: bool = True):
    """Send the proposal email and start the clock. Returns the emails (sent unless not
    `send`). A failed send leaves the article `ready`, so the next tick tries again."""
    msgs = await emails.proposal_emails(db, a, now)
    if not msgs:
        log.warning("Article %s: no recipient for the proposal", a.key)
        return []
    if not send:
        return msgs
    if not emails.send_all(msgs):
        return []
    a.status = ART_PROPOSED
    a.proposal_sent_at = now
    a.proposal_revision = a.revision
    await db.commit()
    return msgs


# --- publication -----------------------------------------------------------------------------


def _checked_date(content: dict[str, Any], fallback: date) -> date:
    try:
        return date.fromisoformat(content.get("checked") or "")
    except ValueError:
        return fallback


def has_result(a: Article) -> bool:
    """A vote explainer written after the vote (its text has the Result section)."""
    return a.kind == "vote" and bool((a.english or {}).get("result"))


def politics_extra(a: Article) -> dict[str, Any] | None:
    """The extra frontmatter fields of a politics page (docs/politics-contract.md)."""
    if a.kind not in POLITICS_KINDS:
        return None
    plan = a.plan or {}
    if a.kind == "roundup":
        return {
            "period_start": date.fromisoformat(plan["period_start"]),
            "period_end": date.fromisoformat(plan["period_end"]),
        }
    if a.kind == "vote":
        return {
            "vote_date": date.fromisoformat(plan["vote_date"]),
            "vote_level": plan["vote_level"],
            "result": (a.english or {}).get("result") or None,
        }
    return {}


def build_files(a: Article, now: datetime) -> tuple[dict[str, str], dict[str, str]]:
    """{relative path: file text} and {lang: page path} for every language that passed."""
    today = now.astimezone(ZURICH).date()
    published = (a.published_at or now).astimezone(ZURICH).date()
    checked = _checked_date(a.english or {}, today)
    versions = {"en": a.english}
    for lang, t in (a.translations or {}).items():
        if t.get("status") == "ok" and t.get("content"):
            versions[lang] = t["content"]
    out: dict[str, str] = {}
    pages: dict[str, str] = {}
    for lang, content in versions.items():
        fm = files.frontmatter(
            content,
            key=a.key,
            kind=a.kind,
            category=a.category,
            canton=a.canton,
            lang=lang,
            published=published,
            updated=today,
            checked=checked,
            extra=politics_extra(a),
        )
        out[files.relative_path(lang, content["slug"])] = files.render_file(fm, content["body"])
        pages[lang] = files.page_path(a.kind, lang, content["slug"], a.canton)
    return out, pages


async def check_publishable(db: AsyncSession, a: Article) -> list[str]:
    keys = {k for (k,) in (await db.execute(select(Article.key))).all()}
    result = has_result(a)
    problems = validate_article(
        a.english or {},
        kind=a.kind,
        lang="en",
        plan_keys=keys,
        read_urls={s["url"] for s in (a.english or {}).get("sources", [])},
        has_result=result,
    )
    for lang, t in (a.translations or {}).items():
        if t.get("status") == "ok" and t.get("content"):
            for p in validate_translation(
                t["content"], a.english, kind=a.kind, lang=lang, plan_keys=keys, has_result=result
            ):
                problems.append(f"{lang}: {p}")
    if a.kind in POLITICS_KINDS and a.english:
        texts, _ = build_files(a, utcnow())
        for rel, text in texts.items():
            fm, _ = files.parse_file(text)
            problems += [f"{rel}: {p}" for p in validate_politics_frontmatter(fm)]
    return problems


async def start_publication(db: AsyncSession, a: Article, now: datetime) -> bool:
    """Write all language files, then the build request. Returns False if not claimed."""
    if not await claim(db, a, (ART_APPROVED,), ART_PUBLISHING):
        return False
    problems = await check_publishable(db, a)
    if problems:
        await fail_publication(
            db, a, "the files would break the contract: " + "; ".join(problems), now
        )
        return True
    root = files.articles_dir()
    texts, _ = build_files(a, now)
    try:
        a.live_files = files.write_article_files(root, texts, a.live_files or {})
        files.request_build(root, f"publish {a.key}", now)
    except OSError as exc:
        await fail_publication(db, a, f"could not write to ARTICLES_DIR: {exc}", now)
        return True
    a.build_requested_at = now
    await db.commit()
    return True


async def fail_publication(db: AsyncSession, a: Article, reason: str, now: datetime) -> None:
    if not await claim(
        db, a, (ART_PUBLISHING, ART_APPROVED), ART_PUBLISH_FAILED, last_error=reason[:4000]
    ):
        return  # another process finished or failed it first
    log.warning("Article %s: publication failed: %s", a.key, reason.split("\n")[0])
    await emails.send_publish_failed(db, a, reason, now)


async def live_check(urls: dict[str, str]) -> dict[str, str]:
    """{lang: problem} for pages that do not answer 200 (a few tries: the swap is quick but
    not instant)."""
    problems: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        for lang, url in urls.items():
            last = ""
            for attempt in range(LIVE_CHECK_TRIES):
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        last = ""
                        break
                    last = f"HTTP {r.status_code}"
                except httpx.HTTPError as exc:
                    last = exc.__class__.__name__
                if attempt + 1 < LIVE_CHECK_TRIES:
                    await asyncio.sleep(LIVE_CHECK_PAUSE)
            if last:
                problems[lang] = f"{url}: {last}"
    return problems


async def indexnow(urls: list[str]) -> bool:
    settings = get_settings()
    if not urls or not settings.articles_indexnow or settings.app_env != "production":
        return False
    base = settings.guide_base_url.rstrip("/")
    host = httpx.URL(base).host
    body = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{base}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(INDEXNOW_ENDPOINT, json=body)
        return r.status_code in (200, 202)
    except httpx.HTTPError:
        return False


async def check_build(db: AsyncSession, a: Article, now: datetime) -> str:
    """Look at the builder's status once: 'waiting', or the final state after handling it."""
    if a.status != ART_PUBLISHING or a.build_requested_at is None:
        return a.status
    result = files.read_build_status(
        Path(get_settings().sitebuild_status_file), a.build_requested_at
    )
    if not result.done:
        limit = timedelta(minutes=get_settings().articles_build_timeout_minutes)
        if now - a.build_requested_at > limit:
            await fail_publication(
                db, a, f"the site builder did not report a finished build within {limit}", now
            )
            return a.status
        return "waiting"
    if not result.ok:
        await fail_publication(db, a, "the site build failed:\n" + (result.error or ""), now)
        return a.status
    return await finish_publication(db, a, now)


async def finish_publication(db: AsyncSession, a: Article, now: datetime) -> str:
    base = get_settings().guide_base_url.rstrip("/")
    _, pages = build_files(a, a.build_requested_at or now)
    urls = {lang: base + path for lang, path in pages.items()}
    problems = await live_check(urls)
    if problems:
        await fail_publication(db, a, "the live check failed: " + "; ".join(problems.values()), now)
        return a.status
    update_of_live = a.published_at is not None
    values: dict[str, Any] = {
        "live_urls": urls,
        "last_published_at": now,
        "published_revision": a.revision,
        "last_error": None,
    }
    if not update_of_live:
        values["published_at"] = a.build_requested_at or now
    if not await claim(db, a, (ART_PUBLISHING,), ART_PUBLISHED, **values):
        return a.status
    pinged = await indexnow(list(urls.values()))
    log.info("Article %s published (%d languages, IndexNow %s)", a.key, len(urls), pinged)
    if a.kind not in POLITICS_KINDS:  # politics pages appear in the digest instead (D-074)
        await emails.send_published(db, a, now, update=update_of_live, indexnow=pinged)
    return a.status


async def wait_for_build(db: AsyncSession, a: Article, *, poll: float = BUILD_POLL_SECONDS) -> str:
    while True:
        state = await check_build(db, a, utcnow())
        if state != "waiting":
            return state
        await asyncio.sleep(poll)


async def run_publication(
    db: AsyncSession, a: Article, now: datetime | None = None, *, poll: float = BUILD_POLL_SECONDS
) -> str:
    """Publish an approved article and wait for the build (the worker's publish job)."""
    now = now or utcnow()
    if a.status == ART_APPROVED:
        await start_publication(db, a, now)
    if a.status != ART_PUBLISHING:
        return a.status
    return await wait_for_build(db, a, poll=poll)


async def unpublish(db: AsyncSession, a: Article, now: datetime) -> list[str]:
    """Remove the article's files and request a build; the article is then `held`."""
    root = files.articles_dir()
    removed = files.remove_article_files(root, a.live_files or {})
    files.request_build(root, f"unpublish {a.key}", now)
    a.live_files = {}
    a.live_urls = {}
    a.status = ART_HELD
    await db.commit()
    return removed


# --- the tick --------------------------------------------------------------------------------


@dataclass
class TickReport:
    plan: str = ""
    actions: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.actions.append(text)
        log.info("Articles: %s", text)


Runner = Callable[[str, str], Awaitable[Any]]  # (job name, article key)


def due_action(a: Article, now: datetime) -> str | None:
    """What the tick would do with this article now (pure, for tests and --dry-run)."""
    if a.status == ART_PLANNED and now >= production_due_at(a):
        return "produce"
    if a.status == ART_CHANGES_REQUESTED:
        return "produce"
    if a.status == ART_READY and now >= proposal_due_at(a):
        return "propose"
    if a.status == ART_PROPOSED:
        due = publish_due_at(a)
        if due is not None and now >= due:
            return "approve"
    if a.status == ART_APPROVED:
        return "publish"
    if a.status == ART_PUBLISHING:
        return "check_build"
    if a.status in ART_PRODUCING and a.production_started_at is not None:
        if now - a.production_started_at >= STALE_PRODUCTION:
            return "recover"
    return None


async def tick(
    db: AsyncSession,
    now: datetime | None = None,
    *,
    run: Runner | None = None,
    dry_run: bool = False,
) -> TickReport:
    """One pass over every article. `run(job, key)` hands production and publication to the
    worker queue; without it they run here, one after the other (CLI, development)."""
    now = now or utcnow()
    report = TickReport()
    if not dry_run:
        report.plan = (await import_plan(db)).summary()
    rows = (
        (
            await db.execute(
                select(Article).where(Article.kind.in_(KINDS)).order_by(Article.publish_at)
            )
        )
        .scalars()
        .all()
    )  # the politics pages have their own tick (app/politics/schedule.py)
    for a in rows:
        action = due_action(a, now)
        if action is None:
            continue
        if dry_run:
            report.add(f"{a.key}: would {action} ({a.status})")
            continue
        if action == "recover":
            await recover_stale(db, a, now)
            report.add(f"{a.key}: stale production recovered ({a.status})")
        elif action == "produce":
            if run is not None:
                await run("produce_article", a.key)
                report.add(f"{a.key}: production queued")
            else:
                state = await run_production(db, a, now)
                report.add(f"{a.key}: produced ({state})")
        elif action == "propose":
            sent = await propose(db, a, now)
            report.add(f"{a.key}: proposal {'sent' if sent else 'not sent'}")
        elif action in ("approve", "publish"):
            if action == "approve" and not await claim(
                db, a, (ART_PROPOSED,), ART_APPROVED, approved_at=now
            ):
                continue
            if run is not None:
                await run("publish_article", a.key)
                report.add(f"{a.key}: publication queued")
            else:
                await start_publication(db, a, now)
                report.add(f"{a.key}: files written, build requested ({a.status})")
        elif action == "check_build":
            state = await check_build(db, a, now)
            if state != "waiting":
                report.add(f"{a.key}: build checked ({state})")
    return report


async def get_by_key(db: AsyncSession, key: str) -> Article | None:
    return (await db.execute(select(Article).where(Article.key == key))).scalar_one_or_none()
