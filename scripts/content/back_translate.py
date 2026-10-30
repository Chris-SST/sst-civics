"""Back-translation check of draft translations (PLAN.md, Languages, translation pipeline
step 3).

Usage:
  python -m scripts.content.back_translate --lang en [--ids ...] [--redo]
      [--direct] [--model ...] [--resume BATCH_ID] [--resume-compare BATCH_ID]

First call: the draft translation is translated back into German without seeing the
original (prompts/content/back_translate/vN.md). Second call: the original German and the
back-translation are compared and judged `same` or `different` with a one-line reason
(prompts/content/compare/vN.md). The result is stored under `checks.back_translation`;
`different` sets the translation to `status: flagged` for the reviewer. Stale drafts (made
from an older German version) are left for scripts.content.translate to refresh."""

from __future__ import annotations

import sys
from typing import Any

from app.content import store
from app.content.schema import QuestionFile, TranslationFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_BACK, PURPOSE_COMPARE, Job, run_jobs
from app.models import OPTION_KEYS, T_DRAFT, T_FLAGGED, TRANSLATION_LANGUAGES
from scripts.content._common import (
    add_ai_args,
    base_parser,
    load,
    main_of,
    options_block,
    root_of,
    run_options,
    say,
    swiss_german,
    today_of,
)

PROMPT_BACK = "content/back_translate"
PROMPT_COMPARE = "content/compare"

_OPTIONS = {
    "type": "object",
    "properties": {k: {"type": "string"} for k in OPTION_KEYS},
    "required": list(OPTION_KEYS),
    "additionalProperties": False,
}
BACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question_de": {"type": "string"},
        "options_de": _OPTIONS,
        "explanation_de": {"type": "string"},
    },
    "required": ["question_de", "options_de", "explanation_de"],
    "additionalProperties": False,
}
COMPARE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["same", "different"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


def back_text(tr: TranslationFile) -> str:
    return (
        f"Sprache: {tr.lang}\n\nFrage:\n{tr.question}\n\nAntworten:\n"
        f"{options_block(tr.options)}\n\nErklärung:\n{tr.explanation}"
    )


def compare_text(q: QuestionFile, back: dict[str, Any]) -> str:
    return (
        "Deutsche Fassung:\n"
        f"Frage: {q.question_de}\nAntworten:\n{options_block(q.options_de)}\n"
        f"Erklärung: {q.explanation_de}\n\n"
        "Rückübersetzung:\n"
        f"Frage: {back['question_de']}\nAntworten:\n{options_block(back['options_de'])}\n"
        f"Erklärung: {back['explanation_de']}"
    )


def check_back(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        return {
            "question_de": swiss_german(str(data["question_de"]).strip()),
            "options_de": {
                k: swiss_german(str(data["options_de"][k]).strip()) for k in OPTION_KEYS
            },
            "explanation_de": swiss_german(str(data["explanation_de"]).strip()),
        }
    except (KeyError, TypeError):
        return None


def needs_check(tr: TranslationFile, q: QuestionFile, redo: bool) -> bool:
    if tr.status != T_DRAFT or tr.source_version != q.version:
        return False
    done = tr.checks.back_translation if tr.checks else None
    return redo or done is None or done.source_version != tr.source_version


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument(
        "--lang", required=True, help=f"one of {', '.join(TRANSLATION_LANGUAGES)} or all"
    )
    parser.add_argument("--ids", nargs="+", default=None)
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--resume-compare", metavar="BATCH_ID", default=None)
    add_ai_args(parser, max_tokens=3000)
    args = parser.parse_args(argv)
    langs = list(TRANSLATION_LANGUAGES) if args.lang == "all" else [args.lang]
    if any(lang not in TRANSLATION_LANGUAGES for lang in langs):
        parser.error(f"--lang is one of {', '.join(TRANSLATION_LANGUAGES)} or all")
    root = root_of(args)
    today = today_of(args)
    cs = load(root)
    ids = set(args.ids) if args.ids else None
    todo: list[tuple[TranslationFile, QuestionFile]] = []
    for (lang, qid), tr in sorted(cs.translations.items()):
        q = cs.questions.get(qid)
        if lang not in langs or q is None or (ids is not None and qid not in ids):
            continue
        if needs_check(tr, q, args.redo):
            todo.append((tr, q))
    if not todo:
        say("No draft translations waiting for the back-translation check.")
        return 0

    back_options = run_options(args)
    compare_options = run_options(args)
    compare_options.resume_batch = args.resume_compare
    compare_options.max_tokens = 400
    async with SessionLocal() as db:
        backs = await run_jobs(
            db,
            purpose=PURPOSE_BACK,
            prompt_name=PROMPT_BACK,
            schema=BACK_SCHEMA,
            jobs=[Job(key=f"{tr.lang}/{tr.id}", text=back_text(tr)) for tr, _ in todo],
            options=back_options,
            say=say,
        )
        back_texts: dict[str, dict[str, Any]] = {}
        jobs = []
        for tr, q in todo:
            key = f"{tr.lang}/{tr.id}"
            outcome = backs.get(key)
            back = check_back(outcome.data if outcome else None)
            if back is None:
                say(f"{key}: no usable back-translation")
                continue
            back_texts[key] = back
            jobs.append(Job(key=key, text=compare_text(q, back)))
        verdicts = await run_jobs(
            db,
            purpose=PURPOSE_COMPARE,
            prompt_name=PROMPT_COMPARE,
            schema=COMPARE_SCHEMA,
            jobs=jobs,
            options=compare_options,
            say=say,
        )
    same = different = failed = 0
    for tr, _q in todo:
        key = f"{tr.lang}/{tr.id}"
        outcome = verdicts.get(key)
        verdict = str((outcome.data or {}).get("verdict", "")) if outcome else ""
        if key not in back_texts or outcome is None or verdict not in ("same", "different"):
            failed += 1
            continue
        data = store.translation_data(tr)
        block = dict(data.get("checks") or {})
        block["back_translation"] = {
            "verdict": verdict,
            "reason": swiss_german(str(outcome.data.get("reason", "")).strip())[:500],
            "model": outcome.model,
            "at": today,
            "source_version": tr.source_version,
            **back_texts[key],
        }
        data["checks"] = block
        if verdict == "different":
            data["status"] = T_FLAGGED
            different += 1
            say(f"{key}: DIFFERENT -> flagged ({block['back_translation']['reason']})")
        else:
            same += 1
            say(f"{key}: same meaning")
        store.write_translation(root, data)
    say(f"{same} same, {different} flagged, {failed} without a result")
    return 0 if not failed else 1


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
