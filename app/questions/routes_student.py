"""Learner practice API on the canton's topics: overview, diagnostic, practice rounds, check
questions after a chat, attempts and reports. Learn, Practise and Mock test with the study
modes replace parts of this in tasks 1.7 to 1.9."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import require_learner
from app.models import (
    ATTEMPT_CHECK,
    ATTEMPT_DIAGNOSTIC,
    ATTEMPT_PRACTICE,
    Q_APPROVED,
    Q_IN_REVIEW,
    TRANSLATION_LANGUAGES,
    Attempt,
    Conversation,
    DiagnosticRun,
    Question,
    QuestionReport,
    User,
)
from app.questions import bank, mastery

router = APIRouter(prefix="/api/practice", tags=["practice"])
# The report endpoint also lives at /api/questions/{id}/report.
questions_router = APIRouter(prefix="/api/questions", tags=["practice"])


class AttemptIn(BaseModel):
    question_id: str = Field(max_length=80)
    answer: str = Field(max_length=20)
    mode: Literal["diagnostic", "practice", "check"] = "practice"
    conversation_id: uuid.UUID | None = None
    diagnostic_id: uuid.UUID | None = None


class ReportIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)
    # Set when the problem is in a translation rather than in the German question.
    lang: Literal["en", "fr", "it", "pt", "es", "sq", "tr"] | None = None


def _require_access(user: User) -> None:
    if not has_access(user, user.canton):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")


def _servable_for(q: Question | None, user: User) -> bool:
    return q is not None and bank.is_servable(q) and q.scope in ("federal", user.canton)


async def _public(db: AsyncSession, user: User, q: Question | None) -> dict[str, Any] | None:
    if q is None:
        return None
    topic = await bank.get_topic(db, user.canton, q.topic_code)
    return bank.question_public(q, topic_name=topic.display(user.locale) if topic else None)


async def _diagnostic_out(
    db: AsyncSession, run: DiagnosticRun, user: User, q: Question | None
) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "canton": run.canton,
        "status": run.status,
        "position": run.position,
        "total": len(run.question_ids),
        "question": await _public(db, user, q),
    }


@router.get("/overview")
async def overview(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    topics = await bank.mastery_overview(db, user)
    run = await bank.latest_diagnostic(db, user.id, user.canton)
    tested = [t for t in topics if t["mastery"] is not None]
    overall = int(round(sum(t["mastery"] for t in tested) / len(tested))) if tested else None
    per_topic = get_settings().diagnostic_questions_per_topic
    return {
        "canton": user.canton,
        "topics": topics,
        "overall": overall,
        "questions_available": sum(t["questions_available"] for t in topics),
        "diagnostic_total_estimate": sum(min(per_topic, t["questions_available"]) for t in topics),
        "diagnostic": None if run is None else {"id": str(run.id), "status": run.status},
        "next": bank.suggest_next(topics),
    }


@router.post("/diagnostic/start", status_code=status.HTTP_201_CREATED)
async def start_diagnostic(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _require_access(user)
    existing = await bank.latest_diagnostic(db, user.id, user.canton)
    if existing and existing.status == "in_progress":
        q = await bank.diagnostic_current(db, existing)
        return await _diagnostic_out(db, existing, user, q)
    run = await bank.build_diagnostic(db, user)
    await db.commit()
    q = await bank.diagnostic_current(db, run)
    return await _diagnostic_out(db, run, user, q)


async def _own_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> DiagnosticRun:
    run = await db.get(DiagnosticRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return run


@router.get("/diagnostic/{run_id}")
async def get_diagnostic(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await _own_run(db, user, run_id)
    out = await _diagnostic_out(db, run, user, await bank.diagnostic_current(db, run))
    if run.status in ("done", "skipped"):
        topics = await bank.mastery_overview(db, user)
        out["summary"] = topics
        out["next"] = bank.suggest_next(topics)
    return out


@router.post("/diagnostic/{run_id}/skip")
async def skip_diagnostic(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await _own_run(db, user, run_id)
    if run.status == "in_progress":
        run.status = "skipped"
        run.completed_at = utcnow()
        await db.commit()
    return await _diagnostic_out(db, run, user, None)


@router.get("/next")
async def next_question(
    topic_code: str, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _require_access(user)
    qs = await bank.next_question(db, user, topic_code)
    if not qs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    out = await _public(db, user, qs[0])
    assert out is not None
    return out


@router.get("/round")
async def practice_round(
    topic_code: str, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A short round of distinct practice questions on one topic, with the count up front so
    the learner knows how many are to go."""
    _require_access(user)
    topic = await bank.get_topic(db, user.canton, topic_code)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    size = get_settings().practice_round_size
    qs, pool, unseen = await bank.select_questions(db, user, topic_code, n=size)
    if not qs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    m = await mastery.get_or_create(db, user.id, topic_code)
    await db.commit()
    name = topic.display(user.locale)
    return {
        "topic_code": topic_code,
        "topic_name": name,
        "mastery": mastery.mastery_percent(m.rating),
        "attempts": m.attempts,
        "pool": pool,
        "unseen": unseen,
        "questions": [bank.question_public(q, topic_name=name) for q in qs],
    }


