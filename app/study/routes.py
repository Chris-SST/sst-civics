"""Learner study API: overview with mastery and readiness, one question in a study mode,
Learn, Practise, answers, the check questions after a chat, and the mock test.

Without a pass (free tier) Learn and Practise serve the canton's sample set only
(app.study.selection) and one mock test may be taken; with a pass, everything servable and any
number of mock tests."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.config import get_settings
from app.db import get_db
from app.deps import require_learner
from app.models import (
    ATTEMPT_CHECK,
    ATTEMPT_PRACTICE,
    MOCK_FINISHED,
    MODE_OWN,
    Attempt,
    Conversation,
    GlossaryTerm,
    MockRun,
    Question,
    QuestionTranslation,
    User,
)
from app.questions import bank, checks
from app.questions.mastery import READINESS_LABEL_KEY
from app.study import clock, mock, modes, progress, selection

router = APIRouter(prefix="/api/study", tags=["study"])
mock_router = APIRouter(prefix="/api/mock", tags=["mock"])

StudyMode = Literal["own", "side", "help", "de"]
MAX_ROUND = 20


class ModeIn(BaseModel):
    mode: StudyMode


class AnswerIn(BaseModel):
    question_id: str = Field(max_length=80)
    answer: str = Field(max_length=20)
    # The mode the question was shown in; the stored mode when left out.
    mode: StudyMode | None = None
    context: Literal["practise", "check"] = "practise"
    conversation_id: uuid.UUID | None = None


class MockAnswerIn(BaseModel):
    question_id: str = Field(max_length=80)
    answer: str = Field(max_length=20)


# --- Helpers -----------------------------------------------------------------------------


class Renderer:
    """Renders many questions for one learner with one glossary and topic-name lookup."""

    def __init__(self, user: User, glossary: list[GlossaryTerm], names: dict[str, str]):
        self.user = user
        self.glossary = glossary
        self.names = names
        self.translations: dict[str, QuestionTranslation] = {}

    @classmethod
    async def create(cls, db: AsyncSession, user: User) -> Renderer:
        glossary = await modes.glossary_for(db, user.study_language)
        names = await bank.topic_names(db, user.canton, user.locale)
        return cls(user, glossary, names)

    async def load(self, db: AsyncSession, questions: list[Question]) -> Renderer:
        ids = [q.id for q in questions if q.id not in self.translations]
        self.translations.update(await modes.translations_for(db, ids, self.user.study_language))
        return self

    def render(self, q: Question, mode: str, *, reveal: bool = False) -> dict[str, Any]:
        return modes.render(
            q,
            mode=mode,
            study_language=self.user.study_language,
            translation=self.translations.get(q.id),
            glossary=self.glossary,
            topic_name=self.names.get(q.topic_code),
            reveal=reveal,
        )


async def _question_for(db: AsyncSession, user: User, question_id: str) -> Question:
    q = await db.get(Question, question_id)
    if q is None or not selection.servable_for(q, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not await selection.can_study(db, user, q):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sample_only")
    return q


def _topic_out(s: selection.TopicState, locale: str) -> dict[str, Any]:
    t = s.topic
    return {
        "topic_code": t.code,
        "topic_name": t.display(locale),
        "name_de": t.name_de,
        "name_en": t.name_en,
        "scope": t.scope,
        "target_questions": t.target_questions,
        "questions_total": s.total,
        "questions_available": s.available,
        "seen": s.seen,
        "understood": s.understood,
        "known": s.known,
        "due": s.due,
        "mastery": s.mastery,
    }


def _readiness_out(states: list[selection.TopicState]) -> dict[str, Any]:
    return {"value": selection.readiness(states), "label_key": READINESS_LABEL_KEY}


async def _mock_info(db: AsyncSession, user: User) -> dict[str, Any]:
    fmt = mock.load_format(user.canton)
    paid = selection.full_access(user)
    free_used = await mock.free_runs_used(db, user.id)
    run = await mock.active_run(db, user)
    if run is not None and await mock.expire_if_due(db, run):
        await db.commit()
        run = None
    last = (
        await db.execute(
            select(MockRun)
            .where(MockRun.user_id == user.id, MockRun.status != "in_progress")
            .order_by(MockRun.started_at.desc())
            .limit(5)
        )
    ).scalars()
    available = 0
    if fmt is not None:
        available = len(await selection.servable_questions(db, user.canton))
    return {
        "configured": fmt is not None,
        "questions": fmt.questions if fmt else None,
        "minutes": fmt.minutes if fmt else None,
        "pass_mark": fmt.pass_mark if fmt else None,
        "pass_mark_confirmed": fmt.pass_mark_confirmed if fmt else False,
        "pass_mark_label_key": mock.PASS_MARK_LABEL_KEY,
        "enough_questions": fmt is not None and available >= fmt.questions,
        "paid": paid,
        "free_mock_used": free_used > 0,
        "can_start": run is not None or paid or free_used == 0,
        "active_run_id": str(run.id) if run else None,
        "recent": [mock.summary(r) for r in last],
    }


# --- Overview ----------------------------------------------------------------------------


@router.get("/overview")
async def overview(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    states = await selection.topic_states(db, user)
    paid = selection.full_access(user)
    return {
        "canton": user.canton,
        "study_language": user.study_language,
        "free_tier": not paid,
        "sample_size": selection.SAMPLE_SIZE,
        "questions_total": sum(s.total for s in states),
        "questions_available": sum(s.available for s in states),
        "topics": [_topic_out(s, user.locale) for s in states],
        "readiness": _readiness_out(states),
        "due": sum(s.due for s in states),
        "mock": await _mock_info(db, user),
    }


# --- One question in a study mode ----------------------------------------------------------


@router.get("/question/{question_id}")
async def get_question(
    question_id: str,
    mode: StudyMode | None = None,
    reveal: bool = False,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The question as the mode shows it; the learner's stored mode when `mode` is left out."""
    q = await _question_for(db, user, question_id)
    p = (await progress.get_many(db, user.id, [q.id])).get(q.id)
    r = await (await Renderer.create(db, user)).load(db, [q])
    out = r.render(q, mode or progress.current_mode(p), reveal=reveal)
    out["progress"] = progress.progress_out(p)
    return out


