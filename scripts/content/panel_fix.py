"""Rewrite questions the AI review panel sent back (D-069).

Usage:
  python -m scripts.content.panel_fix [--ids ...] [--max-rounds 2] [--direct]

Takes questions in `needs_fix` whose panel verdict for the current version is `fix`, gives
Claude Opus the question, the checklist fact and the reviewers' blocking issues
(prompts/content/panel_fix/vN.md), and writes the revised question as a new version in
`draft`, so it goes through the independent answer, the source check, promote and the panel
again. A question the fixer judges beyond repair, or one whose panel verdict is `reject`, is
retired with a review note. After `--max-rounds` panel rounds a question stays in
`needs_fix` for a person."""

from __future__ import annotations

import dataclasses
import sys
from typing import Any

from app.content import store
from app.content.files import ContentSet
from app.content.schema import QuestionFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_PANEL_FIX, Job, run_jobs
from app.models import OPTION_KEYS, Q_DRAFT, Q_NEEDS_FIX, Q_RETIRED
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
    swiss_german,
    today_of,
)
from scripts.content.panel import facts_of

PROMPT = "content/panel_fix"
FIX_MODEL = "claude-opus-5-5"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "retire": {"type": "boolean"},
        "question_de": {"type": "string"},
        "options_de": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in OPTION_KEYS},
            "required": list(OPTION_KEYS),
            "additionalProperties": False,
        },
        "correct": {"type": "string", "enum": list(OPTION_KEYS)},
        "explanation_de": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["retire", "question_de", "options_de", "correct", "explanation_de", "note"],
    "additionalProperties": False,
}


def blocking_issues(q: QuestionFile) -> list[str]:
    panel = q.checks.panel if q.checks else None
    if panel is None:
        return []
    return [
        f"{r.role}: {i}"
        for r in panel.reviews
        if r.verdict != "approve"
        for i in r.issues
        if not i.lower().startswith("klein:")
    ]


def request_text(cs: ContentSet, q: QuestionFile) -> str:
    facts = facts_of(cs, q)
    issues = blocking_issues(q) or ["(keine einzelnen Punkte genannt; prüfe die Frage als Ganzes)"]
    return "\n\n".join(
        [
            f"Frage:\n{q.question_de}",
            f"Antworten:\n{options_block(q.options_de)}",
            f"Als richtig markiert: {q.correct}",
            f"Erklärung:\n{q.explanation_de}",
            "Tatsache aus der Themenliste:\n" + ("\n".join(f"- {f}" for f in facts) or "- (keine)"),
            "Beanstandungen:\n" + "\n".join(f"- {i}" for i in issues),
        ]
    )


def waiting(q: QuestionFile, max_rounds: int) -> bool:
    panel = q.checks.panel if q.checks else None
    return (
        panel is not None
        and panel.version == q.version
        and panel.verdict in ("fix", "reject")
        and panel.round < max_rounds
    )


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=16000)
    parser.add_argument("--max-rounds", type=int, default=2)
    args = parser.parse_args(argv)
    root = root_of(args)
    today = today_of(args)
    cs = load(root)
    todo = [q for q in select_questions(cs, args, [Q_NEEDS_FIX]) if waiting(q, args.max_rounds)]
    if not todo:
        say("No questions waiting for a rewrite.")
        return 0
    rejected = [q for q in todo if q.checks.panel.verdict == "reject"]
    for q in rejected:
        data = store.question_data(q)
        data["status"] = Q_RETIRED
        data["review"] = {
            "action": "ai_panel",
            "note": "Retired: rejected by the AI review panel",
            "at": today,
        }
        store.write_question(root, data)
        say(f"{q.id}: rejected by the panel -> retired")
    todo = [q for q in todo if q not in rejected]
    options = dataclasses.replace(run_options(args), model=args.model or FIX_MODEL, effort="high")
    async with SessionLocal() as db:
        outcomes = await run_jobs(
            db,
            purpose=PURPOSE_PANEL_FIX,
            prompt_name=PROMPT,
            schema=SCHEMA,
            jobs=[Job(key=q.id, text=request_text(cs, q)) for q in todo],
            options=options,
            say=say,
        )
        await db.commit()
    fixed = retired = failed = 0
    for q in todo:
        o = outcomes.get(q.id)
        d = (o.data if o else None) or {}
        if not d or d.get("correct") not in OPTION_KEYS:
            failed += 1
            say(f"{q.id}: no usable rewrite ({o.error if o else 'missing'})")
            continue
        data = store.question_data(q)
        note = swiss_german(str(d.get("note", "")).strip())[:600] or None
        if d.get("retire"):
            data["status"] = Q_RETIRED
            data["review"] = {
                "action": "ai_panel",
                "note": f"Retired by the panel fixer: {note}",
                "at": today,
            }
            retired += 1
            say(f"{q.id}: retired ({note})")
        else:
            data["question_de"] = swiss_german(str(d["question_de"]).strip())
            data["options_de"] = {
                k: swiss_german(str(d["options_de"][k]).strip()) for k in OPTION_KEYS
            }
            data["correct"] = d["correct"]
            data["explanation_de"] = swiss_german(str(d["explanation_de"]).strip())
            data["version"] = q.version + 1
            data["status"] = Q_DRAFT
            data.pop("translations_missing", None)
            checks = dict(data.get("checks") or {})
            checks.pop("independent_answer", None)
            checks.pop("source", None)
            data["checks"] = checks  # the panel block stays, so the next round is counted
            if note:
                data["review"] = {"action": "ai_panel", "note": f"Rewritten: {note}", "at": today}
            fixed += 1
            say(f"{q.id}: rewritten as version {q.version + 1}")
        store.write_question(root, data)
    say(f"{fixed} rewritten, {retired + len(rejected)} retired, {failed} failed")
    return 0 if not failed else 1


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
