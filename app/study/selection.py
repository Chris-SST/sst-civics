"""Which questions a learner may study, the free-tier sample set, topic mastery and readiness,
and the adaptive choice of Practise questions.

Free tier: without a pass, Learn and Practise serve only the canton's sample set, the first
SAMPLE_SIZE servable questions of the canton (federal plus the canton's own) ordered by
difficulty and then id. The set is chosen at request time, not stored at import, so it needs no
import step and is the same for every learner; it shifts only when an easier question, or one
as easy with a lower id, is approved.

Practise picks a round of distinct questions:
1. Tiers: questions due for review first, then new ones, then ones not yet due; a question
   answered in the last RECENT_WINDOW comes last of all, so nothing repeats while an
   alternative exists.
2. Within a tier, slots go to topics by weight / (1 + slots already given), where the weight
   is 0.2 plus the share of the topic not yet mastered: weak topics get more of the round,
   strong ones still appear.
3. Within a topic: due ones the most overdue first, new ones easiest first, the rest by due
   date; ties at random.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Integer, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.models import Question, QuestionProgress, Topic, User
from app.questions import bank
from app.questions.mastery import TopicCounts, readiness_percent, topic_mastery_percent
from app.study import clock, progress

SAMPLE_SIZE = 30
RECENT_WINDOW = timedelta(minutes=10)
MIN_TOPIC_WEIGHT = 0.2

TIER_DUE, TIER_NEW, TIER_LATER, TIER_RECENT = 0, 1, 2, 3


def full_access(user: User) -> bool:
    return has_access(user, user.canton)


async def servable_questions(db: AsyncSession, canton: str) -> list[Question]:
    stmt = (
        select(Question)
        .where(bank.for_canton(canton), bank.servable_clause())
        .order_by(Question.difficulty, Question.id)
    )
    return list((await db.execute(stmt)).scalars().all())


def sample_of(questions: list[Question]) -> list[Question]:
    return sorted(questions, key=lambda q: (q.difficulty, q.id))[:SAMPLE_SIZE]


async def accessible_questions(
    db: AsyncSession, user: User, topic_code: str | None = None
) -> list[Question]:
    """Everything servable with a pass, the sample set without one; optionally one topic."""
    qs = await servable_questions(db, user.canton)
    if not full_access(user):
        qs = sample_of(qs)
    if topic_code is not None:
        qs = [q for q in qs if q.topic_code == topic_code]
    return qs


def servable_for(q: Question | None, user: User) -> bool:
    return q is not None and bank.is_servable(q) and q.scope in ("federal", user.canton)


async def can_study(db: AsyncSession, user: User, q: Question) -> bool:
    if not servable_for(q, user):
        return False
    if full_access(user):
        return True
    return q.id in {s.id for s in await accessible_questions(db, user)}


# --- Mastery and readiness ----------------------------------------------------------------


@dataclass
class TopicState:
    topic: Topic
    total: int  # servable questions on the topic (the whole bank)
    available: int  # of which this learner may study now (the sample set on the free tier)
    understood: int
    known: int
    seen: int  # questions shown in Learn or answered
    due: int  # answered questions due for review now

    @property
    def mastery(self) -> int:
        return topic_mastery_percent(self.known, self.understood, self.total)


async def topic_states(db: AsyncSession, user: User) -> list[TopicState]:
    topics = await bank.canton_topics(db, user.canton)
    all_qs = await servable_questions(db, user.canton)
    available = all_qs if full_access(user) else sample_of(all_qs)
    totals: dict[str, int] = {}
    for q in all_qs:
        totals[q.topic_code] = totals.get(q.topic_code, 0) + 1
    avail: dict[str, int] = {}
    for q in available:
        avail[q.topic_code] = avail.get(q.topic_code, 0) + 1
    now = clock.now()
    rows = (
        await db.execute(
            select(
                Question.topic_code,
                func.sum(QuestionProgress.understood.cast(Integer)),
                func.sum(QuestionProgress.known.cast(Integer)),
                func.sum(
                    case(
                        (
                            or_(
                                QuestionProgress.seen_at.is_not(None),
                                QuestionProgress.last_answered_at.is_not(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
            )
            .join(Question, Question.id == QuestionProgress.question_id)
            .where(
                QuestionProgress.user_id == user.id,
                bank.for_canton(user.canton),
                bank.servable_clause(),
            )
            .group_by(Question.topic_code)
        )
    ).all()
    counts = {code: (int(u or 0), int(k or 0), int(n or 0)) for code, u, k, n in rows}
    due_rows = (
        await db.execute(
            select(Question.topic_code, func.count(QuestionProgress.id))
            .join(Question, Question.id == QuestionProgress.question_id)
            .where(
                QuestionProgress.user_id == user.id,
                QuestionProgress.last_answered_at.is_not(None),
                QuestionProgress.due_at <= now,
                bank.for_canton(user.canton),
                bank.servable_clause(),
            )
            .group_by(Question.topic_code)
        )
    ).all()
    due = {code: int(n) for code, n in due_rows}
    out = []
    for t in topics:
        u, k, n = counts.get(t.code, (0, 0, 0))
        out.append(
            TopicState(
                topic=t,
                total=totals.get(t.code, 0),
                available=avail.get(t.code, 0),
                understood=u,
                known=k,
                seen=n,
                due=due.get(t.code, 0),
            )
        )
    return out


async def topic_mastery_for(db: AsyncSession, user: User, topic_code: str) -> int | None:
    """Mastery on one topic for the chat context, or None before the learner has studied it."""
    for s in await topic_states(db, user):
        if s.topic.code == topic_code:
            return s.mastery if s.seen else None
    return None


def readiness(states: list[TopicState]) -> int:
    """Commune topics without any question (commune questions wait for Phase 2) do not count;
    every other topic does, also before it has questions."""
    return readiness_percent(
        TopicCounts(
            topic_code=s.topic.code,
            target=s.topic.target_questions,
            total=s.total,
            understood=s.understood,
            known=s.known,
        )
        for s in states
        if not (s.topic.scope == "commune" and s.total == 0)
    )


# --- Practise ----------------------------------------------------------------------------


def _tier(p: QuestionProgress | None, now: datetime) -> int:
    if p is None or p.last_answered_at is None:
        return TIER_NEW
    if p.last_answered_at > now - RECENT_WINDOW:
        return TIER_RECENT
    if p.due_at is None or p.due_at <= now:
        return TIER_DUE
    return TIER_LATER


def plan_round(
    candidates: list[Question],
    prog: dict[str, QuestionProgress],
    mastery: dict[str, int],
    n: int,
    now: datetime,
    rng: random.Random | None = None,
) -> list[Question]:
    rng = rng or random.Random()  # noqa: S311 - ordering practice questions, not security
    queues: dict[str, list[tuple[tuple[Any, ...], Question]]] = {}
    for q in candidates:
        p = prog.get(q.id)
        tier = _tier(p, now)
        if tier == TIER_NEW:
            within: float = float(q.difficulty)
        elif p is not None and p.due_at is not None:
            within = p.due_at.timestamp()
        else:
            within = 0.0
        queues.setdefault(q.topic_code, []).append(((tier, within, rng.random()), q))
    for items in queues.values():
        items.sort(key=lambda x: x[0])
    taken = {code: 0 for code in queues}
    picked: list[Question] = []
    while len(picked) < n and any(queues.values()):
        best_tier = min(items[0][0][0] for items in queues.values() if items)
        best_code, best_score = "", -1.0
        for code, items in queues.items():
            if not items or items[0][0][0] != best_tier:
                continue
            weight = MIN_TOPIC_WEIGHT + (100 - mastery.get(code, 0)) / 100
            score = weight / (1 + taken[code])
            if score > best_score:
                best_code, best_score = code, score
        picked.append(queues[best_code].pop(0)[1])
        taken[best_code] += 1
    return picked


async def practise_round(
    db: AsyncSession, user: User, n: int, topic_code: str | None = None
) -> tuple[list[Question], int, int]:
    """Up to `n` distinct questions, and (pool size, how many the learner has never answered)."""
    cands = await accessible_questions(db, user, topic_code)
    prog = await progress.get_many(db, user.id, [q.id for q in cands])
    mastery = {s.topic.code: s.mastery for s in await topic_states(db, user)}
    picked = plan_round(cands, prog, mastery, n, clock.now())
    unseen = sum(1 for q in cands if q.id not in prog or prog[q.id].last_answered_at is None)
    return picked, len(cands), unseen