@router.get("/check")
async def check_questions(
    conversation_id: uuid.UUID,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Two or three questions on the conversation's topic, to check what was learnt."""
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _require_access(user)
    qs = await bank.next_question(db, user, conv.topic_code, n=3)
    return {
        "conversation_id": str(conv.id),
        "topic_code": conv.topic_code,
        "questions": [bank.question_public(q, topic_name=conv.topic_name) for q in qs],
    }


@router.post("/attempts")
async def submit_attempt(
    body: AttemptIn, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _require_access(user)
    q = await db.get(Question, body.question_id)
    if not _servable_for(q, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    assert q is not None

    run: DiagnosticRun | None = None
    if body.mode == ATTEMPT_DIAGNOSTIC:
        if body.diagnostic_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "diagnostic_required")
        run = await db.get(DiagnosticRun, body.diagnostic_id)
        if run is None or run.user_id != user.id or run.status != "in_progress":
            raise HTTPException(status.HTTP_409_CONFLICT, "diagnostic_not_active")
        if run.question_ids[run.position] != q.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "wrong_question")
    elif body.mode == ATTEMPT_CHECK:
        if body.conversation_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversation_required")
        conv = await db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    before = await mastery.get_or_create(db, user.id, q.topic_code)
    mastery_before = mastery.mastery_percent(before.rating)

    attempt = await bank.submit_attempt(
        db,
        learner=user,
        question=q,
        answer_text=body.answer,
        mode=body.mode if body.mode in (ATTEMPT_DIAGNOSTIC, ATTEMPT_CHECK) else ATTEMPT_PRACTICE,
        conversation_id=body.conversation_id,
        diagnostic_id=body.diagnostic_id,
    )
    m = await mastery.get_or_create(db, user.id, q.topic_code)
    out: dict[str, Any] = {
        "attempt_id": str(attempt.id),
        "correct": attempt.correct,
        "score": attempt.score,
        "answer": q.correct,
        "answer_text": q.options_de.get(q.correct),
        "explanation": q.explanation_de,
        "mastery": {
            "topic_code": q.topic_code,
            "mastery": mastery.mastery_percent(m.rating),
            "previous": mastery_before,
        },
    }
    if run is not None:
        run.position += 1
        if run.position >= len(run.question_ids):
            run.status = "done"
            run.completed_at = utcnow()
            topics = await bank.mastery_overview(db, user)
            out["diagnostic"] = {
                **await _diagnostic_out(db, run, user, None),
                "summary": topics,
                "next": bank.suggest_next(topics),
            }
        else:
            out["diagnostic"] = await _diagnostic_out(
                db, run, user, await bank.diagnostic_current(db, run)
            )
    await db.commit()
    return out


@router.get("/attempts")
async def list_attempts(
    topic_code: str | None = None,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(Attempt)
        .where(Attempt.user_id == user.id)
        .order_by(Attempt.created_at.desc())
        .limit(100)
    )
    if topic_code:
        stmt = stmt.where(Attempt.topic_code == topic_code)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(a.id),
            "question_id": a.question_id,
            "topic_code": a.topic_code,
            "mode": a.mode,
            "correct": a.correct,
            "score": a.score,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.post("/questions/{question_id}/report", status_code=status.HTTP_201_CREATED)
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
