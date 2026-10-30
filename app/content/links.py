"""Weekly link check of the sources cited by the question files (task 1.5). HEAD or GET
only, no AI. Run by the worker job `check_source_links` and by
`python -m scripts.content.check_links`.

A question with a source that does not answer is flagged for review in the database:
`file_sync_pending` is set and a `broken_links` entry is added to `pending_changes`, which
`scripts.content.sync_reviews` writes to the file. The question stays served (a moved page
does not make the answer wrong); the source check decides that. A report is written to
content/reports/link-check-<date>.md, or to var/reports/ where the content directory is
read-only (the containers)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.fetch import Page, check_link, gather_limited, new_client
from app.content.files import content_root, load_content
from app.db import utcnow
from app.models import Q_RETIRED, Question

log = logging.getLogger(__name__)

ACTION = "broken_links"


@dataclass
class LinkReport:
    day: date
    checked_urls: int = 0
    broken: dict[str, str] = field(default_factory=dict)  # url -> error
    questions: dict[str, list[str]] = field(default_factory=dict)  # id -> broken urls
    flagged: list[str] = field(default_factory=list)  # ids newly flagged in the database
    report_path: Path | None = None

    def markdown(self) -> str:
        lines = [
            f"# Link check {self.day.isoformat()}",
            "",
            f"{self.checked_urls} source URL(s) checked, {len(self.broken)} not reachable, "
            f"{len(self.questions)} question(s) affected.",
            "",
        ]
        if self.broken:
            lines += ["| URL | Error | Questions |", "| --- | --- | --- |"]
            for url, error in sorted(self.broken.items()):
                ids = sorted(q for q, urls in self.questions.items() if url in urls)
                lines.append(f"| {url} | {error} | {', '.join(ids)} |")
            lines += [
                "",
                "Next: `python -m scripts.content.sync_reviews` writes the flags to the files; "
                "fix or replace the sources, then run `python -m scripts.content.source_check "
                "--ids ...`.",
            ]
        return "\n".join(lines) + "\n"


def _write_report(report: LinkReport, root: Path) -> Path | None:
    name = f"link-check-{report.day.isoformat()}.md"
    fallback = Path.cwd() / "var" / "reports"
    for directory in (root / "reports", fallback):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / name
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(report.markdown())
            return path
        except OSError:
            continue
    log.warning("Link check report could not be written")
    return None


async def run_link_check(
    db: AsyncSession | None,
    root: Path | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
    write_report: bool = True,
) -> LinkReport:
    root = (root or content_root()).resolve()
    report = LinkReport(day=today or date.today())
    cs = load_content(root)
    cited: dict[str, list[str]] = {}
    for q in cs.questions.values():
        if q.status == Q_RETIRED:
            continue
        cited[q.id] = list(dict.fromkeys(s.url for s in q.sources))
    urls = sorted({u for us in cited.values() for u in us})
    report.checked_urls = len(urls)
    own_client = client is None
    client = client or new_client()
    try:
        results: list[Page] = await gather_limited([check_link(client, u) for u in urls])
    finally:
        if own_client:
            await client.aclose()
    report.broken = {p.url: p.error or "error" for p in results if not p.ok}
    for qid, us in cited.items():
        bad = [u for u in us if u in report.broken]
        if bad:
            report.questions[qid] = bad

    if db is not None and report.questions:
        for qid, bad in sorted(report.questions.items()):
            row = await db.get(Question, qid)
            if row is None:
                continue
            pending = list(row.pending_changes or [])
            last = next((c for c in reversed(pending) if c.get("action") == ACTION), None)
            if row.file_sync_pending and last is not None and last.get("urls") == bad:
                continue  # already flagged with the same links
            pending.append(
                {
                    "action": ACTION,
                    "urls": bad,
                    "errors": {u: report.broken[u] for u in bad},
                    "status": row.status,
                    "at": utcnow().isoformat(),
                }
            )
            row.pending_changes = pending
            row.file_sync_pending = True
            report.flagged.append(qid)
        await db.commit()
    if write_report:
        report.report_path = _write_report(report, root)
    log.info(
        "Link check: %d URL(s), %d broken, %d question(s) flagged",
        report.checked_urls,
        len(report.broken),
        len(report.flagged),
    )
    return report
