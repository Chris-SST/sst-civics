"""The politics tick (every 15 minutes in the worker, only with POLITICS_ENABLED; D-074).

Per canton of POLITICS_CANTONS:

1. **Discovery** every morning (the 06:00 tick, Zurich time), before a round-up, and on
   the first run: listings, feeds and vote lists into `politics_items`; announced votes
   become vote pages.
2. **Round-up** every Friday at 07:00 for Friday to Thursday (key `zh-week-<ISO year>-<ISO
   week>` of that Friday). A week with fewer than four political items is skipped (held).
3. **Vote explainers** are produced POLITICS_VOTE_LEAD_DAYS (28) before the vote. After the
   vote the result check runs once a day for 60 days; when the figures are on the
   authorities' data or pages the page is written again with its Result section.
4. **Who's who** on the 1st of each month from 07:00 (and on the first run): the people
   pages are read and their facts listed; only when they differ from the published version
   is the page written again.
5. Every politics page then moves on without a proposal email: ready -> approved ->
   publishing -> published (the same build request and live check as the articles); a
   failure is needs_attention or publish_failed with one email, and in the digest.
6. After publication of a round-up or vote explainer its practice questions are made.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.articles import workflow
from app.articles.constants import POLITICS_KINDS
from app.articles.plan import new_nonce
from app.config import get_settings
from app.content import fetch
from app.db import utcnow
from app.llm import articles as llm
from app.llm import politics as ai
from app.models import (
    ART_APPROVED,
    ART_CHANGES_REQUESTED,
    ART_PLANNED,
    ART_PRODUCING,
    ART_PUBLISHED,
    ART_PUBLISHING,
    ART_READY,
    Article,
    PoliticsItem,
)
from app.politics import discover
from app.politics.discover import zurich_at, zurich_date
from app.politics.produce import source_record
from app.politics.sources import CantonSources, for_canton
from app.study.clock import ZURICH

log = logging.getLogger(__name__)

DISCOVERY_HOUR = 6
ROUNDUP_HOUR = 7
ROUNDUP_GRACE = timedelta(hours=36)  # a round-up missed by more than this is not written
RESULT_WINDOW = timedelta(days=60)
FRIDAY = 4


# --- dates and keys (pure) ----------------------------------------------------------------------


def roundup_friday(now: datetime) -> date:
    """The latest Friday whose 07:00 (Zurich) is not after `now`."""
    local = now.astimezone(ZURICH)
    day = local.date() - timedelta(days=(local.weekday() - FRIDAY) % 7)
    if day == local.date() and local.hour < ROUNDUP_HOUR:
        day -= timedelta(days=7)
    return day


def roundup_period(friday: date) -> tuple[date, date]:
    """Friday to Thursday: the week before the Friday of publication."""
    return friday - timedelta(days=7), friday - timedelta(days=1)


def roundup_key(canton: str, friday: date) -> str:
    year, week, _ = friday.isocalendar()
    return f"{canton}-week-{year}-{week:02d}"


def whoswho_key(canton: str) -> str:
    return f"{canton}-whos-who"


def discovery_due(now: datetime) -> bool:
    local = now.astimezone(ZURICH)
    return local.hour == DISCOVERY_HOUR and local.minute < 15


def whoswho_due(now: datetime, last_check: str | None) -> bool:
    local = now.astimezone(ZURICH)
    if last_check is None:
        return True
    return local.day == 1 and local.hour >= ROUNDUP_HOUR and last_check != local.date().isoformat()


def roster_hash(roster: dict[str, Any], seats: dict[str, int]) -> str:
    canonical = json.dumps({"roster": roster, "seats": seats}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def due_action(a: Article, now: datetime) -> str | None:
    """What the tick does with a politics page now (pure, for tests and --dry-run)."""
    if a.status == ART_PLANNED and now >= a.publish_at:
        if a.kind == "vote" and not (a.plan or {}).get("result"):
            if zurich_date(now) >= date.fromisoformat(a.plan["vote_date"]):
                return None  # the vote has passed: only a result brings it back
        return "produce"
    if a.status == ART_CHANGES_REQUESTED:
        return "produce"
    if a.status == ART_READY:
        return "approve"  # no proposal email for politics pages
    if a.status == ART_APPROVED:
        return "publish"
    if a.status == ART_PUBLISHING:
        return "check_build"
    if a.status in ART_PRODUCING and a.production_started_at is not None:
        if now - a.production_started_at >= workflow.STALE_PRODUCTION:
            return "recover"
    if (
        a.status == ART_PUBLISHED
        and a.kind in ("roundup", "vote")
        and (a.plan or {}).get("questions_revision") != a.published_revision
    ):
        return "questions"
    return None


# --- rows ----------------------------------------


def new_page(key: str, kind: str, canton: str, publish_at: datetime, plan: dict) -> Article:
    return Article(
        key=key,
        kind=kind,
        category="politics",
        canton=canton,
        publish_at=publish_at,
        status=ART_PLANNED,
        plan={"key": key, "kind": kind, "set_canton": canton, **plan},
        translations={},
        reviews=[],
        feedback=[],
        sources_read=[],
        live_urls={},
        live_files={},
        review_nonce=new_nonce(),
    )


def set_plan(a: Article, **values: Any) -> None:
    a.plan = {**(a.plan or {}), **values}  # a new dict, so the JSON column is saved


async def ensure_roundup(
    db: AsyncSession, cs: CantonSources, now: datetime
) -> tuple[str | None, bool]:
    """(key, created) for this week's round-up, or (None, False) when none is due."""
    friday = roundup_friday(now)
    publish_at = zurich_at(friday, ROUNDUP_HOUR)
    if now - publish_at > ROUNDUP_GRACE:
        return None, False
    key = roundup_key(cs.canton, friday)
    if await workflow.get_by_key(db, key) is not None:
        return key, False
    start, end = roundup_period(friday)
    db.add(
        new_page(
            key,
            "roundup",
            cs.canton,
            publish_at,
            {
                "title": f"{cs.name}: politics in the week to {end.strftime('%d %B %Y')}",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            },
        )
    )
    await db.commit()
    return key, True


