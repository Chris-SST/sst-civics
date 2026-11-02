"""Question of the day for the guide site's home page (D-067).

`GET /api/public/question-of-the-day` returns one servable question of the canton (federal or
the canton's own) in German, with its English translation when there is a usable one, the
correct key and the explanation. The pick changes at midnight Swiss time and is the same for
every visitor that day. In production only approved questions with an approved English
translation take part; on staging (SERVE_UNREVIEWED_QUESTIONS) questions in review and draft
English translations do too (`modes.translation_usable`), so the feature can be seen before
the bank is approved. With no question to show the answer is 404 and the page keeps its
built-in sample question.

The guide host proxies this path to the API (infra/Caddyfile)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OPTION_KEYS, Question
from app.questions import bank
from app.study import modes

router = APIRouter(prefix="/api/public", tags=["public"])

ZURICH = ZoneInfo("Europe/Zurich")
SIDE_LANG = "en"  # the guide site shows the German question with English beside it


def pick_index(n: int, day: int) -> int:
    """Spread consecutive days over the bank instead of walking it in id order."""
    return (day * 7919) % n


@router.get("/question-of-the-day")
async def question_of_the_day(
    response: Response,
    canton: str = Query(default="zh", max_length=2),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    questions = list(
        (
            await db.execute(
                select(Question)
                .where(bank.for_canton(canton), bank.servable_clause())
                .order_by(Question.id)
            )
        )
        .scalars()
        .all()
    )
    english = await modes.translations_for(db, [q.id for q in questions], SIDE_LANG)
    pool = [q for q in questions if modes.translation_usable(q, english.get(q.id))]
    if not pool:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_question")
    today = datetime.now(ZURICH).date()
    q = pool[pick_index(len(pool), today.toordinal())]
    tr = english[q.id]
    response.headers["Cache-Control"] = "public, max-age=600"
    return {
        "id": q.id,
        "date": today.isoformat(),
        "topic": q.topic_code,
        "correct": q.correct,
        "de": {
            "question": q.question_de,
            "options": {k: q.options_de.get(k, "") for k in OPTION_KEYS},
            "explanation": q.explanation_de,
        },
        "en": {
            "question": tr.question,
            "options": {k: tr.options.get(k, "") for k in OPTION_KEYS},
            "explanation": tr.explanation,
        },
    }
