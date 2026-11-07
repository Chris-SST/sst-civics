"""The article pipeline by hand (D-073; docs/runbooks/articles.md).

    python -m scripts.articles list
    python -m scripts.articles import-plan
    python -m scripts.articles produce <key> [--force]
    python -m scripts.articles propose <key>
    python -m scripts.articles publish <key>
    python -m scripts.articles hold <key>
    python -m scripts.articles unpublish <key>
    python -m scripts.articles preview <key> --out <dir>
    python -m scripts.articles tick

--dry-run (before the command) uses no AI and changes nothing: `tick` lists what is due,
`produce` validates placeholder text, `propose` prints the email, `publish` lists the files,
`preview` writes placeholder files when the article has no text yet. These commands work
whether or not ARTICLES_ENABLED is set; the worker's schedule only runs when it is.

On the server: docker compose -p civics-prod exec worker python -m scripts.articles list
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.articles import dryrun, files, plan, workflow
from app.articles.constants import KINDS
from app.articles.validate import validate_article
from app.db import SessionLocal, utcnow
from app.models import ART_APPROVED, ART_HELD, ART_PUBLISHED, Article


def say(text: str) -> None:
    print(text)


def _row(a: Article) -> str:
    title = (a.english or {}).get("title") or a.plan.get("title", "")
    langs = sum(1 for t in (a.translations or {}).values() if t.get("status") == "ok")
    when = workflow.zurich_time(a.publish_at)
    return (
        f"{a.key:32} {a.status:17} {when:32} rev {a.revision:<2} +{langs} lang "
        f"CHF {a.cost_chf:5.2f}  {title[:50]}"
    )


async def _get(db, key: str) -> Article:
    a = await workflow.get_by_key(db, key)
    if a is None:
        raise SystemExit(f"No article {key!r}; run import-plan first or check the key.")
    return a


async def cmd_list(db, args) -> int:
    query = select(Article).where(Article.kind.in_(KINDS)).order_by(Article.publish_at)
    rows = (await db.execute(query)).scalars()  # politics pages: python -m scripts.politics list
    any_row = False
    for a in rows:
        any_row = True
        say(_row(a))
        if a.last_error and a.status in ("needs_attention", "publish_failed"):
            say(f"{'':32} ! {a.last_error.splitlines()[0][:110]}")
    if not any_row:
        say("No articles yet. Run: python -m scripts.articles import-plan")
    return 0


async def cmd_import(db, args) -> int:
    if args.dry_run:
        entries, errors = plan.load_plan(plan.plan_path())
        say(f"{len(entries)} valid entr(ies) in {plan.plan_path()}")
        for e in errors:
            say(f"  error: {e}")
        return 1 if errors else 0
    report = await plan.import_plan(db)
    say(report.summary())
    for e in report.errors:
        say(f"  error: {e}")
    return 1 if report.errors else 0


def _plan_keys(rows) -> set[str]:
    return {a.key for a in rows}


async def cmd_produce(db, args) -> int:
    a = await _get(db, args.key)
    if args.dry_run:
        keys = _plan_keys((await db.execute(select(Article))).scalars())
        content = dryrun.placeholder(a.plan, kind=a.kind)
        problems = validate_article(
            content,
            kind=a.kind,
            lang="en",
            plan_keys=keys,
            read_urls={s["url"] for s in content["sources"]},
        )
        say(f"Dry run for {a.key}: placeholder text, {len(problems)} problem(s), nothing stored")
        for p in problems:
            say(f"  - {p}")
        return 1 if problems else 0
    state = await workflow.run_production(db, a, force=args.force)
    if state is None:
        say(f"{a.key} is {a.status}; not produced (use --force to produce again)")
        return 1
    say(f"{a.key}: {state} (revision {a.revision}, CHF {a.cost_chf:.2f} in total)")
    if a.last_error and state == "needs_attention":
        say(f"  reason: {a.last_error}")
    return 0 if state in ("ready", "changes_requested") else 1


async def cmd_propose(db, args) -> int:
    a = await _get(db, args.key)
    if a.english is None:
        say(f"{a.key} has no text yet ({a.status})")
        return 1
    msgs = await workflow.propose(db, a, utcnow(), send=not args.dry_run)
    if not msgs:
        say("No email sent (no recipient, or the mail server refused it).")
        return 1
    if args.dry_run:
        say(f"To: {msgs[0].to}\nSubject: {msgs[0].subject}\n\n{msgs[0].text}")
    else:
        say(f"Proposal sent to {len(msgs)} recipient(s); {a.key} is {a.status}")
    return 0


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


async def cmd_hold(db, args) -> int:
    a = await _get(db, args.key)
    if args.dry_run:
        say(f"would hold {a.key} ({a.status})")
        return 0
    try:
        await workflow.hold(db, a)
    except workflow.ActionRefused:
        say(f"{a.key} is {a.status}; it cannot be held now")
        return 1
    say(f"{a.key} is {ART_HELD}")
    return 0


async def cmd_unpublish(db, args) -> int:
    a = await _get(db, args.key)
    if args.dry_run:
        for rel in (a.live_files or {}).values():
            say(f"would remove {files.articles_dir() / rel}")
        return 0
    removed = await workflow.unpublish(db, a, utcnow())
    say(f"Removed {len(removed)} file(s) and requested a build; {a.key} is {a.status}")
    return 0


async def cmd_preview(db, args) -> int:
    a = await _get(db, args.key)
    out = Path(args.out)
    if a.english is None or args.dry_run:
        content = dryrun.placeholder(a.plan, kind=a.kind)
        a = Article(
            key=a.key,
            kind=a.kind,
            category=a.category,
            canton=a.canton,
            plan=a.plan,
            publish_at=a.publish_at,
            english={**content, "checked": utcnow().date().isoformat()},
            translations={},
            live_files={},
        )
        say("No text yet (or --dry-run): writing placeholder English only")
    texts, pages = workflow.build_files(a, utcnow())
    files.write_article_files(out, texts, {})
    for rel in texts:
        say(f"wrote {out / rel}")
    say(f"Build the site with ARTICLES_DIR={out.resolve()}; pages: {', '.join(pages.values())}")
    return 0


async def cmd_tick(db, args) -> int:
    report = await workflow.tick(db, dry_run=args.dry_run)
    if report.plan:
        say(report.plan)
    for line in report.actions or ["nothing due"]:
        say(line)
    return 0


COMMANDS = {
    "list": cmd_list,
    "import-plan": cmd_import,
    "produce": cmd_produce,
    "propose": cmd_propose,
    "publish": cmd_publish,
    "hold": cmd_hold,
    "unpublish": cmd_unpublish,
    "preview": cmd_preview,
    "tick": cmd_tick,
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m scripts.articles", description=__doc__.split("\n")[0]
    )
    p.add_argument("--dry-run", action="store_true", help="no AI, no changes")
    # --dry-run is also accepted after the command
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common])
    sub.add_parser("import-plan", parents=[common])
    pr = sub.add_parser("produce", parents=[common])
    pr.add_argument("key")
    pr.add_argument("--force", action="store_true", help="produce again from any state")
    for name in ("propose", "publish", "hold", "unpublish"):
        sub.add_parser(name, parents=[common]).add_argument("key")
    pv = sub.add_parser("preview", parents=[common])
    pv.add_argument("key")
    pv.add_argument("--out", required=True)
    sub.add_parser("tick", parents=[common])
    return p


async def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    async with SessionLocal() as db:
        return await COMMANDS[args.command](db, args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