@router.post("/question/{question_id}/mode")
async def set_mode(
    question_id: str,
    body: ModeIn,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Store the learner's mode for this question (a step back, or forward) and render it."""
    q = await _question_for(db, user, question_id)
    p = await progress.get_or_create(db, user.id, q.id)
    progress.set_mode(p, body.mode)
    await db.commit()
    r = await (await Renderer.create(db, user)).load(db, [q])
    out = r.render(q, p.mode)
    out["progress"] = progress.progress_out(p)
    return out


@router.post("/question/{question_id}/seen")
async def mark_seen(
    question_id: str, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    q = await _question_for(db, user, question_id)
    p = await progress.get_or_create(db, user.id, q.id)
    p.seen_at = clock.now()
    await db.commit()
    return {"ok": True, "progress": progress.progress_out(p)}


# --- Learn ---------------------------------------------------------------------------------


@router.get("/learn")
async def learn(
    topic_code: str = Query(max_length=80),
    mode: StudyMode = MODE_OWN,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Every card of one topic with the correct answer and explanation in the chosen mode.
    No scoring; the page marks each card seen as the learner moves through them."""
    topic = await bank.get_topic(db, user.canton, topic_code)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    qs = sorted(
        await selection.accessible_questions(db, user, topic_code),
        key=lambda q: (q.difficulty, q.id),
    )
    prog = await progress.get_many(db, user.id, [q.id for q in qs])
    r = await (await Renderer.create(db, user)).load(db, qs)
    cards = []
    for q in qs:
        card = r.render(q, mode, reveal=True)
        card["progress"] = progress.progress_out(prog.get(q.id))
        cards.append(card)
    return {
        "topic_code": topic.code,
        "topic_name": topic.display(user.locale),
        "scope": topic.scope,
        "mode": mode,
        "free_tier": not selection.full_access(user),
        "cards": cards,
    }


# --- Practise ------------------------------------------------------------------------------


@router.get("/practise")
async def practise(
    topic_code: str | None = Query(default=None, max_length=80),
    n: int | None = Query(default=None, ge=1, le=MAX_ROUND),
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A round of distinct questions chosen by the spaced-repetition schedule, weighted towards
    weak topics; each in the learner's stored mode for it. One topic when `topic_code` is set."""
    topic = None
    if topic_code is not None:
        topic = await bank.get_topic(db, user.canton, topic_code)
        if topic is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    size = n or get_settings().practice_round_size
    qs, pool, unseen = await selection.practise_round(db, user, size, topic_code)
    if not qs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_questions")
    prog = await progress.get_many(db, user.id, [q.id for q in qs])
    r = await (await Renderer.create(db, user)).load(db, qs)
    states = await selection.topic_states(db, user)
    by_code = {s.topic.code: s for s in states}
    questions = []
    for q in qs:
        item = r.render(q, progress.current_mode(prog.get(q.id)))
        item["progress"] = progress.progress_out(prog.get(q.id))
        state = by_code.get(q.topic_code)
        item["topic_mastery"] = state.mastery if state else 0
        questions.append(item)
    return {
        "topic_code": topic.code if topic else None,
        "topic_name": topic.display(user.locale) if topic else None,
        "mastery": by_code[topic.code].mastery if topic and topic.code in by_code else None,
        "readiness": _readiness_out(states),
        "free_tier": not selection.full_access(user),
        "pool": pool,
        "unseen": unseen,
        "questions": questions,
    }


@router.post("/answer")
async def answer(
    body: AnswerIn, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    if body.context == "check":
        if body.conversation_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "conversation_required")
        conv = await db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    q = await _question_for(db, user, body.question_id)
    p = await progress.get_or_create(db, user.id, q.id)
    tr = (await modes.translations_for(db, [q.id], user.study_language)).get(q.id)
    shown, _ = modes.effective_mode(
        body.mode or progress.current_mode(p),
        user.study_language,
        modes.translation_usable(q, tr),
    )
    before = {s.topic.code: s.mastery for s in await selection.topic_states(db, user)}
    correct = checks.check_answer(body.answer, q.correct).correct
    now = clock.now()
    change = progress.apply_answer(
        p, mode=shown, correct=correct, study_language=user.study_language, now=now
    )
    attempt = Attempt(
        user_id=user.id,
        question_id=q.id,
        topic_code=q.topic_code,
        mode=ATTEMPT_CHECK if body.context == "check" else ATTEMPT_PRACTICE,
        study_mode=shown,
        answer_text=body.answer[:20],
        score=1.0 if correct else 0.0,
        correct=correct,
        conversation_id=body.conversation_id if body.context == "check" else None,
        created_at=now,
    )
    db.add(attempt)
    await db.flush()
    states = await selection.topic_states(db, user)
    after = {s.topic.code: s.mastery for s in states}
    usable = modes.translation_usable(q, tr)
    out = {
        "attempt_id": str(attempt.id),
        "correct": correct,
        "score": attempt.score,
        "mode": shown,
        "answer": q.correct,
        "answer_text": q.options_de.get(q.correct),
        "answer_text_translated": tr.options.get(q.correct) if usable and tr else None,
        "explanation": modes.explanation_for(q, tr, user.study_language),
        "explanation_de": q.explanation_de,
        "progress": change,
        "mastery": {
            "topic_code": q.topic_code,
            "mastery": after.get(q.topic_code, 0),
            "previous": before.get(q.topic_code, 0),
        },
        "readiness": _readiness_out(states),
    }
    await db.commit()
    return out


@router.get("/check")
async def check_questions(
    conversation_id: uuid.UUID,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Two or three questions on a chat's topic, to check what was learnt."""
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not has_access(user, user.canton):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
    qs, _, _ = await selection.practise_round(db, user, 3, conv.topic_code)
    prog = await progress.get_many(db, user.id, [q.id for q in qs])
    r = await (await Renderer.create(db, user)).load(db, qs)
    return {
        "conversation_id": str(conv.id),
        "topic_code": conv.topic_code,
        "questions": [r.render(q, progress.current_mode(prog.get(q.id))) for q in qs],
    }


# --- Mock test -------------------------------------------------------------------------------


async def _own_run(db: AsyncSession, user: User, run_id: uuid.UUID) -> MockRun:
    run = await db.get(MockRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return run


async def _run_out(db: AsyncSession, user: User, run: MockRun) -> dict[str, Any]:
    out = mock.summary(run)
    out["now"] = clock.now().isoformat()
    out["minutes"] = run.minutes
    out["pass_mark_confirmed"] = run.canton in mock.CONFIRMED_PASS_MARKS
    out["pass_mark_label_key"] = mock.PASS_MARK_LABEL_KEY
    questions = await mock.questions_of(db, run)
    r = Renderer(user, [], await bank.topic_names(db, user.canton, user.locale))
    if run.status == "in_progress":
        # German only, as in the test: no translation, no help, no answer, no explanation.
        out["seconds_left"] = max(0, int((run.deadline_at - clock.now()).total_seconds()))
        out["answers"] = run.answers or {}
        out["questions"] = [
            {
                "id": qid,
                "question": questions[qid].question_de,
                "options": [
                    {"key": k, "text": questions[qid].options_de.get(k, "")} for k in "abcd"
                ],
            }
            for qid in run.question_ids
            if qid in questions
        ]
        return out
    # Afterwards: every wrong or unanswered question in the learner's language with the
    # explanation (German when no translation is approved).
    wrong = [
        questions[qid]
        for qid in run.question_ids
        if qid in questions and (run.answers or {}).get(qid) != questions[qid].correct
    ]
    r.glossary = await modes.glossary_for(db, user.study_language)
    await r.load(db, wrong)
    review = []
    for q in wrong:
        item = r.render(q, MODE_OWN, reveal=True)
        item["given"] = (run.answers or {}).get(q.id)
        review.append(item)
    out["review"] = review
    return out


@mock_router.get("")
async def mock_info(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await _mock_info(db, user)


@mock_router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_mock(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Start a mock test, or return the one still running."""
    run = await mock.active_run(db, user)
    if run is not None and await mock.expire_if_due(db, run):
        await db.commit()
        run = None
    if run is not None:
        return await _run_out(db, user, run)
    fmt = mock.load_format(user.canton)
    if fmt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_mock_test")
    paid = selection.full_access(user)
    if not paid:
        if user.email_verified_at is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "email_not_verified")
        if await mock.free_runs_used(db, user.id) > 0:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "free_mock_used")
    try:
        run = await mock.start(db, user, fmt, free=not paid)
    except mock.NotEnoughQuestions as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_enough_questions") from exc
    await db.commit()
    return await _run_out(db, user, run)


@mock_router.get("/{run_id}")
async def get_mock(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await _own_run(db, user, run_id)
    if await mock.expire_if_due(db, run):
        await db.commit()
    return await _run_out(db, user, run)


@mock_router.post("/{run_id}/answer")
async def answer_mock(
    run_id: uuid.UUID,
    body: MockAnswerIn,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Save (or change) one answer. Refused once the deadline has passed or the test is in."""
    run = await _own_run(db, user, run_id)
    if run.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "mock_finished")
    if not mock.is_open(run):
        await mock.expire_if_due(db, run)
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "deadline_passed")
    if body.question_id not in run.question_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    key = checks.option_key(body.answer)
    if not key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_answer")
    run.answers = {**(run.answers or {}), body.question_id: key}
    await db.commit()
    return {
        "ok": True,
        "answered": len(run.answers),
        "seconds_left": max(0, int((run.deadline_at - clock.now()).total_seconds())),
    }


@mock_router.post("/{run_id}/finish")
async def finish_mock(
    run_id: uuid.UUID, user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    run = await _own_run(db, user, run_id)
    if not await mock.expire_if_due(db, run):
        await mock.finish(db, run, MOCK_FINISHED)
    await db.commit()
    return await _run_out(db, user, run)
