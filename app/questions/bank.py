"""Serving questions to learners: which questions are servable, a canton's topics and question
counts, and the misses shown to the chat tutor. Questions shown to a learner are the federal ones
and those of the learner's canton; commune-specific questions wait until the app knows a
learner's commune (Phase 2). Study modes, progress, Learn, Practise and the mock test live in
app.study."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Q_APPROVED, Q_IN_REVIEW, Attempt, Question, Topic
from app.questions import checks

REPORTS_TO_HIDE = 2  # open learner reports after which a question is hidden


def servable_clause() -> Any:
    """Approved questions; on staging and in development also those in review, unless
    learners have reported them."""
    if get_settings().unreviewed_questions_allowed:
        return or_(
            Question.status == Q_APPROVED,
            and_(Question.status == Q_IN_REVIEW, Question.report_count < REPORTS_TO_HIDE),
        )
    return Question.status == Q_APPROVED


def is_servable(q: Question) -> bool:
    if q.status == Q_APPROVED:
        return True
    return (
        get_settings().unreviewed_questions_allowed
        and q.status == Q_IN_REVIEW
        and q.report_count < REPORTS_TO_HIDE
    )


def for_canton(canton: str) -> Any:
    """Federal questions plus the canton's own (scope equal to the canton code)."""
    return or_(Question.scope == "federal", Question.scope == canton)


async def canton_topics(db: AsyncSession, canton: str) -> list[Topic]:
    return list(
        (await db.execute(select(Topic).where(Topic.canton == canton).order_by(Topic.position)))
        .scalars()
        .all()
    )


async def get_topic(db: AsyncSession, canton: str, code: str) -> Topic | None:
    return (
        await db.execute(select(Topic).where(Topic.canton == canton, Topic.code == code))
    ).scalar_one_or_none()


async def topic_names(db: AsyncSession, canton: str, locale: str) -> dict[str, str]:
    return {t.code: t.display(locale) for t in await canton_topics(db, canton)}


async def question_counts(db: AsyncSession, canton: str, condition: Any) -> dict[str, int]:
    """Questions per topic code for a canton (federal plus the canton's own)."""
    rows = (
        await db.execute(
            select(Question.topic_code, func.count(Question.id))
            .where(for_canton(canton), condition)
            .group_by(Question.topic_code)
        )
    ).all()
    return {code: int(n) for code, n in rows}


async def recent_misses(
    db: AsyncSession, user_id: uuid.UUID, topic_code: str, limit: int = 3
) -> list[dict[str, str]]:
    """What the learner got wrong on this topic, for the chat's session context. No names."""
    rows = (
        await db.execute(
            select(Attempt, Question)
            .join(Question, Question.id == Attempt.question_id)
            .where(
                Attempt.user_id == user_id,
                Attempt.topic_code == topic_code,
                Attempt.correct.is_(False),
            )
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
    ).all()
    out = []
    for a, q in rows:
        given = checks.option_key(a.answer_text)
        out.append(
            {
                "question": q.question_de[:600],
                "student_answer": f"{given}) {q.options_de.get(given, '')}"[:300] if given else "",
                "correct_answer": f"{q.correct}) {q.options_de.get(q.correct, '')}"[:300],
            }
        )
    return out
