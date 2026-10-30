"""Translate approved German questions (PLAN.md, Languages, translation pipeline steps 1, 2
and 5).

Usage:
  python -m scripts.content.translate --lang en [--ids ...] [--canton zh] [--topic CODE]
      [--redo] [--direct] [--model ...] [--resume BATCH_ID]

Only questions with `status: approved` are translated, and only where there is no
translation yet or the existing one is stale (made from an older German version); a
current draft is replaced only with --redo. A translation with status approved or
in_review is never touched, stale or not: it is printed and skipped (set it back to draft
by hand to have it refreshed). The glossary content/glossary/<lang>.yaml is sent with every
question whose text uses one of its terms. Results are written to
content/translations/<lang>/<id>.yaml with `status: draft` and `source_version` set to the
German version. Prompt: prompts/content/translate/vN.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from app.content import store
from app.content.files import ContentSet
from app.content.schema import GlossaryEntry, QuestionFile
from app.db import SessionLocal
from app.llm.content import PURPOSE_TRANSLATE, Job, run_jobs
from app.models import (
    OPTION_KEYS,
    Q_APPROVED,
    T_APPROVED,
    T_DRAFT,
    T_IN_REVIEW,
    TRANSLATION_LANGUAGES,
)
from app.questions import checks
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
)

PROMPT = "content/translate"

LANGUAGE_NAMES = {
    "en": "Englisch (britische Schreibweise)",
    "fr": "Französisch",
    "it": "Italienisch",
    "pt": "Portugiesisch",
    "es": "Spanisch",
    "sq": "Albanisch",
    "tr": "Türkisch",
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "options": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in OPTION_KEYS},
            "required": list(OPTION_KEYS),
            "additionalProperties": False,
        },
        "explanation": {"type": "string"},
    },
    "required": ["question", "options", "explanation"],
    "additionalProperties": False,
}


def term_pattern(term: str) -> re.Pattern[str]:
    """A word starting with the term ("Bundesrates", "Bundesratswahl" for "Bundesrat");
    abbreviations such as AHV or IV only as whole words, in capitals."""
    if term.isupper():
        return re.compile(rf"\b{re.escape(term)}\b")
    return re.compile(rf"\b{re.escape(term)}", re.IGNORECASE)


def glossary_for(q: QuestionFile, entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
    """Entries whose German term occurs in the question, its options or explanation, or
    that the question lists in `glossary`."""
    text = " ".join([q.question_de, *q.options_de.values(), q.explanation_de])
    listed = {t.casefold() for t in q.glossary}
    return [
        e for e in entries if e.term_de.casefold() in listed or term_pattern(e.term_de).search(text)
    ]


def status_on_disk(root: Path, lang: str, qid: str) -> str | None:
    path = store.translation_path(root, lang, qid)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return str(data.get("status")) if isinstance(data, dict) else None


def request_text(q: QuestionFile, lang: str, terms: list[GlossaryEntry]) -> str:
    lines = [f"Zielsprache: {LANGUAGE_NAMES.get(lang, lang)} ({lang})"]
    if terms:
        lines.append("Glossar (genau so übersetzen):")
        for e in terms:
            keep = "; deutschen Begriff beibehalten" if e.keep_german else ""
            lines.append(f"- {e.term_de} = {e.translation}{keep}")
    lines += [
        f"Frage:\n{q.question_de}",
        f"Antworten:\n{options_block(q.options_de)}",
        f"Erklärung:\n{q.explanation_de}",
    ]
    return "\n\n".join(lines)


def plan(
    cs: ContentSet, questions: list[QuestionFile], lang: str, redo: bool
) -> list[QuestionFile]:
    """The questions to translate into `lang`, printing why the others are skipped."""
    todo = []
    for q in questions:
        tr = cs.translations.get((lang, q.id))
        if tr is None:
            todo.append(q)
            continue
        stale = tr.source_version < q.version
        if tr.status in (T_APPROVED, T_IN_REVIEW):
            extra = f", stale (from version {tr.source_version})" if stale else ""
            say(f"{lang}/{q.id}: {tr.status}{extra}; never overwritten, skipped")
            continue
        if stale or redo:
            todo.append(q)
        else:
            say(f"{lang}/{q.id}: a current {tr.status} translation exists; --redo to replace")
    return todo


def check_reply(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        options = {k: str(data["options"][k]).strip() for k in OPTION_KEYS}
        question = str(data["question"]).strip()
        explanation = str(data["explanation"]).strip()
    except (KeyError, TypeError):
        return None
    if not question or not explanation or not checks.options_valid(options, "a"):
        return None
    return {"question": question, "options": options, "explanation": explanation}


async def translate_language(
    cs: ContentSet, args: Any, lang: str, questions: list[QuestionFile]
) -> tuple[int, int]:
    root = cs.root
    todo = plan(cs, questions, lang, args.redo)
    if not todo:
        say(f"{lang}: nothing to translate")
        return 0, 0
    gl = cs.glossary.get(lang)
    entries = gl.terms if gl else []
    if not entries:
        say(f"{lang}: WARNING no glossary at glossary/{lang}.yaml")
    terms = {q.id: glossary_for(q, entries) for q in todo}
    jobs = [Job(key=q.id, text=request_text(q, lang, terms[q.id])) for q in todo]
    async with SessionLocal() as db:
        outcomes = await run_jobs(
            db,
            purpose=PURPOSE_TRANSLATE,
            prompt_name=PROMPT,
            schema=SCHEMA,
            jobs=jobs,
            options=run_options(args),
            say=say,
        )
    written = failed = 0
    for q in todo:
        outcome = outcomes.get(q.id)
        reply = check_reply(outcome.data if outcome else None)
        if reply is None:
            failed += 1
            say(f"{lang}/{q.id}: no usable translation ({outcome.error if outcome else 'missing'})")
            continue
        if status_on_disk(root, lang, q.id) in (T_APPROVED, T_IN_REVIEW):
            say(f"{lang}/{q.id}: reviewed while this run was waiting; not overwritten")
            continue
        store.write_translation(
            root,
            {
                "id": q.id,
                "lang": lang,
                "source_version": q.version,
                **reply,
                "status": T_DRAFT,
                "reviewed_by": None,
                "reviewed_at": None,
            },
        )
        written += 1
        out = " ".join([reply["question"], *reply["options"].values(), reply["explanation"]])
        missing = [e.term_de for e in terms[q.id] if e.translation.casefold() not in out.casefold()]
        note = f" (glossary term not used as given: {', '.join(missing)})" if missing else ""
        say(f"wrote translations/{lang}/{q.id}.yaml{note}")
    return written, failed


async def run(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument(
        "--lang", required=True, help=f"one of {', '.join(TRANSLATION_LANGUAGES)} or all"
    )
    add_selection_args(parser)
    add_ai_args(parser, max_tokens=3000)
    args = parser.parse_args(argv)
    langs = list(TRANSLATION_LANGUAGES) if args.lang == "all" else [args.lang]
    if any(lang not in TRANSLATION_LANGUAGES for lang in langs):
        parser.error(f"--lang is one of {', '.join(TRANSLATION_LANGUAGES)} or all")
    cs = load(root_of(args))
    approved = select_questions(cs, args, [Q_APPROVED])
    if args.ids:
        for q in select_questions(cs, args, None):
            if q.status != Q_APPROVED:
                say(f"{q.id}: status {q.status}; only approved questions are translated")
    total_failed = 0
    for lang in langs:
        written, failed = await translate_language(cs, args, lang, approved)
        total_failed += failed
        say(f"{lang}: {written} translation(s) written, {failed} failed")
    return 0 if not total_failed else 1


main = main_of(run)

if __name__ == "__main__":
    sys.exit(main())
