"""AI review panel (D-069): three independent reviewers decide whether a question is published.

Usage:
  python -m scripts.content.panel [--ids ...] [--canton zh] [--topic CODE] [--redo]
      [--direct] [--max-requests N]

Chris decided on 2 November 2026 that several independent AI reviews replace the paid human
review. Each question in review (or needing a fix) goes to three reviewers with the same
checklist (prompts/content/panel_review/vN.md) and different focus:

- facts: Claude Opus with the text of the cited official pages;
- exam: Claude Opus without sources, on one clear answer, fair distractors and plain German;
- second: Claude Sonnet with the pages, a second model over the whole checklist.

All three approve: the question becomes `approved` (review note `ai_panel`, and
`translations_missing: true` until every language has a translation). Any `fix` or `reject`:
`needs_fix`, with the blocking issues kept under `checks.panel` for
scripts.content.panel_fix, which rewrites the question for another round. The panel judges
one question version once; --redo judges it again."""

from __future__ import annotations

import asyncio
import dataclasses
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.content import store
from app.content.fetch import Page, excerpt, fetch_page, gather_limited, new_client
from app.content.files import ContentSet
from app.content.schema import QuestionFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_PANEL, Job, Outcome, RunOptions, run_jobs
from app.models import Q_APPROVED, Q_IN_REVIEW, Q_NEEDS_FIX, TRANSLATION_LANGUAGES
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

PROMPT = "content/panel_review"
PAGE_CHARS = 8_000  # per source, as in the source check but shorter: three reviewers read them
MAX_SOURCES = 3

REVIEWERS = (
    (
        "facts",
        "claude-opus-5-5",
        True,
        "Schwerpunkt: Richtigkeit. Prüfe jede Aussage der richtigen Antwort und der Erklärung "
        "am Text der Quellen und an deinem Wissen über den heutigen Stand.",
    ),
    (
        "exam",
        "claude-opus-5-5",
        False,
        "Schwerpunkt: Prüfungsqualität. Löse die Frage zuerst selbst, ohne auf die Markierung "
        "zu schauen. Prüfe dann, ob genau eine Antwort richtig ist, ob die falschen Antworten "
        "fair sind und ob die Sprache klar und einfach ist.",
    ),
    (
        "second",
        "claude-sonnet-5-5",
        True,
        "Schwerpunkt: zweite, unabhängige Meinung über alle Prüfpunkte.",
    ),
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "fix", "reject"]},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "issues"],
    "additionalProperties": False,
}


def facts_of(cs: ContentSet, q: QuestionFile) -> list[str]:
    """The checklist facts the question covers (German and English)."""
    out = []
    for fid in getattr(q, "covers", None) or []:
        for scope in cs.scopes.values():
            fact = next((f for f in scope.facts if f.id == fid), None)
            if fact:
                out.append(f"{fact.fact_de} ({fact.fact_en})")
                break
    return out


def request_text(cs: ContentSet, q: QuestionFile, focus: str, pages: list[Page] | None) -> str:
    facts = facts_of(cs, q)
    lines = [
        focus,
        f"Frage:\n{q.question_de}",
        f"Antworten:\n{options_block(q.options_de)}",
        f"Als richtig markiert: {q.correct}) {q.options_de[q.correct]}",
        f"Erklärung:\n{q.explanation_de}",
        "Tatsache aus der Themenliste:\n" + ("\n".join(f"- {f}" for f in facts) or "- (keine)"),
    ]
    if pages is not None:
        about = f"{q.question_de} {q.options_de[q.correct]} {q.explanation_de}"
        for i, page in enumerate(pages, 1):
            text = (
                excerpt(page.text, about, PAGE_CHARS)
                if page.ok
                else f"(nicht lesbar: {page.error})"
            )
            lines.append(f"Quelle {i}: {page.url}\n<seite>\n{text}\n</seite>")
    return "\n\n".join(lines)


def needs_panel(q: QuestionFile, redo: bool) -> bool:
    done = q.checks.panel if q.checks else None
    return redo or done is None or done.version != q.version


