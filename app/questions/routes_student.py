"""Learner reports on a question or one of its translations. The study API (Learn, Practise,
mock test, study modes) is in app.study.routes; the old /api/practice routes and the diagnostic
are gone (tasks 1.7 to 1.9)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.deps import require_learner
from app.models import (
    Q_APPROVED,
    Q_IN_REVIEW,
    TRANSLATION_LANGUAGES,
    Question,
    QuestionReport,
    User,
)
from app.questions import bank

questions_router = APIRouter(prefix="/api/questions", tags=["questions"])


class ReportIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)
    # Set when the problem is in a translation rather than in the German question.
    lang: Literal["en", "fr", "it", "pt", "es", "sq", "tr"] | None = None


@questions_router.post("/{question_id}/report", status_code=status.HTTP_201_CREATED)
async def report_question(
    question_id: str,
    body: ReportIn,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.lang is not None and body.lang not in TRANSLATION_LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_language")
    db.add(QuestionReport(question_id=q.id, user_id=user.id, comment=body.comment, lang=body.lang))
    q.report_count += 1
    # After two open reports the question goes back to review and is hidden until an admin
    # has looked at it (on staging too, where questions in review are otherwise served).
    if q.report_count >= bank.REPORTS_TO_HIDE and q.status in (Q_APPROVED, Q_IN_REVIEW):
        q.status = Q_IN_REVIEW
        q.file_sync_pending = True
        q.pending_changes = [
            *(q.pending_changes or []),
            {"action": "learner_reports", "status": Q_IN_REVIEW, "at": utcnow().isoformat()},
        ]
    await db.commit()
    return {"ok": True, "report_count": q.report_count}
