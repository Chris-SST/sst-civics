"""Serving questions to learners: topics of a canton, selection, diagnostics, attempts and
mastery. Questions shown to a learner are the federal ones and those of the learner's canton;
commune-specific questions wait until the app knows a learner's commune (Phase 2)."""

from __future__ import annotations

import random
import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.models import (
    Q_APPROVED,
    Q_IN_REVIEW,
    Attempt,
    DiagnosticRun,
    Question,
    Topic,
    TopicMastery,
    User,
)
from app.questions import checks, mastery

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


def question_public(
    q: Question, *, topic_name: str | None = None, reveal: bool = False
) -> dict[str, Any]:
    """The German question with its four options, without the answer unless `reveal`."""
    out: dict[str, Any] = {
        "id": q.id,
        "topic_code": q.topic_code,
        "topic_name": topic_name or q.topic_code,
        "difficulty": q.difficulty,
        "question_text": q.question_de,
        "options": q.options_list(),
        "reviewed": q.status == Q_APPROVED,
    }
    if reveal:
        out["answer"] = q.correct
        out["explanation"] = q.explanation_de
    return out


async def _candidates(
    db: AsyncSession, *, canton: str, topic_code: str | None, exclude: set[str]
) -> list[Question]:
    stmt = select(Question).where(for_canton(canton), servable_clause())
    if topic_code:
        stmt = stmt.where(Question.topic_code == topic_code)
    rows = list((await db.execute(stmt)).scalars().all())
    return [q for q in rows if q.id not in exclude]


async def recently_attempted(db: AsyncSession, user_id: uuid.UUID, limit: int = 40) -> set[str]:
    rows = (
        await db.execute(
            select(Attempt.question_id)
            .where(Attempt.user_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return set(rows)


async def topic_history(
    db: AsyncSession, user_id: uuid.UUID, topic_code: str
) -> dict[str, tuple[int, bool]]:
    """Latest attempt per question on this topic: question id -> (order, correct), where a
    higher order means answered more recently."""
    rows = (
        await db.execute(
            select(Attempt.question_id, Attempt.correct)
            .where(Attempt.user_id == user_id, Attempt.topic_code == topic_code)
            .order_by(Attempt.created_at.asc())
        )
    ).all()
    return {qid: (i, bool(ok)) for i, (qid, ok) in enumerate(rows)}


def _closest(cands: list[Question], difficulty: int, n: int) -> list[Question]:
    random.shuffle(cands)
    cands.sort(key=lambda q: abs(q.difficulty - difficulty))
    return cands[:n]


# --- Diagnostic ------------------------------------------------------------------------------


async def build_diagnostic(db: AsyncSession, learner: User) -> DiagnosticRun:
    per_topic = get_settings().diagnostic_questions_per_topic
    chosen: list[str] = []
    seen = await recently_attempted(db, learner.id)
    for topic in await canton_topics(db, learner.canton):
        cands = await _candidates(db, canton=learner.canton, topic_code=topic.code, exclude=seen)
        picked: list[Question] = []
        for target in (2, 3)[:per_topic]:
            pool = [q for q in cands if q not in picked]
            picked += _closest(pool, target, 1)
        chosen += [q.id for q in picked]
    run = DiagnosticRun(
        user_id=learner.id,
        canton=learner.canton,
        question_ids=chosen,
        status="in_progress" if chosen else "done",
        completed_at=None if chosen else utcnow(),
    )
    db.add(run)
    await db.flush()
    return run


async def diagnostic_current(db: AsyncSession, run: DiagnosticRun) -> Question | None:
    if run.status != "in_progress" or run.position >= len(run.question_ids):
        return None
    return await db.get(Question, run.question_ids[run.position])


async def latest_diagnostic(
    db: AsyncSession, user_id: uuid.UUID, canton: str
) -> DiagnosticRun | None:
    return (
        await db.execute(
            select(DiagnosticRun)
            .where(DiagnosticRun.user_id == user_id, DiagnosticRun.canton == canton)
            .order_by(DiagnosticRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


# --- Practice and check questions ------------------------------------------------------------


async def select_questions(
    db: AsyncSession, learner: User, topic_code: str, n: int = 1
) -> tuple[list[Question], int, int]:
    """Up to `n` distinct questions on a topic, and (pool size, how many are new to the learner).

    Questions the learner has never attempted come first, nearest the target difficulty. When
    those run out, earlier questions return: the ones answered wrong first, then the ones seen
    longest ago, so the question just answered is the very last to come back.
    """
    m = await mastery.get_or_create(db, learner.id, topic_code)
    target = mastery.target_difficulty(m.rating)
    cands = await _candidates(db, canton=learner.canton, topic_code=topic_code, exclude=set())
    history = await topic_history(db, learner.id, topic_code)
    unseen = [q for q in cands if q.id not in history]
    picked = _closest(unseen, target, n)
    if len(picked) < n:
        seen = [q for q in cands if q.id in history]
        seen.sort(key=lambda q: (history[q.id][1], history[q.id][0]))
        picked += seen[: n - len(picked)]
    return picked, len(cands), len(unseen)


async def next_question(
    db: AsyncSession, learner: User, topic_code: str, n: int = 1
) -> list[Question]:
    picked, _, _ = await select_questions(db, learner, topic_code, n)
    return picked


# --- Attempts ----------------------------------------------------------------------------------


async def submit_attempt(
    db: AsyncSession,
    *,
    learner: User,
    question: Question,
    answer_text: str,
    mode: str,
    conversation_id: uuid.UUID | None = None,
    diagnostic_id: uuid.UUID | None = None,
) -> Attempt:
    outcome = checks.check_answer(answer_text, question.correct)
    score, correct = (1.0 if outcome.correct else 0.0), outcome.correct
    attempt = Attempt(
        user_id=learner.id,
        question_id=question.id,
        topic_code=question.topic_code,
        mode=mode,
        answer_text=answer_text[:20],
        score=score,
        correct=correct,
        conversation_id=conversation_id,
        diagnostic_id=diagnostic_id,
    )
    db.add(attempt)
    await mastery.record_result(db, learner.id, question.topic_code, question.difficulty, score)
    await db.flush()
    return attempt


# --- Overview -----------------------------------------------------------------------------------


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


async def mastery_overview(db: AsyncSession, learner: User) -> list[dict[str, Any]]:
    """Every topic of the learner's canton, in file order, with mastery and question counts."""
    rows = {
        r.topic_code: r
        for r in (await db.execute(select(TopicMastery).where(TopicMastery.user_id == learner.id)))
        .scalars()
        .all()
    }
    counts = await question_counts(db, learner.canton, servable_clause())
    now = utcnow()
    out = []
    for topic in await canton_topics(db, learner.canton):
        m = rows.get(topic.code)
        out.append(
            {
                "topic_code": topic.code,
                "topic_name": topic.display(learner.locale),
                "name_de": topic.name_de,
                "name_en": topic.name_en,
                "scope": topic.scope,
                "mastery": mastery.mastery_percent(m.rating) if m else None,
                "attempts": m.attempts if m else 0,
                "due": bool(m and m.next_review_at and m.next_review_at <= now),
                "questions_available": counts.get(topic.code, 0),
            }
        )
    return out


def suggest_next(overview: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Weakest tested topics first, then topics due for review, then untested ones."""
    tested = [t for t in overview if t["mastery"] is not None and t["questions_available"]]
    tested.sort(key=lambda t: (not t["due"], t["mastery"]))
    untested = [t for t in overview if t["mastery"] is None and t["questions_available"]]
    return (tested + untested)[:limit]


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
