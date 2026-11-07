"""AI calls of "Politics in your canton" (app/politics/, D-074): purposes, prompt names and
the structured-output schemas. The calls themselves go through `app.llm.articles.call` and
`record`, like the article pipeline's: direct structured-output calls, the system prompt a
versioned file under `prompts/politics/`, the user message JSON built from public pages of
the authorities. Nothing personal is ever sent.

Translations of the pages reuse the article prompts (`articles/translate`,
`articles/translation_review`); everything else has its own prompt."""

from __future__ import annotations

from typing import Any

from app.llm.articles import ARTICLE_SCHEMA, FIX_SCHEMA, REVIEW_SCHEMA

PURPOSE_LINKS = "politics_links"  # pick item links from a listing that did not parse
PURPOSE_PROPOSALS = "politics_proposals"  # the proposals named on a vote announcement
PURPOSE_RESULTS = "politics_results"  # cantonal vote results stated on a page
PURPOSE_ROSTER = "politics_roster"  # the who's-who facts, to see whether anything changed
PURPOSE_SELECT = "politics_select"
PURPOSE_WRITE = "politics_write"
PURPOSE_FIX = "politics_fix"
PURPOSE_NEUTRALITY = "politics_neutrality"
PURPOSE_REVIEW = "politics_review"
PURPOSE_QUESTIONS = "politics_questions"
PURPOSE_QUESTION_CHECK = "politics_question_check"
PURPOSE_QUESTION_TRANSLATE = "politics_question_translate"

PROMPT_LINKS = "politics/links"
PROMPT_PROPOSALS = "politics/proposals"
PROMPT_RESULTS = "politics/results"
PROMPT_ROSTER = "politics/roster"
PROMPT_SELECT = "politics/select"
PROMPT_WRITE = {
    "roundup": "politics/write_roundup",
    "vote": "politics/write_vote",
    "whoswho": "politics/write_whoswho",
}
PROMPT_FIX = "politics/fix"
PROMPT_NEUTRALITY = "politics/neutrality_review"
PROMPT_REVIEW = "politics/fact_review"
PROMPT_QUESTIONS = "politics/questions"
PROMPT_QUESTION_CHECK = "politics/question_check"
PROMPT_QUESTION_TRANSLATE = "politics/question_translate"

PAGE_SCHEMA = ARTICLE_SCHEMA
PAGE_FIX_SCHEMA = FIX_SCHEMA
NEUTRALITY_SCHEMA = REVIEW_SCHEMA
FACT_REVIEW_SCHEMA = REVIEW_SCHEMA


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}

LINKS_SCHEMA = _obj(
    {"items": {"type": "array", "items": _obj({"url": _STR, "title": _STR, "date": _STR})}}
)

PROPOSALS_SCHEMA = _obj(
    {
        "vote_date": _STR,  # YYYY-MM-DD, or "" when the page names none
        "proposals": {"type": "array", "items": _obj({"title_de": _STR, "short_name": _STR})},
    }
)

RESULTS_SCHEMA = _obj(
    {
        "results": {
            "type": "array",
            "items": _obj(
                {
                    "title_de": _STR,
                    "yes_percent": {"type": "number"},
                    "turnout_percent": {"type": "number"},
                    "accepted": {"type": "boolean"},
                }
            ),
        }
    }
)

ROSTER_SCHEMA = _obj(
    {
        "regierungsrat": {
            "type": "array",
            "items": _obj({"name": _STR, "office": _STR, "party": _STR}),
        },
        "president": _STR,
        "kantonsrat_groups": _STRS,
        "zurich_executive": {
            "type": "array",
            "items": _obj({"name": _STR, "office": _STR, "party": _STR}),
        },
        "winterthur_executive": {
            "type": "array",
            "items": _obj({"name": _STR, "office": _STR, "party": _STR}),
        },
    }
)

SELECT_SCHEMA = _obj(
    {
        "items": {
            "type": "array",
            "items": _obj({"url": _STR, "why": _STR}),
        },
        "quiet_week": {"type": "boolean"},
    }
)

_OPTIONS = _obj({"a": _STR, "b": _STR, "c": _STR, "d": _STR})

QUESTIONS_SCHEMA = _obj(
    {
        "questions": {
            "type": "array",
            "items": _obj(
                {
                    "question_de": _STR,
                    "options_de": _OPTIONS,
                    "correct": {"type": "string", "enum": ["a", "b", "c", "d"]},
                    "explanation_de": _STR,
                    "page_fact": _STR,
                }
            ),
        }
    }
)

QUESTION_CHECK_SCHEMA = _obj(
    {
        "checks": {
            "type": "array",
            "items": _obj(
                {
                    "n": {"type": "integer"},
                    "answer": {"type": "string", "enum": ["a", "b", "c", "d", "none"]},
                    "answerable_from_page": {"type": "boolean"},
                    "single_correct": {"type": "boolean"},
                    "neutral": {"type": "boolean"},
                    "problem": _STR,
                }
            ),
        }
    }
)

_TRANSLATED_QUESTION = _obj({"question": _STR, "options": _OPTIONS, "explanation": _STR})

QUESTION_TRANSLATE_SCHEMA = _obj(
    {
        "translations": {
            "type": "array",
            "items": _obj(
                {
                    "n": {"type": "integer"},
                    "en": _TRANSLATED_QUESTION,
                    "fr": _TRANSLATED_QUESTION,
                    "it": _TRANSLATED_QUESTION,
                    "pt": _TRANSLATED_QUESTION,
                    "es": _TRANSLATED_QUESTION,
                    "sq": _TRANSLATED_QUESTION,
                    "tr": _TRANSLATED_QUESTION,
                }
            ),
        }
    }
)
