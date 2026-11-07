"""The app's optional "Current affairs" topic (D-074): the current-affairs questions of the
learner's canton, free for everyone signed in, hidden when there are none.

Answers are checked here and nothing is stored: no attempt, no progress, no mastery, so
these questions can never count towards the mock test, the free sample set or readiness."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.deps import require_learner
from app.models import CA_OK, OPTION_KEYS, CurrentAffairsQuestion, User
from app.politics import questions

router = APIRouter(prefix="/api/study/current-affairs", tags=["current-affairs"])


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(max_length=4)


@router.get("")
async def current_affairs(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    qs = await questions.servable(db, user.canton, utcnow())
    return {
        "canton": user.canton,
        "count": len(qs),
        "questions": [questions.render(q, user.study_language) for q in qs],
    }


@router.post("/answer")
async def answer(
    body: AnswerIn, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    q = await db.get(CurrentAffairsQuestion, body.question_id)
    if (
        q is None
        or q.status != CA_OK
        or q.canton != user.canton
        or q.expires_at <= utcnow()
        or body.answer not in OPTION_KEYS
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    out = questions.render(q, user.study_language, reveal=True)
    out["correct"] = body.answer == q.correct
    return out