# --- who's who ----------------------------------------


async def read_people(cs: CantonSources, now: datetime) -> tuple[list[dict], dict[str, int]]:
    """The people pages (and the member pages they link to) as sources, and the seats per
    party counted from the Kantonsrat's member list."""
    pages: list[dict[str, Any]] = []
    seats: dict[str, int] = {}
    async with fetch.new_client() as client:
        for source in cs.of_type("people"):
            raw, err = await discover.fetch_raw(client, source.url)
            if err or raw is None:
                pages.append(source_record(source.url, source.id, "", now))
                continue
            text = fetch.html_to_text(raw)
            title = text.splitlines()[0] if text else source.id
            pages.append(source_record(source.url, title, text, now))
            if source.seats:
                seats = discover.party_seats(text)
            if source.follow:
                for url in discover.linked_pages(raw, source.url, source.follow)[:12]:
                    page = await fetch.fetch_page(client, url)
                    first = page.text.splitlines()[0] if page.text else url
                    pages.append(source_record(url, first, page.text if page.readable else "", now))
    return pages, seats


async def check_whoswho(
    db: AsyncSession, cs: CantonSources, now: datetime, *, dry_run: bool = False
) -> str:
    """The monthly check. Returns what happened, for the tick report."""
    key = whoswho_key(cs.canton)
    a = await workflow.get_by_key(db, key)
    if a is not None and a.status not in (ART_PUBLISHED, ART_PLANNED):
        return f"{key}: not checked ({a.status})"
    if dry_run:
        return f"{key}: would read the people pages and compare"
    pages, seats = await read_people(cs, now)
    readable = [p for p in pages if p["ok"]]
    today = zurich_date(now).isoformat()
    if len(readable) < 3:
        if a is not None:
            set_plan(a, last_check=today)
            await db.commit()
        return f"{key}: only {len(readable)} people page(s) readable; not checked"
    s = get_settings()
    result = await llm.call(
        purpose=ai.PURPOSE_ROSTER,
        prompt_name=ai.PROMPT_ROSTER,
        model=s.politics_extract_model,
        payload={
            "canton": cs.name,
            "pages": [{"url": p["url"], "text": p["text"][:15_000]} for p in readable],
        },
        schema=ai.ROSTER_SCHEMA,
        effort="low",
        max_tokens=4000,
    )
    await llm.record(db, result)
    if not result.ok:
        await db.commit()
        return f"{key}: the roster could not be read ({result.error})"
    roster = result.data or {}
    digest = roster_hash(roster, seats)
    if a is None:
        a = new_page(key, "whoswho", cs.canton, now, {"title": f"{cs.name}: who's who"})
        db.add(a)
    elif a.status == ART_PUBLISHED and (a.plan or {}).get("roster_hash") == digest:
        set_plan(a, last_check=today)
        await db.commit()
        return f"{key}: unchanged, not republished"
    set_plan(a, last_check=today, roster=roster, seats=seats, roster_hash=digest)
    a.sources_read = pages
    a.status = ART_PLANNED
    a.publish_at = now
    await db.commit()
    return f"{key}: changed, to be written"


