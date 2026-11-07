"""Politics in your canton by hand (D-074; docs/runbooks/politics.md).

    python -m scripts.politics list
    python -m scripts.politics discover [--canton zh]
    python -m scripts.politics produce <key> [--force]
    python -m scripts.politics publish <key>
    python -m scripts.politics questions <key>
    python -m scripts.politics roundup [--canton zh]      # create this week's round-up now
    python -m scripts.politics tick

--dry-run (before or after the command) uses no AI and changes nothing: `discover` reads
the sources and prints what it finds, `produce` prints the page's brief and its sources,
`publish` lists the files it would write, `tick` lists what is due. The commands work
whether or not POLITICS_ENABLED is set; the worker's schedule only runs when it is.

On the server: docker compose -p civics-prod exec worker python -m scripts.politics list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import select

from app.articles import files, workflow
from app.articles.constants import POLITICS_KINDS
from app.content import fetch
from app.db import SessionLocal, utcnow
from app.models import ART_APPROVED, ART_PUBLISHED, Article
from app.politics import discover, schedule
from app.politics.produce import PoliticsRun
from app.politics.sources import for_canton


def say(text: str) -> None:
    print(text)


def _row(a: Article) -> str:
    title = (a.english or {}).get("title") or (a.plan or {}).get("title", "")
    langs = len(a.live_urls or {})
    when = workflow.zurich_time(a.publish_at)
    q = (a.plan or {}).get("questions")
    extra = f" q {q}" if q is not None else ""
    return (
        f"{a.key:44} {a.kind:8} {a.status:16} {when:32} {langs} lang "
        f"CHF {a.cost_chf:5.2f}{extra}  {title[:46]}"
    )


async def _get(db, key: str) -> Article:
    a = await workflow.get_by_key(db, key)
    if a is None or a.kind not in POLITICS_KINDS:
        raise SystemExit(f"No politics page {key!r}; see `list`.")
    return a


async def cmd_list(db, args) -> int:
    rows = (
        await db.execute(
            select(Article).where(Article.kind.in_(POLITICS_KINDS)).order_by(Article.publish_at)
        )
    ).scalars()
    any_row = False
    for a in rows:
        any_row = True
        say(_row(a))
        if a.last_error and a.status in ("needs_attention", "publish_failed", "held"):
            say(f"{'':44} ! {a.last_error.splitlines()[0][:110]}")
    if not any_row:
        say("No politics pages yet. Run: python -m scripts.politics discover")
    return 0


async def cmd_discover(db, args) -> int:
    cs = for_canton(args.canton)
    if cs is None:
        raise SystemExit(f"No block for {args.canton!r} in content/politics/sources.yaml")
    if args.dry_run:
        today = discover.zurich_date(utcnow())
        bad = 0
        async with fetch.new_client() as client:
            for source in cs.of_type("listing", "rss", "vote_list"):
                entries, errors = await discover.read_source(client, source, today)
                bad += len(errors)
                say(f"{source.id:26} {source.type:9} {len(entries):3} item(s) {'; '.join(errors)}")
                for e in entries[:3]:
                    say(f"{'':26}   {e.item_date}  {e.title[:70]}")
        return 1 if bad else 0
    report = await discover.discover(db, cs, utcnow())
    say(report.summary())
    for key in report.votes_created:
        say(f"  vote page: {key}")
    for e in report.errors:
        say(f"  error: {e}")
    return 1 if report.errors else 0


async def cmd_roundup(db, args) -> int:
    cs = for_canton(args.canton)
    if cs is None:
        raise SystemExit(f"No block for {args.canton!r}")
    friday = schedule.roundup_friday(utcnow())
    key = schedule.roundup_key(cs.canton, friday)
    if args.dry_run:
        start, end = schedule.roundup_period(friday)
        say(f"would create {key} for {start} to {end}")
        return 0
    key, created = await schedule.ensure_roundup(db, cs, utcnow())
    say(f"{key}: {'created' if created else 'exists already or not due'}")
    return 0


async def cmd_produce(db, args) -> int:
    a = await _get(db, args.key)
    if args.dry_run:
        run = PoliticsRun(db, a, utcnow())
        await run.load_context()
        say(json.dumps(run.article_brief(), ensure_ascii=False, indent=2, default=str))
        for s in a.sources_read or []:
            say(f"  source {'read' if s.get('ok') else 'NOT READ'}: {s['url']}")
        return 0
    state = await workflow.run_production(db, a, force=args.force)
    if state is None:
        say(f"{a.key} is {a.status}; not produced (use --force to produce again)")
        return 1
    say(f"{a.key}: {state} (revision {a.revision}, CHF {a.cost_chf:.2f} in total)")
    if a.last_error and state in ("needs_attention", "held"):
        say(f"  reason: {a.last_error}")
    return 0 if state in ("ready", "changes_requested") else 1


async def cmd_publish(db, args) -> int:
    a = await _get(db, args.key)
    if args.dry_run:
        texts, pages = workflow.build_files(a, utcnow()) if a.english else ({}, {})
        for rel in texts:
            say(f"would write {files.articles_dir() / rel}")
        for lang, path in pages.items():
            say(f"  {lang}: {path}")
        return 0 if texts else 1
    if a.status != ART_APPROVED:
        try:
            await workflow.publish_now(db, a, utcnow())
        except workflow.ActionRefused:
            say(f"{a.key} is {a.status}; it cannot be published from that state")
            return 1
    say(f"Publishing {a.key}: writing files and waiting for the site builder ...")
    state = await workflow.run_publication(db, a)
    say(f"{a.key}: {state}")
    if a.last_error and state == "publish_failed":
        say(a.last_error)
    return 0 if state == ART_PUBLISHED else 1


async def cmd_questions(db, args) -> int:
    a = await _get(db, args.key)
    if a.status != ART_PUBLISHED or a.kind not in ("roundup", "vote"):
        say(f"{a.key} is a {a.kind} in state {a.status}; needs a published round-up or vote")
        return 1
    if args.dry_run:
        say(f"would write, check and translate 2-3 questions for {a.key}")
        return 0
    say(f"{a.key}: {await schedule.run_questions(db, a, utcnow())}")
    return 0


async def cmd_tick(db, args) -> int:
    report = await schedule.tick(db, dry_run=args.dry_run)
    for line in report.actions or ["nothing due"]:
        say(line)
    return 0


COMMANDS = {
    "list": cmd_list,
    "discover": cmd_discover,
    "roundup": cmd_roundup,
    "produce": cmd_produce,
    "publish": cmd_publish,
    "questions": cmd_questions,
    "tick": cmd_tick,
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.politics", description=__doc__.split("\n")[0]
    )
    p.add_argument("--dry-run", action="store_true", help="no AI, no changes")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common])
    for name in ("discover", "roundup"):
        sub.add_parser(name, parents=[common]).add_argument("--canton", default="zh")
    pr = sub.add_parser("produce", parents=[common])
    pr.add_argument("key")
    pr.add_argument("--force", action="store_true", help="produce again from any state")
    for name in ("publish", "questions"):
        sub.add_parser(name, parents=[common]).add_argument("key")
    sub.add_parser("tick", parents=[common])
    return p


async def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    async with SessionLocal() as db:
        return await COMMANDS[args.command](db, args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
