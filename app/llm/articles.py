"""AI calls of the article pipeline (app/articles/produce.py, D-073): writing, fact review,
fixes, translation and translation review.

Direct (non-batch) structured-output calls, since articles are few and time-boxed. The
system prompt is a versioned file under `prompts/articles/`; the user message is the JSON
the pipeline builds from the plan entry, the public source pages and the article itself.
Nothing personal is ever sent: no name, email or identifier (Chris's suggestions are about
the text and are sent as written).

`call` talks to the provider only, so several calls can run at once; `record` writes the
cost log row afterwards (one database session must not be used concurrently)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import prompts, service
from app.llm.client import LLMError, LLMUnavailable, Usage, get_provider

PURPOSE_WRITE = "article_write"
PURPOSE_REVIEW = "article_review"
PURPOSE_FIX = "article_fix"
PURPOSE_TRANSLATE = "article_translate"
PURPOSE_TRANSLATION_REVIEW = "article_translation_review"

PROMPT_WRITE = "articles/write"
PROMPT_REVIEW = "articles/review"
PROMPT_FIX = "articles/fix"
PROMPT_TRANSLATE = "articles/translate"
PROMPT_TRANSLATION_REVIEW = "articles/translation_review"

_FAQ = {
    "type": "object",
    "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
    "required": ["q", "a"],
    "additionalProperties": False,
}
_SOURCE = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
    "required": ["title", "url"],
    "additionalProperties": False,
}
_ARTICLE_FIELDS: dict[str, Any] = {
    "title": {"type": "string"},
    "slug": {"type": "string"},
    "description": {"type": "string"},
    "summary": {"type": "array", "items": {"type": "string"}},
    "body": {"type": "string"},
    "faq": {"type": "array", "items": _FAQ},
    "sources": {"type": "array", "items": _SOURCE},
    "related": {"type": "array", "items": {"type": "string"}},
}

ARTICLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": _ARTICLE_FIELDS,
    "required": list(_ARTICLE_FIELDS),
    "additionalProperties": False,
}

FIX_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {**_ARTICLE_FIELDS, "changes": {"type": "array", "items": {"type": "string"}}},
    "required": [*_ARTICLE_FIELDS, "changes"],
    "additionalProperties": False,
}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fix"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "problem": {"type": "string"},
                    "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                    "fix": {"type": "string"},
                },
                "required": ["claim", "problem", "severity", "fix"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "findings"],
    "additionalProperties": False,
}

_TRANSLATION_FIELDS: dict[str, Any] = {
    "title": {"type": "string"},
    "slug": {"type": "string"},
    "description": {"type": "string"},
    "summary": {"type": "array", "items": {"type": "string"}},
    "body": {"type": "string"},
    "faq": {"type": "array", "items": _FAQ},
    "source_titles": {"type": "array", "items": {"type": "string"}},
}

TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": _TRANSLATION_FIELDS,
    "required": list(_TRANSLATION_FIELDS),
    "additionalProperties": False,
}

TRANSLATION_REVIEW_SCHEMA = REVIEW_SCHEMA


@dataclass
class CallResult:
    purpose: str
    prompt_label: str
    model: str
    data: dict[str, Any] | None
    usage: Usage | None
    latency_ms: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


async def call(
    *,
    purpose: str,
    prompt_name: str,
    model: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
    effort: str,
    max_tokens: int = 16_000,
    timeout: float = 600.0,
) -> CallResult:
    spec = prompts.load(prompt_name)
    started = time.monotonic()
    try:
        data, completion = await get_provider().structured(
            model=model,
            system=spec.text,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            schema=schema,
            max_tokens=max_tokens,
            effort=effort,
            timeout=timeout,
        )
    except LLMUnavailable:
        return CallResult(purpose, spec.label, model, None, None, 0, "AI provider not configured")
    except LLMError as exc:
        ms = int((time.monotonic() - started) * 1000)
        return CallResult(
            purpose, spec.label, model, None, None, ms, f"{exc.code} {exc.detail}".strip()
        )
    ms = int((time.monotonic() - started) * 1000)
    if not isinstance(data, dict):
        return CallResult(purpose, spec.label, completion.model, None, completion.usage, ms, "bad")
    return CallResult(purpose, spec.label, completion.model or model, data, completion.usage, ms)


async def record(db: AsyncSession, result: CallResult) -> float:
    """Write the cost log row; returns the cost in CHF."""
    if result.usage is None and result.error == "AI provider not configured":
        return 0.0
    row = await service.record_call(
        db,
        user_id=None,
        conversation_id=None,
        purpose=result.purpose,
        model=result.model,
        prompt_version=result.prompt_label,
        status="ok" if result.ok else "error",
        usage=result.usage,
        latency_ms=result.latency_ms,
    )
    return float(row.cost_chf)
