"""Independent answer pass for draft questions (PLAN.md, Question bank, step 2).

Usage:
  python -m scripts.content.answer [--ids ...] [--canton zh] [--topic CODE] [--redo]
      [--direct] [--model ...] [--resume BATCH_ID]

A second call sees the question and its four options, never the key or the explanation,
and names the option it believes correct with one sentence of reasoning. The result goes
under `checks.independent_answer`; when it disagrees with the key the question is set to
`needs_fix` and the reasoning is kept for the reviewer. Prompt: prompts/content/answer/vN.md."""

from __future__ import annotations

import sys
from typing import Any

from app.content import store
from app.content.schema import QuestionFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_ANSWER, Job, run_jobs
from app.models import OPTION_KEYS, Q_DRAFT, Q_NEEDS_FIX
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

PROMPT = "content/answer"

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "option": {"type": "string", "enum": list(OPTION_KEYS)},
        "reasoning": {"type": "string"},
    },
    "required": ["option", "reasoning"],
    "additionalProperties": False,
}


def request_text(q: QuestionFile) -> str:
    """Question and options only: no key, no explanation, no sources."""
    return f"Frage:\n{q.question_de}\n\nAntworten:\n{options_block(q.options_de)}"


def needs_answer(q: QuestionFile, redo: bool) -> bool:
    done = q.checks.independent_answer if q.checks else None
    return redo or done is None or done.version != q.version


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=600)
    args = parser.parse_args(argv)
    root = root_of(args)
    today = today_of(args)
    cs = load(root)
    todo = [q for q in select_questions(cs, args, [Q_DRAFT]) if needs_answer(q, args.redo)]
    if not todo:
        say("No draft questions waiting for the independent answer.")
        return 0
    jobs = [Job(key=q.id, text=request_text(q)) for q in todo]
    async with SessionLocal() as db:
        outcomes = await run_jobs(
            db,
            purpose=PURPOSE_ANSWER,
            prompt_name=PROMPT,
            schema=SCHEMA,
            jobs=jobs,
            options=run_options(args),
            say=say,
        )
    agreed = disagreed = failed = 0
    for q in todo:
        outcome = outcomes.get(q.id)
        option = str((outcome.data or {}).get("option", "")).strip().lower() if outcome else ""
        if outcome is None or option not in OPTION_KEYS:
            failed += 1
            say(f"{q.id}: no usable answer ({outcome.error if outcome else 'missing'})")
            continue
        agrees = option == q.correct
        data = store.question_data(q)
        checks_block = dict(data.get("checks") or {})
        checks_block["independent_answer"] = {
            "option": option,
            "agrees": agrees,
            "model": outcome.model,
            "at": today,
            "version": q.version,
            "reasoning": str(outcome.data.get("reasoning", "")).strip()[:1000] or None,
        }
        data["checks"] = checks_block
        if agrees:
            agreed += 1
            say(f"{q.id}: agrees ({option})")
        else:
            data["status"] = Q_NEEDS_FIX
            disagreed += 1
            say(f"{q.id}: DISAGREES, answered {option}, key is {q.correct} -> needs_fix")
        store.write_question(root, data)
    say(f"{agreed} agree, {disagreed} disagree (needs_fix), {failed} without an answer")
    return 0 if not failed else 1


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
