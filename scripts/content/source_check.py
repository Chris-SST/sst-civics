"""Source check: does the cited official page support the correct answer? (PLAN.md,
Question bank, step 3)

Usage:
  python -m scripts.content.source_check [--ids ...] [--canton zh] [--topic CODE] [--redo]
      [--direct] [--model ...] [--resume BATCH_ID]

Fetches each cited source (httpx, timeout, user agent, 2 MB cap, HTML to text), then asks
the model whether the page text supports the correct answer: supported, not_supported or
unclear, recorded under `checks.source`. `sources[].checked` is set to today only for the
pages that support it. not_supported, and a source that cannot be read (dead link), set
the question to `needs_fix`. Checks draft questions; with --ids any question that is not
retired. Prompt: prompts/content/source_check/vN.md."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from app.content import store
from app.content.fetch import Page, excerpt, fetch_page, gather_limited, new_client
from app.content.schema import QuestionFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_SOURCE, Job, RunOptions, run_jobs
from app.models import Q_APPROVED, Q_DRAFT, Q_IN_REVIEW, Q_NEEDS_FIX
from scripts.content._common import (
    add_ai_args,
    add_selection_args,
    base_parser,
    load,
    main_of,
    options_block,
    root_of,
    run_options,
    say,
    select_questions,
    today_of,
)

PROMPT = "content/source_check"
PAGE_CHARS = 12_000  # per source sent to the model
MAX_SOURCES = 3
VERDICTS = ("supported", "not_supported", "unclear")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "supported_by": {"type": "array", "items": {"type": "integer"}},
        "note": {"type": "string"},
    },
    "required": ["verdict", "supported_by", "note"],
    "additionalProperties": False,
}


def request_text(q: QuestionFile, pages: list[Page]) -> str:
    focus = f"{q.question_de} {q.options_de[q.correct]} {q.explanation_de}"
    lines = [
        f"Frage:\n{q.question_de}",
        f"Antworten:\n{options_block(q.options_de)}",
        f"Als richtig markiert: {q.correct}) {q.options_de[q.correct]}",
        f"Erklärung:\n{q.explanation_de}",
    ]
    for i, page in enumerate(pages, 1):
        note = " (gekürzt)" if page.truncated or len(page.text) > PAGE_CHARS else ""
        lines.append(
            f"Quelle {i}: {page.url}{note}\n<seite>\n{excerpt(page.text, focus, PAGE_CHARS)}\n"
            "</seite>"
        )
    return "\n\n".join(lines)


def _record(
    q: QuestionFile,
    *,
    verdict: str,
    note: str,
    today: date,
    model: str | None,
    supported_urls: set[str],
) -> dict[str, Any]:
    data = store.question_data(q)
    block = dict(data.get("checks") or {})
    block["source"] = {
        "verdict": verdict,
        "note": note[:1000],
        "at": today,
        "model": model,
        "version": q.version,
    }
    data["checks"] = block
    if verdict == "supported":
        for s in data["sources"]:
            if s["url"] in supported_urls:
                s["checked"] = today
    elif verdict in ("not_supported", "dead_link"):
        data["status"] = Q_NEEDS_FIX
    return data


async def check_sources(
    root: Path,
    questions: list[QuestionFile],
    *,
    options: RunOptions,
    today: date,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Fetch, judge and write back. Returns question id -> verdict."""
    urls = sorted({s.url for q in questions for s in q.sources[:MAX_SOURCES]})
    own_client = client is None
    client = client or new_client()
    try:
        fetched = await gather_limited([fetch_page(client, u) for u in urls])
    finally:
        if own_client:
            await client.aclose()
    pages = dict(zip(urls, fetched, strict=True))
    verdicts: dict[str, str] = {}
    jobs: list[Job] = []
    readable: dict[str, list[Page]] = {}
    for q in questions:
        cited = [pages[s.url] for s in q.sources[:MAX_SOURCES]]
        dead = [p for p in cited if not p.ok]
        if dead:
            note = "; ".join(f"{p.url}: {p.error}" for p in dead)
            store.write_question(
                root,
                _record(
                    q, verdict="dead_link", note=note, today=today, model=None, supported_urls=set()
                ),
            )
            verdicts[q.id] = "dead_link"
            say(f"{q.id}: dead link -> needs_fix ({note})")
            continue
        usable = [p for p in cited if p.readable]
        if not usable:
            note = "Keine Quelle hat lesbaren Text (Seite braucht JavaScript oder ist ein PDF)."
            store.write_question(
                root,
                _record(
                    q, verdict="unclear", note=note, today=today, model=None, supported_urls=set()
                ),
            )
            verdicts[q.id] = "unclear"
            say(f"{q.id}: unclear, no readable page text; check by hand")
            continue
        readable[q.id] = usable
        jobs.append(Job(key=q.id, text=request_text(q, usable)))

    if jobs:
        async with SessionLocal() as db:
            outcomes = await run_jobs(
                db,
                purpose=PURPOSE_SOURCE,
                prompt_name=PROMPT,
                schema=SCHEMA,
                jobs=jobs,
                options=options,
                say=say,
            )
        by_id = {q.id: q for q in questions}
        for job in jobs:
            q = by_id[job.key]
            outcome = outcomes.get(job.key)
            verdict = str((outcome.data or {}).get("verdict", "")) if outcome else ""
            if outcome is None or verdict not in VERDICTS:
                say(f"{q.id}: no usable verdict ({outcome.error if outcome else 'missing'})")
                continue
            usable = readable[q.id]
            numbers = [n for n in outcome.data.get("supported_by") or [] if isinstance(n, int)]
            supported_urls = {usable[n - 1].url for n in numbers if 1 <= n <= len(usable)}
            if verdict == "supported" and not supported_urls:
                supported_urls = {p.url for p in usable}
            note = str(outcome.data.get("note", "")).strip()
            store.write_question(
                root,
                _record(
                    q,
                    verdict=verdict,
                    note=note,
                    today=today,
                    model=outcome.model,
                    supported_urls=supported_urls,
                ),
            )
            verdicts[q.id] = verdict
            tail = " -> needs_fix" if verdict == "not_supported" else ""
            say(f"{q.id}: {verdict}{tail}. {note}")
    counts = {v: list(verdicts.values()).count(v) for v in (*VERDICTS, "dead_link")}
    say(", ".join(f"{n} {v}" for v, n in counts.items()))
    return verdicts


def needs_check(q: QuestionFile, redo: bool) -> bool:
    done = q.checks.source if q.checks else None
    return redo or done is None or done.version != q.version


async def run(argv: list[str] | None = None, *, client: httpx.AsyncClient | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=800)
    args = parser.parse_args(argv)
    root = root_of(args)
    cs = load(root)
    statuses = (Q_DRAFT, Q_NEEDS_FIX, Q_IN_REVIEW, Q_APPROVED) if args.ids else (Q_DRAFT,)
    todo = [q for q in select_questions(cs, args, statuses) if needs_check(q, args.redo)]
    if not todo:
        say("No questions waiting for the source check.")
        return 0
    await check_sources(root, todo, options=run_options(args), today=today_of(args), client=client)
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
