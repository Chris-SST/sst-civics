"""Readiness check: 20 questions from the whole servable bank of the learner's canton, drawn
like the mock test (app.study.mock: scope proportions of the canton's test, spread across
topics), German only, no visible time limit, answers checked at the end. The result shows the
share right overall and per topic area (history, state and politics, society, geography,
culture), a "where you stand" level, and the questions answered wrongly with their explanation.

It is a run in `mock_runs` with `kind = readiness`. Without a pass one check a day (Swiss
day); with a pass any number. A check left open closes itself after READINESS_WINDOW and is
scored on the answers saved. Answers do not change question progress (a measurement, like the
mock test), and a check does not close Explain this or the help chat, since it is a
self-assessment and has no time limit."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RUN_READINESS, MockRun, Question
from app.study import clock, mock
from app.tutoring.limits import day_start

READINESS_QUESTIONS = 20
READINESS_MINUTES_ESTIMATE = 10  # shown on the entry card; not enforced
READINESS_WINDOW = timedelta(hours=12)

# Topic areas by the second part of the topic code (bund.<area>.…, kanton.<area>.…,
# gemeinde.<area>…). Codes not listed fall under "society".
AREAS = ("history", "politics", "society", "geography", "culture")
AREA_BY_PART = {
    "geschichte": "history",
    "demokratie": "politics",
    "international": "politics",
    "organisation": "politics",
    "einbuergerung": "politics",
    "sozial": "society",
    "alltag": "society",
    "leistungen": "society",
    "geografie": "geography",
    "kultur": "culture",
}

# "Where you stand", by the share answered correctly (percent, lowest bound first match).
LEVELS = ((80, "ready"), (60, "close"), (40, "halfway"), (0, "start"))


def area_of(topic_code: str) -> str:
    parts = topic_code.split(".")
    return AREA_BY_PART.get(parts[1] if len(parts) > 1 else "", "society")


def level_of(percent: int) -> str:
    return next(name for bound, name in LEVELS if percent >= bound)


def check_format(canton: str) -> mock.MockFormat:
    """The canton's mock-test proportions with 20 questions and no pass mark."""
    base = mock.load_format(canton)
    return mock.MockFormat(
        canton=canton,
        questions=READINESS_QUESTIONS,
        minutes=0,
        pass_mark=None,
        proportions=dict(base.proportions) if base else {},
    )


async def runs_today(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count(MockRun.id)).where(
                    MockRun.user_id == user_id,
                    MockRun.kind == RUN_READINESS,
                    MockRun.started_at >= day_start(clock.now()),
                )
            )
        ).scalar_one()
    )


async def start(db: AsyncSession, user, *, free: bool) -> MockRun:
    return await mock.start(
        db,
        user,
        check_format(user.canton),
        free=free,
        kind=RUN_READINESS,
        window=READINESS_WINDOW,
    )


def percent(right: int, total: int) -> int:
    return round(100 * right / total) if total else 0


def result(run: MockRun, questions: dict[str, Question]) -> dict[str, Any]:
    """The overall share right, the level and one row per topic area that had questions."""
    per_area: dict[str, list[int]] = {}
    for qid in run.question_ids:
        q = questions.get(qid)
        if q is None:
            continue
        row = per_area.setdefault(area_of(q.topic_code), [0, 0])
        row[1] += 1
        if (run.answers or {}).get(qid) == q.correct:
            row[0] += 1
    total = sum(t for _, t in per_area.values())
    right = sum(r for r, _ in per_area.values())
    overall = percent(right, total)
    return {
        "percent": overall,
        "level": level_of(overall),
        "areas": [
            {
                "area": a,
                "correct": per_area[a][0],
                "total": per_area[a][1],
                "percent": percent(*per_area[a]),
            }
            for a in AREAS
            if a in per_area
        ],
    }
