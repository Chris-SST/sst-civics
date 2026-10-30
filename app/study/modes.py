"""The four study modes as a rendering contract (PLAN.md, Languages).

- own: `translation` and `german`; the page shows the translation first, the German small.
- side: `translation` and `german`; both with equal weight.
- help: `german` and `terms` (glossary terms in the question, with translation and note).
- de: `german` only, exactly as in the test.

`mode` is the mode actually rendered. When the learner's study language has no approved,
current translation of the question, `own` and `side` fall back to `de` with `fallback: true`.
A learner studying in German always gets `de`. With `reveal`, each block also carries the
explanation and the response the correct option key (Learn cards, answers in Practise)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CONTENT_MASTER_LANGUAGE,
    MODE_DE,
    MODE_HELP,
    MODE_OWN,
    MODE_SIDE,
    OPTION_KEYS,
    Q_APPROVED,
    STUDY_MODES,
    T_APPROVED,
    GlossaryTerm,
    Question,
    QuestionTranslation,
)

NEXT_MODE = {MODE_OWN: MODE_SIDE, MODE_SIDE: MODE_HELP, MODE_HELP: MODE_DE, MODE_DE: MODE_DE}
PREVIOUS_MODE = {MODE_OWN: MODE_OWN, MODE_SIDE: MODE_OWN, MODE_HELP: MODE_SIDE, MODE_DE: MODE_HELP}
TRANSLATED_MODES = (MODE_OWN, MODE_SIDE)


def mode_index(mode: str) -> int:
    return STUDY_MODES.index(mode)


def later_mode(a: str, b: str) -> str:
    return a if mode_index(a) >= mode_index(b) else b


def translation_usable(q: Question, tr: QuestionTranslation | None) -> bool:
    """Approved and made from the German version now served (not stale, not hidden)."""
    return (
        tr is not None
        and tr.status == T_APPROVED
        and not tr.hidden
        and tr.source_version >= q.version
    )


def effective_mode(requested: str, study_language: str, has_translation: bool) -> tuple[str, bool]:
    """(mode rendered, fallback flag)."""
    if study_language == CONTENT_MASTER_LANGUAGE:
        return MODE_DE, False
    if requested in TRANSLATED_MODES and not has_translation:
        return MODE_DE, True
    return requested, False


async def translations_for(
    db: AsyncSession, question_ids: list[str], lang: str
) -> dict[str, QuestionTranslation]:
    if lang == CONTENT_MASTER_LANGUAGE or not question_ids:
        return {}
    rows = (
        await db.execute(
            select(QuestionTranslation).where(
                QuestionTranslation.question_id.in_(question_ids),
                QuestionTranslation.lang == lang,
            )
        )
    ).scalars()
    return {tr.question_id: tr for tr in rows}


async def glossary_for(db: AsyncSession, lang: str) -> list[GlossaryTerm]:
    if lang == CONTENT_MASTER_LANGUAGE:
        return []
    return list(
        (await db.execute(select(GlossaryTerm).where(GlossaryTerm.lang == lang))).scalars().all()
    )


def _term_position(term: str, text: str) -> int | None:
    m = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE)
    return m.start() if m else None


def terms_in(q: Question, glossary: list[GlossaryTerm]) -> list[dict[str, Any]]:
    """Glossary terms that occur in the German question or its options (whole words), and the
    terms the question file links, in order of first appearance; linked terms that do not
    occur in the text come last."""
    text = "\n".join([q.question_de, *(q.options_de.get(k, "") for k in OPTION_KEYS)])
    linked = {t.lower() for t in (q.glossary or [])}
    found: list[tuple[int, str, GlossaryTerm]] = []
    for g in glossary:
        pos = _term_position(g.term, text)
        if pos is None and g.term.lower() not in linked:
            continue
        found.append((pos if pos is not None else len(text) + 1, g.term.lower(), g))
    found.sort(key=lambda x: (x[0], x[1]))
    return [
        {
            "term": g.term,
            "translation": g.translation,
            "note": g.note,
            "in_text": pos <= len(text),
        }
        for pos, _, g in found
    ]


def _options(options: dict[str, str]) -> list[dict[str, str]]:
    return [{"key": k, "text": options.get(k, "")} for k in OPTION_KEYS]


def explanation_for(q: Question, tr: QuestionTranslation | None, lang: str) -> dict[str, str]:
    """The explanation in the learner's language when a usable translation exists, else German."""
    if translation_usable(q, tr):
        assert tr is not None
        return {"lang": lang, "text": tr.explanation}
    return {"lang": CONTENT_MASTER_LANGUAGE, "text": q.explanation_de}


def render(
    q: Question,
    *,
    mode: str,
    study_language: str,
    translation: QuestionTranslation | None,
    glossary: list[GlossaryTerm],
    topic_name: str | None = None,
    reveal: bool = False,
) -> dict[str, Any]:
    if mode not in STUDY_MODES:
        mode = MODE_OWN
    usable = translation_usable(q, translation)
    shown, fallback = effective_mode(mode, study_language, usable)
    german: dict[str, Any] = {
        "lang": CONTENT_MASTER_LANGUAGE,
        "question": q.question_de,
        "options": _options(q.options_de),
    }
    out: dict[str, Any] = {
        "id": q.id,
        "version": q.version,
        "topic_code": q.topic_code,
        "topic_name": topic_name or q.topic_code,
        "difficulty": q.difficulty,
        "reviewed": q.status == Q_APPROVED,
        "requested_mode": mode,
        "mode": shown,
        "fallback": fallback,
        "lang": study_language,
        "german": german,
        "translation": None,
        "terms": [],
    }
    if shown in TRANSLATED_MODES and translation is not None:
        out["translation"] = {
            "lang": translation.lang,
            "question": translation.question,
            "options": _options(translation.options),
        }
    if shown == MODE_HELP:
        out["terms"] = terms_in(q, glossary)
    if reveal:
        out["answer"] = q.correct
        german["explanation"] = q.explanation_de
        if out["translation"] is not None and translation is not None:
            out["translation"]["explanation"] = translation.explanation
        out["explanation"] = explanation_for(q, translation, study_language)
    return out
