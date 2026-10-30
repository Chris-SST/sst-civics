"""Elo-style mastery per student and topic (D-040)."""

from __future__ import annotations

import math
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import TopicMastery

START_RATING = 1200.0  # equal to a difficulty-3 question: an untested student sits at 50%
K_EARLY = 64.0
K_LATE = 32.0
EARLY_ATTEMPTS = 10


def question_rating(difficulty: int) -> float:
    return 600.0 + 200.0 * max(1, min(5, difficulty))


def expected_score(student_rating: float, q_rating: float) -> float:
    return 1.0 / (1.0 + 10 ** ((q_rating - student_rating) / 400.0))


def mastery_percent(rating: float) -> int:
    """0 to 100: the chance of answering a difficulty-3 question, roughly."""
    p = 1.0 / (1.0 + 10 ** ((question_rating(3) - rating) / 400.0))
    return int(round(100 * p))


def review_interval(rating: float, correct: bool) -> timedelta:
    """Spaced revisits: weak topics come back soon, strong ones later."""
    if not correct:
        return timedelta(days=1)
    pct = mastery_percent(rating)
    if pct < 50:
        return timedelta(days=2)
    if pct < 75:
        return timedelta(days=5)
    return timedelta(days=12)


def target_difficulty(rating: float) -> int:
    """The difficulty at which the student has about a 65% chance: a stretch, not a wall."""
    # Solve expected_score = 0.65 for q_rating, then map back to 1..5
    q = rating - 400 * math.log10(0.65 / 0.35)
    d = (q - 600.0) / 200.0
    return max(1, min(5, int(round(d))))


async def get_or_create(
    db: AsyncSession, user_id, course_key: str, topic_code: str
) -> TopicMastery:
    row = (
        await db.execute(
            select(TopicMastery).where(
                TopicMastery.user_id == user_id,
                TopicMastery.course_key == course_key,
                TopicMastery.topic_code == topic_code,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = TopicMastery(
            user_id=user_id, course_key=course_key, topic_code=topic_code, rating=START_RATING
        )
        db.add(row)
        await db.flush()
    return row


async def record_result(
    db: AsyncSession, user_id, course_key: str, topic_code: str, difficulty: int, score: float
) -> TopicMastery:
    row = await get_or_create(db, user_id, course_key, topic_code)
    k = K_EARLY if row.attempts < EARLY_ATTEMPTS else K_LATE
    exp = expected_score(row.rating, question_rating(difficulty))
    row.rating = row.rating + k * (score - exp)
    row.attempts += 1
    if score >= 0.7:
        row.correct += 1
    now = utcnow()
    row.last_attempt_at = now
    row.next_review_at = now + review_interval(row.rating, score >= 0.7)
    await db.flush()
    return row
