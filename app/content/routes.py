"""Content API: a canton's topics (public) and one question with its translation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.db import get_db
from app.deps import current_user
from app.models import (
    CANTONS,
    CONTENT_MASTER_LANGUAGE,
    LANGUAGES,
    Q_APPROVED,
    T_APPROVED,
    Question,
    QuestionTranslation,
    User,
)
from app.questions import bank

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/topics")
async def topics(
    canton: str = Query(default="zh", min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Every topic of a canton in the order of its topic file, with the number of approved
    questions (federal plus the canton's own). No sign-in needed."""
    canton = canton.lower()
    if canton not in CANTONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_canton")
    counts = await bank.question_counts(db, canton, Question.status == Q_APPROVED)
    rows = await bank.canton_topics(db, canton)
    return {
        "canton": canton,
        "topics": [
            {
                "code": t.code,
                "scope": t.scope,
                "name_de": t.name_de,
                "name_en": t.name_en,
                "target_questions": t.target_questions,
                "approved_questions": counts.get(t.code, 0),
                "sources": t.sources,
            }
            for t in rows
        ],
        "approved_questions": sum(counts.get(t.code, 0) for t in rows),
    }


def translation_status(q: Question, tr: QuestionTranslation | None, lang: str) -> str:
    """source (German), approved, in_review, draft, stale (hidden) or missing."""
    if lang == CONTENT_MASTER_LANGUAGE:
        return "source"
    if tr is None:
        return "missing"
    if tr.hidden or tr.source_version < q.version:
        return "stale"
    return tr.status


@router.get("/questions/{question_id}")
async def question(
    question_id: str,
    lang: str | None = Query(default=None, min_length=2, max_length=5),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The German question, its answer and explanation, and the translation in `lang` (the
    learner's study language by default) when it is approved and not stale."""
    q = await db.get(Question, question_id)
    if user.is_learner:
        if not has_access(user, user.canton):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
        if q is None or not bank.is_servable(q) or q.scope not in ("federal", user.canton):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    elif q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    lang = (lang or user.study_language or "en").lower()
    if lang not in LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_language")
    tr = None
    if lang != CONTENT_MASTER_LANGUAGE:
        tr = (
            await db.execute(
                select(QuestionTranslation).where(
                    QuestionTranslation.question_id == q.id, QuestionTranslation.lang == lang
                )
            )
        ).scalar_one_or_none()
    state = translation_status(q, tr, lang)
    topic = await bank.get_topic(db, q.canton or user.canton, q.topic_code)
    return {
        "id": q.id,
        "version": q.version,
        "scope": q.scope,
        "canton": q.canton,
        "topic_code": q.topic_code,
        "topic_name_de": topic.name_de if topic else None,
        "topic_name_en": topic.name_en if topic else None,
        "difficulty": q.difficulty,
        "glossary": q.glossary,
        "sources": q.sources,
        "correct": q.correct,
        "de": {
            "question": q.question_de,
            "options": q.options_list(),
            "explanation": q.explanation_de,
        },
        "lang": lang,
        "translation_status": state,
        "translation": (
            {
                "lang": tr.lang,
                "question": tr.question,
                "options": [{"key": k, "text": tr.options.get(k, "")} for k in sorted(tr.options)],
                "explanation": tr.explanation,
            }
            if tr is not None and state == T_APPROVED
            else None
        ),
    }
