"""Serving questions to students: selection, diagnostics, attempts and mastery."""

from __future__ import annotations

import random
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.llm import prompts
from app.llm.client import LLMError
from app.models import (
    Q_APPROVED,
    Q_AUTO_VERIFIED,
    QTYPE_MCQ,
    QTYPE_STRUCTURED,
    Attempt,
    DiagnosticRun,
    Question,
    TopicMastery,
    User,
)
from app.questions import checks, mastery, pipeline


def servable_statuses() -> tuple[str, ...]:
    if get_settings().unreviewed_questions_allowed:
        return (Q_APPROVED, Q_AUTO_VERIFIED)
    return (Q_APPROVED,)


def topic_name(module_key: str, topic_code: str, locale: str = "en") -> str:
    info = prompts.course_info(module_key)
    topic = info.topic(topic_code) if info else None
    return topic.display(locale) if topic else topic_code


def question_public(q: Question, *, reveal: bool = False, locale: str = "en") -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(q.id),
        "module_key": q.module_key,
        "topic_code": q.topic_code,
        "topic_name": topic_name(q.module_key, q.topic_code, locale),
        "difficulty": q.difficulty,
        "qtype": q.qtype,
        "calculator_allowed": q.calculator_allowed,
        "question_text": q.question_text,
        "options": q.options if q.qtype == QTYPE_MCQ else None,
        "unit": q.unit,
        "marks": q.marks,
        "reviewed": q.status == Q_APPROVED,
    }
    if reveal:
        out["answer"] = q.answer
        out["worked_solution"] = q.worked_solution
    return out


async def _candidates(
    db: AsyncSession,
    *,
    module_key: str,
    level: str | None,
    topic_code: str | None,
    language: str,
    exclude: set[uuid.UUID],
) -> list[Question]:
    stmt = select(Question).where(
        Question.module_key == module_key, Question.status.in_(servable_statuses())
    )
    if level:
        stmt = stmt.where(Question.level.in_((level, "both")))
    if topic_code:
        stmt = stmt.where(Question.topic_code == topic_code)
    rows = list((await db.execute(stmt)).scalars().all())
    rows = [q for q in rows if q.id not in exclude]
    in_lang = [q for q in rows if q.language == language]
    return in_lang or [q for q in rows if q.language == "en"] or rows


