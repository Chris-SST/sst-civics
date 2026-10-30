"""Write admin review actions back to the question files (D-046, task 1.5). This is the only
path that changes content files from the database.

Usage:
  python -m scripts.content.sync_reviews [--root content] [--dry-run]

For every question with `file_sync_pending`, the entries of `pending_changes` are applied
to content/questions/<scope>/<id>.yaml in order:

- approve: `status: approved`; edits made while approving are applied and the version is
  raised by one (once per run);
- send_back: `status: needs_fix`, the reviewer's note under `review.note`;
- retire: `status: retired`;
- learner_reports: `status: in_review` (two open learner reports);
- broken_links (weekly link check): the URLs under `checks.links` and a review note; the
  status is left alone, the source check decides.

Then the pending flags are cleared and the database row takes the file's status, version
and content hash, so the next import finds them equal. A file whose version differs from the
database (changed by hand since the last import) is skipped: import first, then review
again. Commit the changed files afterwards; the import on deploy reads them."""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from app.content import store
from app.content.files import question_content_hash
from app.content.schema import QuestionFile
from app.db import SessionLocal
from app.models import OPTION_KEYS, Q_APPROVED, Q_IN_REVIEW, Q_NEEDS_FIX, Q_RETIRED, Question
from scripts.content._common import base_parser, load, main_of, root_of, say, today_of

STATUS_OF = {
    "approve": Q_APPROVED,
    "send_back": Q_NEEDS_FIX,
    "retire": Q_RETIRED,
    "learner_reports": Q_IN_REVIEW,
}
EDIT_FIELDS = {
    "question_de": "question_de",
    "options_de": "options_de",
    "correct": "correct",
    "explanation_de": "explanation_de",
    "difficulty": "difficulty",
    "topic_code": "topic",
}


def _day(value: Any, fallback: date) -> date:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return fallback
    return fallback


def apply_changes(
    q: QuestionFile, changes: list[dict[str, Any]], today: date
) -> tuple[dict[str, Any], list[str]]:
    """The file's new content and a line per change applied."""
    data = store.question_data(q)
    log: list[str] = []
    edited = False
    for change in changes:
        action = change.get("action")
        at = _day(change.get("at"), today)
        note = (change.get("note") or "").strip() or None
        if action in STATUS_OF:
            data["status"] = STATUS_OF[action]
            if action == "learner_reports":
                note = note or "Two open learner reports."
            data["review"] = {"action": action, "note": note, "at": at}
            log.append(f"{action} -> {data['status']}" + (f" ({note})" if note else ""))
            for name, value in (change.get("edits") or {}).items():
                field = EDIT_FIELDS.get(name)
                if field is None:
                    continue
                if field == "options_de":
                    value = {k: str(value[k]).strip() for k in OPTION_KEYS}
                if data.get(field) != value:
                    data[field] = value
                    edited = True
                    log.append(f"edit {field}")
        elif action == "broken_links":
            urls = [str(u) for u in change.get("urls") or []]
            block = dict(data.get("checks") or {})
            block["links"] = {"broken": urls, "at": at}
            data["checks"] = block
            data["review"] = {
                "action": action,
                "note": "Source link(s) not reachable: " + ", ".join(urls),
                "at": at,
            }
            log.append(f"broken links recorded ({len(urls)})")
        else:
            log.append(f"unknown action {action!r} left out")
    if edited:
        data["version"] = q.version + 1
        log.append(f"version {q.version} -> {q.version + 1}")
    return data, log


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print, change nothing")
    args = parser.parse_args(argv)
    root = root_of(args)
    today = today_of(args)
    cs = load(root)
    written = skipped = 0
    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(Question)
                    .where(Question.file_sync_pending.is_(True))
                    .order_by(Question.id)
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            say("No review actions waiting for write-back.")
            return 0
        for row in rows:
            q = cs.questions.get(row.id)
            if q is None:
                skipped += 1
                say(f"{row.id}: no file under questions/; skipped")
                continue
            if q.version != row.version:
                skipped += 1
                say(
                    f"{row.id}: the file is at version {q.version}, the database at "
                    f"{row.version}; import the files first, then review again. Skipped."
                )
                continue
            data, log = apply_changes(q, list(row.pending_changes or []), today)
            say(f"{row.id}: " + "; ".join(log or ["nothing to write"]))
            if args.dry_run:
                continue
            try:
                new = store.write_question(root, data)
            except ValueError as exc:
                skipped += 1
                say(f"{row.id}: the result does not fit the schema, skipped ({exc})")
                continue
            row.file_sync_pending = False
            row.pending_changes = None
            row.status = row.file_status = new.status
            row.version = new.version
            row.content_hash = question_content_hash(new)
            await db.commit()  # one question at a time: a failure later keeps this one
            written += 1
    say(f"{written} file(s) written, {skipped} skipped" + (" (dry run)" if args.dry_run else ""))
    return 0 if not skipped else 1


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
