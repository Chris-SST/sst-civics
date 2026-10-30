"""Progress per learner and question, and the spaced-repetition schedule.

Rules (PLAN.md, Languages):
- A correct answer moves the question one mode forward: own language, side by side, German
  with help, German only. A wrong answer leaves the mode as it is; the learner can step back
  (or choose any mode) at any time.
- Understood: answered correctly in the learner's language, that is in `own` or `side` (for a
  learner whose study language is German, any correct answer, since German is their language).
- Known: answered correctly in German only twice, on different Zurich calendar days.

Schedule: Leitner boxes. A new question sits in box 0. A correct answer moves it up one box and
schedules it after that box's interval; a wrong answer puts it back in box 0, due again after
RETRY_AFTER. The first box is short so that a question met in the learner's own language comes
back in the next mode in the same sitting; the later boxes are days apart, so the two German-only
answers that make a question known fall on different days in the normal course.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CONTENT_MASTER_LANGUAGE,
    MODE_DE,
    MODE_OWN,
    MODE_SIDE,
    STUDY_MODES,
    QuestionProgress,
)
from app.study import clock
from app.study.modes import NEXT_MODE, later_mode

# Interval after a correct answer that lands the question in box N.
BOX_INTERVALS = {
    1: timedelta(minutes=10),
    2: timedelta(days=1),
    3: timedelta(days=3),
    4: timedelta(days=7),
    5: timedelta(days=14),
    6: timedelta(days=30),
}
MAX_BOX = max(BOX_INTERVALS)
RETRY_AFTER = timedelta(minutes=10)


async def get_many(
    db: AsyncSession, user_id: uuid.UUID, question_ids: list[str] | None = None
) -> dict[str, QuestionProgress]:
    stmt = select(QuestionProgress).where(QuestionProgress.user_id == user_id)
    if question_ids is not None:
        if not question_ids:
            return {}
        stmt = stmt.where(QuestionProgress.question_id.in_(question_ids))
    return {p.question_id: p for p in (await db.execute(stmt)).scalars()}


async def get_or_create(db: AsyncSession, user_id: uuid.UUID, question_id: str) -> QuestionProgress:
    row = (
        await db.execute(
            select(QuestionProgress).where(
                QuestionProgress.user_id == user_id, QuestionProgress.question_id == question_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = QuestionProgress(
            user_id=user_id,
            question_id=question_id,
            mode=MODE_OWN,
            mode_reached=MODE_OWN,
            correct_own=0,
            correct_side=0,
            correct_help=0,
            correct_de=0,
            wrong=0,
            understood=False,
            known=False,
            box=0,
        )
        db.add(row)
        await db.flush()
    return row


def current_mode(p: QuestionProgress | None) -> str:
    return p.mode if p is not None and p.mode in STUDY_MODES else MODE_OWN


def set_mode(p: QuestionProgress, mode: str) -> None:
    """The learner's own choice of mode, back or forward."""
    if mode not in STUDY_MODES:
        raise ValueError(mode)
    p.mode = mode
    p.mode_reached = later_mode(p.mode_reached or MODE_OWN, mode)


def apply_answer(
    p: QuestionProgress,
    *,
    mode: str,
    correct: bool,
    study_language: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Update progress for one answer given in `mode` (the mode actually shown). Returns what
    changed, for the feedback panel."""
    now = now or clock.now()
    before = {"mode": p.mode, "understood": p.understood, "known": p.known}
    p.last_answered_at = now
    if correct:
        field = f"correct_{mode}"
        setattr(p, field, (getattr(p, field) or 0) + 1)
        if mode in (MODE_OWN, MODE_SIDE) or study_language == CONTENT_MASTER_LANGUAGE:
            p.understood = True
        if mode == MODE_DE:
            today = clock.zurich_day(now)
            if p.last_correct_de_date is not None and p.last_correct_de_date != today:
                p.known = True
            p.last_correct_de_date = today
        set_mode(p, NEXT_MODE[mode])
        p.box = min((p.box or 0) + 1, MAX_BOX)
        p.due_at = now + BOX_INTERVALS[p.box]
    else:
        p.wrong = (p.wrong or 0) + 1
        p.box = 0
        p.due_at = now + RETRY_AFTER
    return {
        "mode": p.mode,
        "previous_mode": before["mode"],
        "moved_forward": p.mode != before["mode"],
        "mode_reached": p.mode_reached,
        "understood": p.understood,
        "known": p.known,
        "newly_understood": p.understood and not before["understood"],
        "newly_known": p.known and not before["known"],
        "box": p.box,
        "due_at": p.due_at.isoformat() if p.due_at else None,
    }


def progress_out(p: QuestionProgress | None) -> dict[str, Any]:
    if p is None:
        return {
            "mode": MODE_OWN,
            "mode_reached": MODE_OWN,
            "understood": False,
            "known": False,
            "seen": False,
            "box": 0,
        }
    return {
        "mode": current_mode(p),
        "mode_reached": p.mode_reached,
        "understood": p.understood,
        "known": p.known,
        "seen": p.seen_at is not None or p.last_answered_at is not None,
        "box": p.box,
    }
