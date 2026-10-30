"""Learner practice API: diagnostic, next question, attempts, check questions, reports."""

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
from app.llm import prompts
from app.models import (
    ATTEMPT_CHECK,
    ATTEMPT_DIAGNOSTIC,
    ATTEMPT_PRACTICE,
    Q_NEEDS_REVIEW,
    Attempt,
    Conversation,
    DiagnosticRun,
    Question,
    QuestionReport,
    User,
)
from app.questions import bank, mastery

router = APIRouter(prefix="/api/practice", tags=["practice"])


class DiagnosticStart(BaseModel):
    course_key: str


class AttemptIn(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(max_length=4000)
    mode: Literal["diagnostic", "practice", "check"] = "practice"
    course_key: str | None = None
    conversation_id: uuid.UUID | None = None
    diagnostic_id: uuid.UUID | None = None


class ReportIn(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


async def _full_access(db: AsyncSession, user: User) -> None:
    if not has_access(user, user.canton):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")


def _own_course(user: User, course_key: str) -> None:
    if not prompts.has_course_module(course_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_course")


def run_locale(q: Question, user: User) -> str:
    return user.locale


def _diagnostic_out(run: DiagnosticRun, q: Question | None, locale: str = "en") -> dict[str, Any]:
    return {
        "id": str(run.id),
        "course_key": run.course_key,
        "status": run.status,
        "position": run.position,
        "total": len(run.question_ids),
        "question": bank.question_public(q, locale=locale) if q else None,
    }


@router.get("/overview")
async def overview(
    course_key: str, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _own_course(user, course_key)
    topics = await bank.mastery_overview(db, user, course_key)
    run = await bank.latest_diagnostic(db, user.id, course_key)
    tested = [t for t in topics if t["mastery"] is not None]
    overall = int(round(sum(t["mastery"] for t in tested) / len(tested))) if tested else None
    per_topic = get_settings().diagnostic_questions_per_topic
    return {
        "course_key": course_key,
        "topics": topics,
        "overall": overall,
        "questions_available": sum(t["questions_available"] for t in topics),
        "diagnostic_total_estimate": sum(min(per_topic, t["questions_available"]) for t in topics),
        "diagnostic": None if run is None else {"id": str(run.id), "status": run.status},
        "next": bank.suggest_next(topics),
    }


@router.post("/diagnostic/start", status_code=status.HTTP_201_CREATED)
async def start_diagnostic(
    body: DiagnosticStart, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    _own_course(user, body.course_key)
    await _full_access(db, user)
    existing = await bank.latest_diagnostic(db, user.id, body.course_key)
    if existing and existing.status == "in_progress":
        q = await bank.diagnostic_current(db, existing)
        return _diagnostic_out(existing, q, user.locale)
    run = await bank.build_diagnostic(db, user, body.course_key)
    await db.commit()
    q = await bank.diagnostic_current(db, run)
    return _diagnostic_out(run, q, user.locale)


@router.get("/diagnostic/{run_id}")
async def get_diagnostic(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await db.get(DiagnosticRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    out = _diagnostic_out(run, await bank.diagnostic_current(db, run), user.locale)
    if run.status in ("done", "skipped"):
        topics = await bank.mastery_overview(db, user, run.course_key)
        out["summary"] = topics
        out["next"] = bank.suggest_next(topics)
    return out


@router.post("/diagnostic/{run_id}/skip")
async def skip_diagnostic(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await db.get(DiagnosticRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if run.status == "in_progress":
        run.status = "skipped"
        run.completed_at = utcnow()
        await db.commit()
    return _diagnostic_out(run, None)


@router.get("/next")
async def next_question(
    course_key: str,
    topic_code: str,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _own_course(user, course_key)
    await _full_access(db, user)
    qs = await bank.next_question(db, user, course_key, topic_code)
    if not qs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    return bank.question_public(qs[0], locale=user.locale)


@router.get("/round")
async def practice_round(
    course_key: str,
    topic_code: str,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A short round of distinct practice questions on one topic, with the count up front so
    the learner knows how many are to go."""
    _own_course(user, course_key)
    await _full_access(db, user)
    size = get_settings().practice_round_size
    qs, pool, unseen = await bank.select_questions(db, user, course_key, topic_code, n=size)
    if not qs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    m = await mastery.get_or_create(db, user.id, course_key, topic_code)
    await db.commit()
    return {
        "course_key": course_key,
        "topic_code": topic_code,
        "topic_name": bank.topic_name(
            prompts.course_module_key(course_key), topic_code, user.locale
        ),
        "mastery": mastery.mastery_percent(m.rating),
        "attempts": m.attempts,
        "pool": pool,
        "unseen": unseen,
        "questions": [bank.question_public(q, locale=user.locale) for q in qs],
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
    await _full_access(db, user)
    qs = await bank.next_question(db, user, conv.course_key, conv.topic_code, n=3)
    return {
        "conversation_id": str(conv.id),
        "course_key": conv.course_key,
        "topic_code": conv.topic_code,
        "questions": [bank.question_public(q, locale=user.locale) for q in qs],
    }


@router.post("/attempts")
async def submit_attempt(
    body: AttemptIn, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    await _full_access(db, user)
    q = await db.get(Question, body.question_id)
    if q is None or q.status not in bank.servable_statuses():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")

    run: DiagnosticRun | None = None
    course_key = body.course_key
    if body.mode == ATTEMPT_DIAGNOSTIC:
        if body.diagnostic_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "diagnostic_required")
        run = await db.get(DiagnosticRun, body.diagnostic_id)
        if run is None or run.user_id != user.id or run.status != "in_progress":
            raise HTTPException(status.HTTP_409_CONFLICT, "diagnostic_not_active")
        if run.question_ids[run.position] != str(q.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "wrong_question")
        course_key = run.course_key
    elif body.mode == ATTEMPT_CHECK:
        if body.conversation_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversation_required")
        conv = await db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        course_key = conv.course_key
    if not course_key:
        # Practice: find the course that uses this module
        course_key = next(
            (
                c
                for c in prompts.available_courses()
                if prompts.course_module_key(c) == q.module_key
            ),
            None,
        )
        if course_key is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_course")
    _own_course(user, course_key)
    before = await mastery.get_or_create(db, user.id, course_key, q.topic_code)
    mastery_before = mastery.mastery_percent(before.rating)

    attempt = await bank.submit_attempt(
        db,
        student=user,
        question=q,
        course_key=course_key,
        answer_text=body.answer,
        mode=body.mode
        if body.mode in (ATTEMPT_DIAGNOSTIC, ATTEMPT_PRACTICE, ATTEMPT_CHECK)
        else ATTEMPT_PRACTICE,
        conversation_id=body.conversation_id,
        diagnostic_id=body.diagnostic_id,
    )
    out: dict[str, Any] = {
        "attempt_id": str(attempt.id),
        "correct": attempt.correct,
        "score": attempt.score,
        "answer": q.answer,
        "answer_text": next(
            (
                o.get("text")
                for o in (q.options or [])
                if str(o.get("key", "")).upper() == q.answer.strip().upper()
            ),
            None,
        )
        if q.qtype == "mcq"
        else None,
        "worked_solution": q.worked_solution,
    }
    m = await mastery.get_or_create(db, user.id, course_key, q.topic_code)
    out["mastery"] = {
        "topic_code": q.topic_code,
        "mastery": mastery.mastery_percent(m.rating),
        "previous": mastery_before,
    }

    if run is not None:
        run.position += 1
        if run.position >= len(run.question_ids):
            run.status = "done"
            run.completed_at = utcnow()
            topics = await bank.mastery_overview(db, user, course_key)
            out["diagnostic"] = {
                **_diagnostic_out(run, None),
                "summary": topics,
                "next": bank.suggest_next(topics),
            }
        else:
            out["diagnostic"] = _diagnostic_out(
                run, await bank.diagnostic_current(db, run), user.locale
            )
    await db.commit()
    return out


@router.get("/attempts")
async def list_attempts(
    course_key: str | None = None,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(Attempt)
        .where(Attempt.user_id == user.id)
        .order_by(Attempt.created_at.desc())
        .limit(100)
    )
    if course_key:
        stmt = stmt.where(Attempt.course_key == course_key)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(a.id),
            "question_id": str(a.question_id),
            "topic_code": a.topic_code,
            "mode": a.mode,
            "correct": a.correct,
            "score": a.score,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.post("/questions/{question_id}/report", status_code=status.HTTP_201_CREATED)
async def report_question(
    question_id: uuid.UUID,
    body: ReportIn,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    db.add(QuestionReport(question_id=q.id, user_id=user.id, comment=body.comment))
    q.report_count += 1
    # After two reports the question is hidden until a tutor has looked at it (plan).
    if q.report_count >= 2 and q.status in bank.servable_statuses():
        q.status = Q_NEEDS_REVIEW
        q.check_results = {**(q.check_results or {}), "issues": ["student_reports"]}
    await db.commit()
    return {"ok": True, "report_count": q.report_count}