# --- vote results ----------------------------------------


async def check_result(db: AsyncSession, a: Article, cs: CantonSources, now: datetime) -> bool:
    """Look for the official result of a vote that has taken place. True when found (the
    page is then written again with its Result section)."""
    plan = a.plan or {}
    today = zurich_date(now).isoformat()
    if plan.get("result") or plan.get("result_checked") == today:
        return False
    vote_date = date.fromisoformat(plan["vote_date"])
    if not (vote_date < zurich_date(now) <= vote_date + RESULT_WINDOW):
        return False
    set_plan(a, result_checked=today)
    result: dict[str, Any] | None = None
    if plan.get("vote_level") == "federal":
        item = await db.scalar(
            select(PoliticsItem).where(
                PoliticsItem.canton == cs.canton,
                PoliticsItem.source_id == "ch-federal-votes",
                PoliticsItem.url.like(f"%#vorlage-{plan.get('federal_id')}"),
            )
        )
        fed = ((item.data or {}).get("federal") or {}) if item else {}
        if fed.get("result"):
            r = fed["result"]
            text = (
                f"Eidgenössische Volksabstimmung vom {vote_date.strftime('%d.%m.%Y')}: "
                f"{fed.get('title', '')}. Ergebnis: {fed.get('status', '')}. Ja-Anteil "
                f"{r['yes_percent']} Prozent, Stimmbeteiligung {r['turnout_percent']} Prozent. "
                "Quelle: Bundeskanzlei, Daten der eidgenössischen Volksabstimmungen."
            )
            result = {
                **r,
                "source_url": item.data.get("cite") or item.url.split("#")[0],
                "source_title": f"Federal Chancellery: vote of {vote_date.strftime('%d %B %Y')}",
                "source_text": text,
            }
    else:
        notices = (
            (
                await db.execute(
                    select(PoliticsItem).where(
                        PoliticsItem.canton == cs.canton,
                        PoliticsItem.level == "canton",
                        PoliticsItem.item_date >= vote_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        notices = [n for n in notices if discover.RESULT_TITLE.search(n.title)]
        s = get_settings()
        async with fetch.new_client() as client:
            for n in notices[:3]:
                page = await fetch.fetch_page(client, n.url)
                if not page.readable:
                    continue
                call = await llm.call(
                    purpose=ai.PURPOSE_RESULTS,
                    prompt_name=ai.PROMPT_RESULTS,
                    model=s.politics_extract_model,
                    payload={
                        "vote_date": vote_date.isoformat(),
                        "proposal_title_de": plan.get("title_de"),
                        "text": page.text[:15_000],
                    },
                    schema=ai.RESULTS_SCHEMA,
                    effort="low",
                    max_tokens=2000,
                )
                await llm.record(db, call)
                for r in (call.data or {}).get("results") or []:
                    if (
                        discover.title_overlap(str(r.get("title_de", "")), plan.get("title_de", ""))
                        < 1
                    ):
                        continue
                    yes, turnout = r.get("yes_percent"), r.get("turnout_percent")
                    if (
                        isinstance(yes, (int, float))
                        and isinstance(turnout, (int, float))
                        and 0 < yes < 100
                        and 0 < turnout <= 100
                        and isinstance(r.get("accepted"), bool)
                    ):
                        result = {
                            "yes_percent": round(float(yes), 2),
                            "turnout_percent": round(float(turnout), 2),
                            "accepted": r["accepted"],
                            "source_url": n.url,
                            "source_title": n.title,
                        }
                        break
                if result:
                    break
    if result is None:
        await db.commit()
        return False
    set_plan(a, result=result)
    if a.status == ART_PUBLISHED:
        a.status = ART_PLANNED
        a.publish_at = now
    await db.commit()
    log.info("Politics %s: result found, to be written again", a.key)
    return True


# --- the tick ----------------------------------------


@dataclass
class TickReport:
    actions: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        self.actions.append(text)
        log.info("Politics: %s", text)


Runner = Callable[[str, str], Awaitable[Any]]


async def run_questions(db: AsyncSession, a: Article, now: datetime) -> str:
    from app.politics import questions

    try:
        n, note = await questions.generate(db, a, now)
    except Exception as exc:  # noqa: BLE001  questions never block the page
        await db.rollback()
        a = await db.get(Article, a.id)
        n, note = 0, f"failed: {exc.__class__.__name__}"
        log.exception("Politics %s: questions failed", a.key)
    set_plan(a, questions_revision=a.published_revision, questions_note=note, questions=n)
    await db.commit()
    return note


async def tick(
    db: AsyncSession,
    now: datetime | None = None,
    *,
    run: Runner | None = None,
    dry_run: bool = False,
) -> TickReport:
    """One pass. `run(job, key)` hands production, publication and the questions to the
    worker queue; without it they run here (CLI, development, tests)."""
    now = now or utcnow()
    report = TickReport()
    for canton in get_settings().politics_canton_codes:
        cs = for_canton(canton)
        if cs is None:
            report.add(f"{canton}: no block in content/politics/sources.yaml")
            continue
        await canton_tick(db, cs, now, report, run=run, dry_run=dry_run)
    rows = (
        (
            await db.execute(
                select(Article).where(Article.kind.in_(POLITICS_KINDS)).order_by(Article.publish_at)
            )
        )
        .scalars()
        .all()
    )
    for a in rows:
        action = due_action(a, now)
        if action is None:
            continue
        if dry_run:
            report.add(f"{a.key}: would {action} ({a.status})")
            continue
        await act(db, a, action, now, report, run)
    return report


async def canton_tick(
    db: AsyncSession,
    cs: CantonSources,
    now: datetime,
    report: TickReport,
    *,
    run: Runner | None,
    dry_run: bool,
) -> None:
    known = await db.scalar(
        select(func.count()).select_from(PoliticsItem).where(PoliticsItem.canton == cs.canton)
    )
    friday = roundup_friday(now)
    roundup_now = (
        now - zurich_at(friday, ROUNDUP_HOUR) <= ROUNDUP_GRACE
        and (await workflow.get_by_key(db, roundup_key(cs.canton, friday))) is None
    )
    if discovery_due(now) or not known or roundup_now:
        if dry_run:
            report.add(f"{cs.canton}: would run discovery")
        else:
            d = await discover.discover(db, cs, now)
            report.add(d.summary())
    if roundup_now:
        if dry_run:
            report.add(f"{roundup_key(cs.canton, friday)}: would create this week's round-up")
        else:
            key, created = await ensure_roundup(db, cs, now)
            if created:
                report.add(f"{key}: round-up created")
    w = await workflow.get_by_key(db, whoswho_key(cs.canton))
    if whoswho_due(now, (w.plan or {}).get("last_check") if w else None):
        report.add(await check_whoswho(db, cs, now, dry_run=dry_run))
    if not dry_run:
        votes = (
            (
                await db.execute(
                    select(Article).where(Article.kind == "vote", Article.status == ART_PUBLISHED)
                )
            )
            .scalars()
            .all()
        )
        for v in votes:
            if ((v.plan or {}).get("set_canton") or v.canton) == cs.canton and await check_result(
                db, v, cs, now
            ):
                report.add(f"{v.key}: result found")


async def act(
    db: AsyncSession, a: Article, action: str, now: datetime, report: TickReport, run: Runner | None
) -> None:
    if action == "recover":
        await workflow.recover_stale(db, a, now)
        report.add(f"{a.key}: stale production recovered ({a.status})")
    elif action == "produce":
        if run is not None:
            await run("produce_politics_page", a.key)
            report.add(f"{a.key}: production queued")
        else:
            state = await workflow.run_production(db, a, now)
            report.add(f"{a.key}: produced ({state})")
    elif action in ("approve", "publish"):
        if action == "approve" and not await workflow.claim(
            db, a, (ART_READY,), ART_APPROVED, approved_at=now
        ):
            return
        if run is not None:
            await run("publish_politics_page", a.key)
            report.add(f"{a.key}: publication queued")
        else:
            await workflow.start_publication(db, a, now)
            report.add(f"{a.key}: files written, build requested ({a.status})")
    elif action == "check_build":
        state = await workflow.check_build(db, a, now)
        if state != "waiting":
            report.add(f"{a.key}: build checked ({state})")
    elif action == "questions":
        if run is not None:
            await run("politics_questions", a.key)
            report.add(f"{a.key}: questions queued")
        else:
            report.add(f"{a.key}: questions: {await run_questions(db, a, now)}")
