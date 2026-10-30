"""Move checked drafts to review (PLAN.md, Question bank, steps 2 to 4).

Usage:
  python -m scripts.content.promote [--ids ...] [--canton zh] [--topic CODE] [--dry-run]

A draft goes to `in_review` when the independent answer agrees with the key and the source
check found the answer supported, both for the question's current version. Everything else
stays a draft and the reason is printed. Approval itself is a person's decision in the admin
area (Admin, Question bank), never this script's."""

from __future__ import annotations

import sys

from app.content import store
from app.content.schema import QuestionFile
from app.models import Q_DRAFT, Q_IN_REVIEW
from scripts.content._common import (
    add_selection_args,
    base_parser,
    load,
    main_of,
    root_of,
    say,
    select_questions,
)


def blocker(q: QuestionFile) -> str | None:
    """Why `q` cannot go to review yet, or None."""
    answer = q.checks.independent_answer if q.checks else None
    source = q.checks.source if q.checks else None
    if answer is None or answer.version not in (None, q.version):
        return "no independent answer for this version"
    if not answer.agrees:
        return "the independent answer disagrees"
    if source is None or source.version not in (None, q.version):
        return "no source check for this version"
    if source.verdict != "supported":
        return f"source check: {source.verdict}"
    return None


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    add_selection_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = root_of(args)
    cs = load(root)
    moved = waiting = 0
    for q in select_questions(cs, args, [Q_DRAFT]):
        why = blocker(q)
        if why:
            waiting += 1
            say(f"{q.id}: stays draft ({why})")
            continue
        moved += 1
        say(f"{q.id}: -> in_review")
        if not args.dry_run:
            data = store.question_data(q)
            data["status"] = Q_IN_REVIEW
            store.write_question(root, data)
    say(
        f"{moved} moved to in_review, {waiting} still draft"
        + (" (dry run)" if args.dry_run else "")
    )
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
