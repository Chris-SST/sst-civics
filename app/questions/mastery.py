"""Elo-style mastery per learner and topic code. Question difficulty runs from 1 to 3."""

from __future__ import annotations

import math
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import TopicMastery

START_RATING = 1200.0  # equal to a difficulty-2 question: an untested learner sits at 50%
K_EARLY = 64.0
K_LATE = 32.0
EARLY_ATTEMPTS = 10
MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 3


def question_rating(difficulty: int) -> float:
    """800, 1200 and 1600 for difficulties 1, 2 and 3."""
    d = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, difficulty))
    return 1200.0 + 400.0 * (d - 2)


def expected_score(learner_rating: float, q_rating: float) -> float:
    return 1.0 / (1.0 + 10 ** ((q_rating - learner_rating) / 400.0))


def mastery_percent(rating: float) -> int:
    """0 to 100: the chance of answering a difficulty-2 question, roughly."""
    p = 1.0 / (1.0 + 10 ** ((question_rating(2) - rating) / 400.0))
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
    """The difficulty at which the learner has about a 65% chance: a stretch, not a wall."""
    q = rating - 400 * math.log10(0.65 / 0.35)
    d = 2 + (q - 1200.0) / 400.0
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, int(round(d))))


async def get_or_create(db: AsyncSession, user_id: uuid.UUID, topic_code: str) -> TopicMastery:
    row = (
        await db.execute(
            select(TopicMastery).where(
                TopicMastery.user_id == user_id, TopicMastery.topic_code == topic_code
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = TopicMastery(user_id=user_id, topic_code=topic_code, rating=START_RATING)
        db.add(row)
        await db.flush()
    return row


async def record_result(
    db: AsyncSession, user_id: uuid.UUID, topic_code: str, difficulty: int, score: float
) -> TopicMastery:
    row = await get_or_create(db, user_id, topic_code)
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
