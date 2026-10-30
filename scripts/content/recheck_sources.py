"""Yearly source re-check (PLAN.md, Question bank, step 6): run the source check again on
every question that is not retired and whose most recently checked source is older than
`--older-than` days (default 300, so it happens well before the validator's 365-day limit).

Usage:
  python -m scripts.content.recheck_sources [--older-than 300] [--canton zh] [--topic CODE]
      [--ids ...] [--direct] [--model ...] [--resume BATCH_ID]

Same rules as scripts.content.source_check: a supported answer refreshes `checked`;
not_supported or a dead link sets the question to `needs_fix`, which takes it out of the
app at the next deploy until it is fixed and approved again."""

from __future__ import annotations

import sys
from datetime import timedelta

import httpx

from app.models import Q_RETIRED
from scripts.content._common import (
    add_ai_args,
    add_selection_args,
    base_parser,
    load,
    main_of,
    root_of,
    run_options,
    say,
    select_questions,
    today_of,
)
from scripts.content.source_check import check_sources


async def run(argv: list[str] | None = None, *, client: httpx.AsyncClient | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--older-than", type=int, default=300, metavar="DAYS")
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=800)
    args = parser.parse_args(argv)
    root = root_of(args)
    today = today_of(args)
    cutoff = today - timedelta(days=args.older_than)
    cs = load(root)
    todo = [
        q
        for q in select_questions(cs, args, None)
        if q.status != Q_RETIRED and max(s.checked for s in q.sources) < cutoff
    ]
    if not todo:
        say(f"No question has all its sources checked before {cutoff.isoformat()}.")
        return 0
    say(f"{len(todo)} question(s) last checked before {cutoff.isoformat()}")
    await check_sources(root, todo, options=run_options(args), today=today, client=client)
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
