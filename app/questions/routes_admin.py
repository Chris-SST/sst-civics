"""Review and generation API for admins. Reviewer scopes arrive in Phase 1."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.deps import require_admin
from app.jobs import enqueue
from app.llm import prompts
from app.models import (
    Q_APPROVED,
    Q_AUTO_VERIFIED,
    Q_NEEDS_REVIEW,
    Q_RETIRED,
    QUESTION_STATUSES,
    QUESTION_TYPES,
    AuditLog,
    GenerationBatch,
    Question,
    QuestionReport,
    User,
)
from app.questions import pipeline

router = APIRouter(prefix="/api/review", tags=["review"])

AVAILABLE_MODULES = ("ib_maths_aa", "ib_maths_ai", "ib_physics")


class GenerateIn(BaseModel):
    module_key: str
    level: Literal["sl", "hl", "both"] = "both"
    topic_codes: list[str] = Field(min_length=1, max_length=40)
    difficulties: list[int] = Field(default_factory=lambda: [2, 3, 4], min_length=1, max_length=5)
    per_request: int = Field(default=5, ge=1, le=10)
    language: Literal["en", "de", "fr"] = "en"
    mode: Literal["batch", "direct"] = "batch"


class QuestionEdits(BaseModel):
    question_text: str | None = None
    options: list[dict[str, str]] | None = None
    answer: str | None = None
    unit: str | None = None
    tolerance: float | None = None
    worked_solution: str | None = None
    mark_scheme: str | None = None
    marks: int | None = Field(default=None, ge=1, le=12)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic_code: str | None = None
    qtype: str | None = None
    calculator_allowed: bool | None = None
    level: Literal["sl", "hl", "both"] | None = None


class ReviewIn(BaseModel):
    action: Literal["approve", "retire", "needs_review"]
    edits: QuestionEdits | None = None
    note: str | None = Field(default=None, max_length=2000)
    minutes: int = Field(default=3, ge=0, le=120)


def _modules_for(user: User) -> set[str]:
    """Admins review every module. Reviewer scopes arrive in Phase 1 (D-009)."""
    return set(AVAILABLE_MODULES)


def _check_module(user: User, module_key: str) -> None:
    if module_key not in _modules_for(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")


def _question_full(q: Question) -> dict[str, Any]:
    return {
        "id": str(q.id),
        "module_key": q.module_key,
        "level": q.level,
        "topic_code": q.topic_code,
        "difficulty": q.difficulty,
        "qtype": q.qtype,
        "calculator_allowed": q.calculator_allowed,
        "language": q.language,
        "question_text": q.question_text,
        "options": q.options,
        "answer": q.answer,
        "unit": q.unit,
        "tolerance": q.tolerance,
        "worked_solution": q.worked_solution,
        "mark_scheme": q.mark_scheme,
        "marks": q.marks,
        "status": q.status,
        "spot_check": q.spot_check,
        "source": q.source,
        "prompt_version": q.prompt_version,
        "check_results": q.check_results,
        "solve_answer": q.solve_answer,
        "review_note": q.review_note,
        "reviewed_at": q.reviewed_at,
        "report_count": q.report_count,
        "created_at": q.created_at,
    }


@router.get("/modules")
async def modules(user: User = Depends(require_admin)) -> list[dict[str, Any]]:
    out = []
    for key in sorted(_modules_for(user)):
        info = prompts.course_info(key)
        if info is None:
            continue
        out.append(
            {
                "module_key": key,
                "name": info.display(user.locale),
                "topics": [
                    {"code": t.code, "name": t.display(user.locale), "levels": list(t.levels)}
                    for t in info.topics
                    if not t.code.endswith("-EX")
                ],
            }
        )
    return out


@router.get("/queue")
async def queue(
    module_key: str | None = None,
    q_status: str | None = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    allowed = _modules_for(user)
    if module_key:
        _check_module(user, module_key)
        allowed = {module_key}
    stmt = select(Question).where(Question.module_key.in_(allowed))
    if q_status in QUESTION_STATUSES:
        stmt = stmt.where(Question.status == q_status)
    else:
        # The review queue: everything an admin should look at
        stmt = stmt.where(
            (Question.status == Q_NEEDS_REVIEW)
            | ((Question.status == Q_AUTO_VERIFIED) & Question.spot_check.is_(True))
        )
    rows = (await db.execute(stmt.order_by(Question.created_at).limit(200))).scalars().all()
    return [_question_full(q) for q in rows]


@router.get("/questions/{question_id}")
async def get_question(
    question_id: uuid.UUID, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _check_module(user, q.module_key)
    return _question_full(q)


@router.patch("/questions/{question_id}")
async def review_question(
    question_id: uuid.UUID,
    body: ReviewIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _check_module(user, q.module_key)
    if body.edits:
        for field_name, value in body.edits.model_dump(exclude_none=True).items():
            if field_name == "qtype" and value not in QUESTION_TYPES:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_qtype")
            setattr(q, field_name, value)
    q.status = {"approve": Q_APPROVED, "retire": Q_RETIRED, "needs_review": Q_NEEDS_REVIEW}[
        body.action
    ]
    q.spot_check = False
    q.reviewer_id = user.id
    q.reviewed_at = utcnow()
    q.review_note = body.note
    q.review_minutes += body.minutes
    if body.action == "approve":
        for report in (
            await db.execute(
                select(QuestionReport).where(
                    QuestionReport.question_id == q.id, QuestionReport.resolved_at.is_(None)
                )
            )
        ).scalars():
            report.resolved_at = utcnow()
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=f"question.{body.action}",
            target_type="question",
            target_id=str(q.id),
            meta={"minutes": body.minutes, "edited": bool(body.edits)},
        )
    )
    await db.commit()
    await db.refresh(q)
    return _question_full(q)


@router.get("/stats")
async def stats(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    allowed = _modules_for(user)
    rows = (
        await db.execute(
            select(
                Question.module_key, Question.topic_code, Question.status, func.count(Question.id)
            )
            .where(Question.module_key.in_(allowed))
            .group_by(Question.module_key, Question.topic_code, Question.status)
        )
    ).all()
    by_module: dict[str, dict[str, Any]] = {}
    for module_key, topic, st, n in rows:
        m = by_module.setdefault(
            module_key, {"module_key": module_key, "by_status": {}, "topics": {}}
        )
        m["by_status"][st] = m["by_status"].get(st, 0) + n
        t = m["topics"].setdefault(topic, {})
        t[st] = t.get(st, 0) + n
    open_reports = (
        await db.execute(
            select(func.count(QuestionReport.id))
            .join(Question, Question.id == QuestionReport.question_id)
            .where(QuestionReport.resolved_at.is_(None), Question.module_key.in_(allowed))
        )
    ).scalar_one()
    minutes = (
        await db.execute(
            select(func.coalesce(func.sum(Question.review_minutes), 0)).where(
                Question.reviewer_id == user.id
            )
        )
    ).scalar_one()
    return {
        "modules": list(by_module.values()),
        "open_reports": int(open_reports),
        "my_review_minutes": int(minutes),
    }


# --- Generation (admin) -----------------------------------------------------------------------


def _batch_out(b: GenerationBatch) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "mode": b.mode,
        "module_key": b.module_key,
        "level": b.level,
        "topic_codes": b.topic_codes,
        "difficulties": b.difficulties,
        "per_request": b.per_request,
        "language": b.language,
        "status": b.status,
        "requests": b.requests,
        "questions_created": b.questions_created,
        "error": b.error,
        "created_at": b.created_at,
        "ended_at": b.ended_at,
    }


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate(
    body: GenerateIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    info = prompts.course_info(body.module_key)
    if body.module_key not in AVAILABLE_MODULES or info is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_course")
    valid = {t.code for t in info.topics}
    if any(code not in valid for code in body.topic_codes):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_topic")
    if any(d < 1 or d > 5 for d in body.difficulties):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_difficulty")
    batch = await pipeline.submit_generation(
        db,
        module_key=body.module_key,
        level=body.level,
        topic_codes=body.topic_codes,
        difficulties=body.difficulties,
        per_request=body.per_request,
        language=body.language,
        mode=body.mode,
        requested_by=admin.id,
    )
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="question.generate",
            target_type="generation_batch",
            target_id=str(batch.id),
            meta={"mode": body.mode, "requests": batch.requests},
        )
    )
    await db.commit()
    if body.mode == "direct" and batch.status == "submitted":
        await enqueue("generate_questions_direct", batch_id=str(batch.id))
    await db.refresh(batch)
    return _batch_out(batch)


@router.get("/batches")
async def batches(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(GenerationBatch).order_by(GenerationBatch.created_at.desc()).limit(50)
        )
    ).scalars()
    return [_batch_out(b) for b in rows]


@router.post("/batches/{batch_id}/poll")
async def poll_batch(
    batch_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    batch = await db.get(GenerationBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if batch.mode == "batch" and batch.status == "submitted":
        await pipeline.process_batch(db, batch)
        await db.refresh(batch)
    return _batch_out(batch)


@router.get("/reports")
async def reports(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    allowed = _modules_for(user)
    rows = (
        await db.execute(
            select(QuestionReport, Question)
            .join(Question, Question.id == QuestionReport.question_id)
            .where(QuestionReport.resolved_at.is_(None), Question.module_key.in_(allowed))
            .order_by(QuestionReport.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "question_id": str(q.id),
            "module_key": q.module_key,
            "topic_code": q.topic_code,
            "comment": r.comment,
            "created_at": r.created_at,
            "question_status": q.status,
        }
        for r, q in rows
    ]