async def recently_attempted(
    db: AsyncSession, student_id: uuid.UUID, limit: int = 40
) -> set[uuid.UUID]:
    rows = (
        await db.execute(
            select(Attempt.question_id)
            .where(Attempt.student_id == student_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return set(rows)


async def topic_history(
    db: AsyncSession, student_id: uuid.UUID, topic_code: str
) -> dict[uuid.UUID, tuple[Any, bool]]:
    """Latest attempt per question on this topic: question id -> (when, correct)."""
    rows = (
        await db.execute(
            select(Attempt.question_id, Attempt.created_at, Attempt.correct)
            .where(Attempt.student_id == student_id, Attempt.topic_code == topic_code)
            .order_by(Attempt.created_at.asc())
        )
    ).all()
    return {qid: (at, bool(ok)) for qid, at, ok in rows}


def _closest(cands: list[Question], difficulty: int, n: int) -> list[Question]:
    random.shuffle(cands)
    cands.sort(key=lambda q: abs(q.difficulty - difficulty))
    return cands[:n]


# --- Diagnostic ------------------------------------------------------------------------------


async def build_diagnostic(db: AsyncSession, student: User, course_key: str) -> DiagnosticRun:
    module = prompts.course_module_key(course_key)
    level = prompts.course_level(course_key)
    info = prompts.course_info(module)
    per_topic = get_settings().diagnostic_questions_per_topic
    chosen: list[str] = []
    seen = await recently_attempted(db, student.id)
    if info:
        for topic in info.topics_for(level):
            if topic.code.endswith("-EX"):
                continue
            cands = await _candidates(
                db,
                module_key=module,
                level=level,
                topic_code=topic.code,
                language=student.locale,
                exclude=seen,
            )
            picked: list[Question] = []
            for target in (2, 4)[:per_topic]:
                pool = [q for q in cands if q not in picked]
                picked += _closest(pool, target, 1)
            chosen += [str(q.id) for q in picked]
    run = DiagnosticRun(
        student_id=student.id,
        course_key=course_key,
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
    return await db.get(Question, uuid.UUID(run.question_ids[run.position]))


async def latest_diagnostic(
    db: AsyncSession, student_id: uuid.UUID, course_key: str
) -> DiagnosticRun | None:
    return (
        await db.execute(
            select(DiagnosticRun)
            .where(DiagnosticRun.student_id == student_id, DiagnosticRun.course_key == course_key)
            .order_by(DiagnosticRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


# --- Practice and check questions ------------------------------------------------------------


async def select_questions(
    db: AsyncSession, student: User, course_key: str, topic_code: str, n: int = 1
) -> tuple[list[Question], int, int]:
    """Up to `n` distinct questions on a topic, and (pool size, how many are new to the student).

    Questions the student has never attempted come first, nearest the target difficulty. When
    those run out, earlier questions return: the ones answered wrong first, then the ones seen
    longest ago, so the question just answered is the very last to come back.
    """
    module = prompts.course_module_key(course_key)
    level = prompts.course_level(course_key)
    m = await mastery.get_or_create(db, student.id, course_key, topic_code)
    target = mastery.target_difficulty(m.rating)
    cands = await _candidates(
        db,
        module_key=module,
        level=level,
        topic_code=topic_code,
        language=student.locale,
        exclude=set(),
    )
    history = await topic_history(db, student.id, topic_code)
    unseen = [q for q in cands if q.id not in history]
    picked = _closest(unseen, target, n)
    if len(picked) < n:
        seen = [q for q in cands if q.id in history]
        seen.sort(key=lambda q: (history[q.id][1], history[q.id][0]))
        picked += seen[: n - len(picked)]
    return picked, len(cands), len(unseen)


async def next_question(
    db: AsyncSession, student: User, course_key: str, topic_code: str, n: int = 1
) -> list[Question]:
    picked, _, _ = await select_questions(db, student, course_key, topic_code, n)
    return picked


# --- Attempts ----------------------------------------------------------------------------------


async def submit_attempt(
    db: AsyncSession,
    *,
    student: User,
    question: Question,
    course_key: str,
    answer_text: str,
    mode: str,
    conversation_id: uuid.UUID | None = None,
    diagnostic_id: uuid.UUID | None = None,
) -> Attempt:
    ai_marked = False
    feedback: str | None = None
    if question.qtype == QTYPE_STRUCTURED:
        try:
            score, feedback, correct = await pipeline.mark_structured(
                db, question, answer_text, student.id
            )
            ai_marked = True
        except LLMError:
            # Marking unavailable: record the attempt without a score so it is not counted
            # against the student. The solution is shown and mastery is left unchanged.
            score, correct, feedback = 0.0, False, None
            attempt = Attempt(
                student_id=student.id,
                question_id=question.id,
                course_key=course_key,
                topic_code=question.topic_code,
                mode=mode,
                answer_text=answer_text,
                score=0.0,
                correct=False,
                feedback=None,
                ai_marked=False,
                conversation_id=conversation_id,
                diagnostic_id=diagnostic_id,
            )
            db.add(attempt)
            await db.flush()
            return attempt
    else:
        outcome = checks.check_answer(
            question.qtype, answer_text, question.answer, question.tolerance
        )
        score, correct = (1.0 if outcome.correct else 0.0), outcome.correct
    attempt = Attempt(
        student_id=student.id,
        question_id=question.id,
        course_key=course_key,
        topic_code=question.topic_code,
        mode=mode,
        answer_text=answer_text,
        score=score,
        correct=correct,
        feedback=feedback,
        ai_marked=ai_marked,
        conversation_id=conversation_id,
        diagnostic_id=diagnostic_id,
    )
    db.add(attempt)
    await mastery.record_result(
        db, student.id, course_key, question.topic_code, question.difficulty, score
    )
    await db.flush()
    return attempt


# --- Overview -----------------------------------------------------------------------------------


async def mastery_overview(
    db: AsyncSession, student: User, course_key: str
) -> list[dict[str, Any]]:
    module = prompts.course_module_key(course_key)
    level = prompts.course_level(course_key)
    info = prompts.course_info(module)
    if info is None:
        return []
    rows = {
        r.topic_code: r
        for r in (
            await db.execute(
                select(TopicMastery).where(
                    TopicMastery.student_id == student.id, TopicMastery.course_key == course_key
                )
            )
        )
        .scalars()
        .all()
    }
    counts = dict(
        (
            await db.execute(
                select(Question.topic_code, func.count(Question.id))
                .where(Question.module_key == module, Question.status.in_(servable_statuses()))
                .group_by(Question.topic_code)
            )
        ).all()
    )
    now = utcnow()
    out = []
    for topic in info.topics_for(level):
        if topic.code.endswith("-EX"):
            continue
        m = rows.get(topic.code)
        out.append(
            {
                "topic_code": topic.code,
                "topic_name": topic.display(student.locale),
                "mastery": mastery.mastery_percent(m.rating) if m else None,
                "attempts": m.attempts if m else 0,
                "due": bool(m and m.next_review_at and m.next_review_at <= now),
                "questions_available": int(counts.get(topic.code, 0)),
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
    db: AsyncSession, student_id: uuid.UUID, course_key: str, topic_code: str, limit: int = 3
) -> list[dict[str, str]]:
    """What the student got wrong on this topic, for the tutor's session context. No names."""
    rows = (
        await db.execute(
            select(Attempt, Question)
            .join(Question, Question.id == Attempt.question_id)
            .where(
                Attempt.student_id == student_id,
                Attempt.course_key == course_key,
                Attempt.topic_code == topic_code,
                Attempt.correct.is_(False),
            )
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "question": q.question_text[:600],
            "student_answer": a.answer_text[:300],
            "correct_answer": q.answer[:200],
        }
        for a, q in rows
    ]
