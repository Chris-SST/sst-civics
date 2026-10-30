"""Check that every cited source still answers (HEAD or GET, no AI). The worker runs the
same check weekly as the job `check_source_links`.

Usage:
  python -m scripts.content.check_links [--root content] [--no-db]

Questions with a broken link are flagged in the database (`file_sync_pending`, a
`broken_links` entry in `pending_changes`) unless --no-db is given, and the report is
written to content/reports/link-check-<date>.md. Rules: app/content/links.py."""

from __future__ import annotations

import sys

import httpx

from app.content.links import run_link_check
from app.db import SessionLocal
from scripts.content._common import base_parser, main_of, root_of, say, today_of


async def run(argv: list[str] | None = None, *, client: httpx.AsyncClient | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--no-db", action="store_true", help="report only, flag nothing")
    args = parser.parse_args(argv)
    root = root_of(args)
    if args.no_db:
        report = await run_link_check(None, root, client=client, today=today_of(args))
    else:
        async with SessionLocal() as db:
            report = await run_link_check(db, root, client=client, today=today_of(args))
    for url, error in sorted(report.broken.items()):
        say(f"BROKEN {url}: {error}")
    say(
        f"{report.checked_urls} URL(s) checked, {len(report.broken)} broken, "
        f"{len(report.flagged)} question(s) flagged; report: {report.report_path}"
    )
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
