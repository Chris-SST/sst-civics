"""Mock test (PLAN.md, Learning app): German only, the canton's number of questions and time
limit from the `test` block of its topic file, drawn in the official proportions by scope and
spread across topics, with a deadline set by the server at the start.

Drawing: the scope quotas are `test.questions` times `test.proportions` (largest remainder, so
they add up), capped by the servable questions of each scope; a shortfall goes to the scopes
that still have questions. Within a scope, the quota is shared across topics in proportion to
their `target_questions` in the same way, so the test is spread across topics as the official
catalogue is. The final order is shuffled.

Free tier: one mock test ever without a pass (the run is marked `free`); with a pass, any
number. Answers are saved one at a time and refused after the deadline; a run whose deadline
has passed is scored on the answers saved in time.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.files import content_root
from app.content.schema import TopicFile
from app.models import (
    ATTEMPT_MOCK,
    MOCK_EXPIRED,
    MOCK_IN_PROGRESS,
    MODE_DE,
    SCOPE_CANTON,
    SCOPE_COMMUNE,
    SCOPE_FEDERAL,
    Attempt,
    MockRun,
    Question,
    User,
)
from app.questions import bank
from app.study import clock
from app.study.selection import servable_questions

# Cantons whose pass mark has been confirmed by the authority. Zurich's 30 of 50 comes from a
# press report (PLAN.md), so every result says the pass mark is unconfirmed until it is here.
CONFIRMED_PASS_MARKS: frozenset[str] = frozenset()
PASS_MARK_LABEL_KEY = "mock.passMarkUnconfirmed"  # noqa: S105 - an i18n key
SCOPE_BY_PREFIX = (
    ("bund.", SCOPE_FEDERAL),
    ("kanton.", SCOPE_CANTON),
    ("gemeinde.", SCOPE_COMMUNE),
)


class NotEnoughQuestions(Exception):
    def __init__(self, needed: int, available: int):
        super().__init__(f"{available} of {needed}")
        self.needed = needed
        self.available = available


@dataclass(frozen=True)
class MockFormat:
    canton: str
    questions: int
    minutes: int
    pass_mark: int | None
    proportions: dict[str, float] = field(default_factory=dict)

    @property
    def pass_mark_confirmed(self) -> bool:
        return self.canton in CONFIRMED_PASS_MARKS


_format_cache: dict[str, tuple[int, MockFormat | None]] = {}


def load_format(canton: str) -> MockFormat | None:
    """The `test` block of content/topics/<canton>.yaml, re-read when the file changes."""
    path: Path = content_root() / "topics" / f"{canton}.yaml"
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None
    key = str(path)
    cached = _format_cache.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        parsed = TopicFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValidationError):
        return None
    fmt = None
    if parsed.test is not None:
        fmt = MockFormat(
            canton=canton,
            questions=parsed.test.questions,
            minutes=parsed.test.minutes,
            pass_mark=parsed.test.pass_mark,
            proportions=dict(parsed.test.proportions),
        )
    _format_cache[key] = (stamp, fmt)
    return fmt


def scope_of(topic_code: str) -> str:
    for prefix, scope in SCOPE_BY_PREFIX:
        if topic_code.startswith(prefix):
            return scope
    return SCOPE_FEDERAL


def largest_remainder(total: int, weights: dict[str, float]) -> dict[str, int]:
    keys = sorted(weights)
    s = sum(max(0.0, weights[k]) for k in keys)
    if total <= 0 or s <= 0:
        return {k: 0 for k in keys}
    exact = {k: total * max(0.0, weights[k]) / s for k in keys}
    out = {k: int(exact[k]) for k in keys}
    rest = total - sum(out.values())
    for k in sorted(keys, key=lambda k: (-(exact[k] - out[k]), k))[:rest]:
        out[k] += 1
    return out


def allocate(total: int, weights: dict[str, float], caps: dict[str, int]) -> dict[str, int]:
    """Share `total` by `weights`, no key above its cap; what a capped key cannot take goes to
    the others (by weight, or by spare room when none of them has a weight)."""
    result = {k: 0 for k in caps}
    remaining = min(total, sum(caps.values()))
    active = {k for k in caps if caps[k] > 0}
    while remaining > 0 and active:
        w = {k: weights.get(k, 0.0) for k in active}
        if sum(w.values()) <= 0:
            w = {k: float(caps[k] - result[k]) for k in active}
        share = largest_remainder(remaining, w)
        for k in active:
            add = min(share[k], caps[k] - result[k])
            result[k] += add
            remaining -= add
        active = {k for k in active if caps[k] > result[k]}
    return result


async def draw(
    db: AsyncSession, canton: str, fmt: MockFormat, rng: random.Random | None = None
) -> list[str]:
    rng = rng or random.SystemRandom()
    topics = {t.code: t for t in await bank.canton_topics(db, canton)}
    by_scope: dict[str, dict[str, list[Question]]] = {}
    for q in await servable_questions(db, canton):
        by_scope.setdefault(scope_of(q.topic_code), {}).setdefault(q.topic_code, []).append(q)
    available = sum(len(qs) for topic in by_scope.values() for qs in topic.values())
    if available < fmt.questions:
        raise NotEnoughQuestions(fmt.questions, available)
    caps = {s: sum(len(qs) for qs in t.values()) for s, t in by_scope.items()}
    weights = fmt.proportions or {s: float(c) for s, c in caps.items()}
    quotas = allocate(fmt.questions, {s: float(weights.get(s, 0.0)) for s in caps}, caps)
    chosen: list[Question] = []
    for scope, per_topic in by_scope.items():
        topic_caps = {code: len(qs) for code, qs in per_topic.items()}
        topic_weights = {
            code: float(topics[code].target_questions if code in topics else 1)
            for code in per_topic
        }
        for code, k in allocate(quotas.get(scope, 0), topic_weights, topic_caps).items():
            chosen += rng.sample(per_topic[code], k)
    rng.shuffle(chosen)
    return [q.id for q in chosen]


# --- Runs ----------------------------------------------------------------------------------


async def free_runs_used(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count(MockRun.id)).where(MockRun.user_id == user_id, MockRun.free)
            )
        ).scalar_one()
    )


async def active_run(db: AsyncSession, user: User) -> MockRun | None:
    return (
        await db.execute(
            select(MockRun)
            .where(
                MockRun.user_id == user.id,
                MockRun.canton == user.canton,
                MockRun.status == MOCK_IN_PROGRESS,
            )
            .order_by(MockRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def start(db: AsyncSession, user: User, fmt: MockFormat, *, free: bool) -> MockRun:
    now = clock.now()
    ids = await draw(db, user.canton, fmt)
    run = MockRun(
        user_id=user.id,
        canton=user.canton,
        status=MOCK_IN_PROGRESS,
        question_ids=ids,
        answers={},
        minutes=fmt.minutes,
        pass_mark=fmt.pass_mark,
        free=free,
        started_at=now,
        deadline_at=now + timedelta(minutes=fmt.minutes),
    )
    db.add(run)
    await db.flush()
    return run


def is_open(run: MockRun, now: datetime | None = None) -> bool:
    return run.status == MOCK_IN_PROGRESS and (now or clock.now()) <= run.deadline_at


def score_of(run: MockRun, questions: dict[str, Question]) -> int:
    return sum(
        1
        for qid in run.question_ids
        if qid in questions and run.answers.get(qid) == questions[qid].correct
    )


async def questions_of(db: AsyncSession, run: MockRun) -> dict[str, Question]:
    rows = (await db.execute(select(Question).where(Question.id.in_(run.question_ids)))).scalars()
    return {q.id: q for q in rows}


async def finish(db: AsyncSession, run: MockRun, status: str) -> None:
    """Score the run and record one attempt per answered question. Idempotent."""
    if run.status != MOCK_IN_PROGRESS:
        return
    now = clock.now()
    questions = await questions_of(db, run)
    run.score = score_of(run, questions)
    run.status = status
    run.finished_at = min(now, run.deadline_at)
    for qid, given in (run.answers or {}).items():
        q = questions.get(qid)
        if q is None:
            continue
        db.add(
            Attempt(
                user_id=run.user_id,
                question_id=q.id,
                topic_code=q.topic_code,
                mode=ATTEMPT_MOCK,
                study_mode=MODE_DE,
                answer_text=given,
                score=1.0 if given == q.correct else 0.0,
                correct=given == q.correct,
                mock_run_id=run.id,
                created_at=run.finished_at,
            )
        )
    await db.flush()


async def expire_if_due(db: AsyncSession, run: MockRun) -> bool:
    if run.status == MOCK_IN_PROGRESS and clock.now() > run.deadline_at:
        await finish(db, run, MOCK_EXPIRED)
        return True
    return False


def passed(run: MockRun) -> bool | None:
    if run.pass_mark is None or run.score is None:
        return None
    return run.score >= run.pass_mark


def summary(run: MockRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "deadline_at": run.deadline_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "total": len(run.question_ids),
        "answered": len(run.answers or {}),
        "score": run.score,
        "pass_mark": run.pass_mark,
        "passed": passed(run),
        "free": run.free,
    }