def decide(reviews: list[dict[str, Any]]) -> str:
    verdicts = [r["verdict"] for r in reviews]
    if len(verdicts) < len(REVIEWERS):
        return "fix"  # a reviewer gave no answer: never approve on a partial panel
    if all(v == "approve" for v in verdicts):
        return "approve"
    if verdicts.count("reject") >= 2:
        return "reject"
    return "fix"


def record(
    q: QuestionFile,
    reviews: list[dict[str, Any]],
    *,
    cs: ContentSet,
    today: date,
) -> tuple[dict[str, Any], str]:
    verdict = decide(reviews)
    data = store.question_data(q)
    block = dict(data.get("checks") or {})
    previous = q.checks.panel if q.checks else None
    rnd = (previous.round + 1) if previous and previous.version != q.version else 1
    if previous and previous.version == q.version:
        rnd = previous.round
    block["panel"] = {
        "verdict": verdict,
        "reviews": reviews,
        "round": rnd,
        "at": today,
        "version": q.version,
    }
    data["checks"] = block
    if verdict == "approve":
        data["status"] = Q_APPROVED
        data["review"] = {
            "action": "ai_panel",
            "note": "Approved by the AI review panel",
            "at": today,
        }
        if any((lang, q.id) not in cs.translations for lang in TRANSLATION_LANGUAGES):
            data["translations_missing"] = True
    else:
        data["status"] = Q_NEEDS_FIX
    return data, verdict


async def review(
    root: Path, cs: ContentSet, todo: list[QuestionFile], options: RunOptions, today: date
) -> dict[str, int]:
    urls = sorted({s.url for q in todo for s in q.sources[:MAX_SOURCES]})
    async with new_client() as client:
        fetched = await gather_limited([fetch_page(client, u) for u in urls])
    pages = dict(zip(urls, fetched, strict=True))

    async def one(role: str, model: str, with_sources: bool, focus: str) -> dict[str, Outcome]:
        jobs = [
            Job(
                key=q.id,
                text=request_text(
                    cs,
                    q,
                    focus,
                    [pages[s.url] for s in q.sources[:MAX_SOURCES]] if with_sources else None,
                ),
            )
            for q in todo
        ]
        opts = dataclasses.replace(options, model=model)
        async with SessionLocal() as db:
            out = await run_jobs(
                db,
                purpose=PURPOSE_PANEL,
                prompt_name=PROMPT,
                schema=SCHEMA,
                jobs=jobs,
                options=opts,
                say=lambda m, r=role: say(f"[{r}] {m}"),
            )
            await db.commit()
        return out

    results = await asyncio.gather(*(one(*r) for r in REVIEWERS))
    counts = {"approve": 0, "fix": 0, "reject": 0}
    for q in todo:
        reviews = []
        for (role, _, _, _), outcomes in zip(REVIEWERS, results, strict=True):
            o = outcomes.get(q.id)
            if o is None or not o.data or o.data.get("verdict") not in counts:
                say(f"{q.id}: no usable review from {role} ({o.error if o else 'missing'})")
                continue
            issues = [str(i).strip()[:600] for i in o.data.get("issues") or [] if str(i).strip()]
            reviews.append(
                {"role": role, "model": o.model, "verdict": o.data["verdict"], "issues": issues}
            )
        data, verdict = record(q, reviews, cs=cs, today=today)
        store.write_question(root, data)
        counts[verdict] += 1
        say(f"{q.id}: {verdict} ({', '.join(r['role'] + '=' + r['verdict'] for r in reviews)})")
    return counts


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=16000)
    args = parser.parse_args(argv)
    root = root_of(args)
    cs = load(root)
    todo = [
        q
        for q in select_questions(cs, args, [Q_IN_REVIEW, Q_NEEDS_FIX])
        if needs_panel(q, args.redo)
    ]
    if not todo:
        say("No questions waiting for the review panel.")
        return 0
    options = run_options(args)
    if options.effort == "medium":
        options = dataclasses.replace(options, effort="high")
    say(f"Panel: {len(todo)} questions x {len(REVIEWERS)} reviewers")
    counts = await review(root, cs, todo, options, today_of(args))
    say(f"{counts['approve']} approved, {counts['fix']} to fix, {counts['reject']} rejected")
    return 0


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
