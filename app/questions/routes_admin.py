"""Admin review queue for questions imported from content/, and the translation status
screen. Reviewer scopes per language or canton arrive in Phase 1 (D-009).

Review actions change the database only. Each one is recorded in the question's
`pending_changes` with `file_sync_pending` set, because the file under content/ is the master
copy and must be updated by the pipeline (task 1.5 adds the write-back). Until then the next
import keeps these changes as long as the file's version has not risen."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.routes import translation_status
from app.db import get_db, utcnow
from app.deps import require_admin
from app.models import (
    OPTION_KEYS,
    Q_APPROVED,
    Q_DRAFT,
    Q_IN_REVIEW,
    Q_RETIRED,
    QUESTION_STATUSES,
    TRANSLATION_LANGUAGES,
    AuditLog,
    Question,
    QuestionReport,
    QuestionTranslation,
    Topic,
    User,
)
from app.questions import checks

router = APIRouter(prefix="/api/review", tags=["review"])

# action -> (statuses it may start from, resulting status)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "approve": ((Q_DRAFT, Q_IN_REVIEW, Q_APPROVED), Q_APPROVED),
    "send_back": ((Q_DRAFT, Q_IN_REVIEW, Q_APPROVED), Q_DRAFT),
    "retire": ((Q_DRAFT, Q_IN_REVIEW, Q_APPROVED), Q_RETIRED),
}


class QuestionEdits(BaseModel):
    question_de: str | None = Field(default=None, min_length=1, max_length=2000)
    options_de: dict[str, str] | None = None
    correct: Literal["a", "b", "c", "d"] | None = None
    explanation_de: str | None = Field(default=None, min_length=1, max_length=4000)
    difficulty: Literal[1, 2, 3] | None = None
    topic_code: str | None = Field(default=None, max_length=80)


class ReviewIn(BaseModel):
    action: Literal["approve", "send_back", "retire"]
    edits: QuestionEdits | None = None
    note: str | None = Field(default=None, max_length=2000)
    minutes: int = Field(default=3, ge=0, le=120)


def _canton_filter(stmt: Any, canton: str | None) -> Any:
    if not canton:
        return stmt
    if canton == "federal":
        return stmt.where(Question.canton.is_(None))
    return stmt.where(Question.canton == canton)


def _question_full(q: Question) -> dict[str, Any]:
    return {
        "id": q.id,
        "version": q.version,
        "scope": q.scope,
        "canton": q.canton,
        "topic_code": q.topic_code,
        "difficulty": q.difficulty,
        "question_de": q.question_de,
        "options_de": q.options_de,
        "correct": q.correct,
        "explanation_de": q.explanation_de,
        "sources": q.sources,
        "glossary": q.glossary,
        "translations_missing": q.translations_missing,
        "status": q.status,
        "file_status": q.file_status,
        "file_sync_pending": q.file_sync_pending,
        "pending_changes": q.pending_changes or [],
        "content_hash": q.content_hash,
        "imported_at": q.imported_at,
        "review_note": q.review_note,
        "reviewed_at": q.reviewed_at,
        "report_count": q.report_count,
        "updated_at": q.updated_at,
    }


@router.get("/meta")
async def meta(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Filters for the review screens: cantons with a topic file and their topics."""
    rows = (await db.execute(select(Topic).order_by(Topic.canton, Topic.position))).scalars()
    topics = [
        {
            "canton": t.canton,
            "code": t.code,
            "scope": t.scope,
            "name_de": t.name_de,
            "name_en": t.name_en,
        }
        for t in rows
    ]
    return {
        "cantons": sorted({t["canton"] for t in topics}),
        "topics": topics,
        "statuses": list(QUESTION_STATUSES),
        "languages": list(TRANSLATION_LANGUAGES),
    }


@router.get("/queue")
async def queue(
    q_status: str | None = Query(default=None, alias="status"),
    canton: str | None = None,
    topic: str | None = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Questions by status, canton ("federal" for federal ones) and topic. Without a status:
    everything an admin should look at, drafts and questions in review."""
    stmt = select(Question)
    if q_status in QUESTION_STATUSES:
        stmt = stmt.where(Question.status == q_status)
    else:
        stmt = stmt.where(Question.status.in_((Q_DRAFT, Q_IN_REVIEW)))
    stmt = _canton_filter(stmt, canton)
    if topic:
        stmt = stmt.where(Question.topic_code == topic)
    rows = (
        (await db.execute(stmt.order_by(Question.report_count.desc(), Question.id).limit(300)))
        .scalars()
        .all()
    )
    return [_question_full(q) for q in rows]


@router.get("/questions/{question_id}")
async def get_question(
    question_id: str, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    trs = {
        t.lang: t
        for t in (
            await db.execute(
                select(QuestionTranslation).where(QuestionTranslation.question_id == q.id)
            )
        ).scalars()
    }
    reports = (
        (
            await db.execute(
                select(QuestionReport)
                .where(QuestionReport.question_id == q.id, QuestionReport.resolved_at.is_(None))
                .order_by(QuestionReport.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out = _question_full(q)
    out["translations"] = [
        {
            "lang": lang,
            "state": translation_status(q, trs.get(lang), lang),
            "source_version": trs[lang].source_version if lang in trs else None,
            "reviewed_by": trs[lang].reviewed_by if lang in trs else None,
            "reviewed_at": trs[lang].reviewed_at if lang in trs else None,
        }
        for lang in TRANSLATION_LANGUAGES
    ]
    out["reports"] = [
        {"id": str(r.id), "lang": r.lang, "comment": r.comment, "created_at": r.created_at}
        for r in reports
    ]
    return out


async def _apply_edits(db: AsyncSession, q: Question, edits: QuestionEdits) -> dict[str, Any]:
    changes = edits.model_dump(exclude_none=True)
    if "options_de" in changes:
        opts = {str(k).strip().lower(): str(v).strip() for k, v in changes["options_de"].items()}
        changes["options_de"] = opts
    options = changes.get("options_de", q.options_de)
    correct = changes.get("correct", q.correct)
    if not checks.options_valid(options, correct):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_options")
    if "topic_code" in changes:
        stmt = select(Topic).where(Topic.code == changes["topic_code"])
        stmt = (
            stmt.where(Topic.scope == "federal")
            if q.canton is None
            else stmt.where(Topic.canton == q.canton, Topic.scope != "federal")
        )
        if (await db.execute(stmt.limit(1))).scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_topic")
    for name, value in changes.items():
        setattr(q, name, {k: options[k] for k in OPTION_KEYS} if name == "options_de" else value)
    return changes


@router.patch("/questions/{question_id}")
async def review_question(
    question_id: str,
    body: ReviewIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Approve (optionally with edits), send back to draft with a note, or retire."""
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    allowed_from, target = TRANSITIONS[body.action]
    if q.status not in allowed_from:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    note = (body.note or "").strip() or None
    if body.action == "send_back" and not note:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "note_required")
    if body.edits is not None and body.action != "approve":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "edits_need_approve")
    changes = await _apply_edits(db, q, body.edits) if body.edits else {}
    now = utcnow()
    previous = q.status
    q.status = target
    q.reviewer_id = user.id
    q.reviewed_at = now
    q.review_note = note
    q.review_minutes += body.minutes
    # Not written to the file: the pipeline must update content/ (task 1.5).
    q.file_sync_pending = True
    q.pending_changes = [
        *(q.pending_changes or []),
        {
            "action": body.action,
            "from": previous,
            "status": target,
            "edits": changes or None,
            "note": note,
            "by": str(user.id),
            "at": now.isoformat(),
        },
    ]
    open_reports = (
        await db.execute(
            select(QuestionReport).where(
                QuestionReport.question_id == q.id, QuestionReport.resolved_at.is_(None)
            )
        )
    ).scalars()
    for report in open_reports:
        report.resolved_at = now
    q.report_count = 0
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=f"question.{body.action}",
            target_type="question",
            target_id=q.id,
            meta={
                "from": previous,
                "to": target,
                "version": q.version,
                "edited": sorted(changes),
                "minutes": body.minutes,
            },
        )
    )
    await db.commit()
    await db.refresh(q)
    return _question_full(q)


@router.get("/stats")
async def stats(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(Question.scope, Question.status, func.count(Question.id)).group_by(
                Question.scope, Question.status
            )
        )
    ).all()
    by_scope: dict[str, dict[str, Any]] = {}
    for scope, st, n in rows:
        entry = by_scope.setdefault(scope, {"scope": scope, "by_status": {}})
        entry["by_status"][st] = entry["by_status"].get(st, 0) + int(n)
    open_reports = (
        await db.execute(
            select(func.count(QuestionReport.id)).where(QuestionReport.resolved_at.is_(None))
        )
    ).scalar_one()
    pending = (
        await db.execute(
            select(func.count(Question.id)).where(Question.file_sync_pending.is_(True))
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
        "scopes": sorted(by_scope.values(), key=lambda s: (s["scope"] != "federal", s["scope"])),
        "open_reports": int(open_reports),
        "pending_file_updates": int(pending),
        "my_review_minutes": int(minutes),
    }


@router.get("/translations")
async def translations(
    canton: str | None = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per launch language, over approved German questions: approved, in review, draft,
    stale (made from an older German version, hidden) and missing translations."""
    stmt = _canton_filter(
        select(Question.id, Question.version, Question.translations_missing), canton
    )
    approved = (await db.execute(stmt.where(Question.status == Q_APPROVED))).all()
    ids = [qid for qid, _, _ in approved]
    trs: dict[tuple[str, str], QuestionTranslation] = {}
    if ids:
        for t in (
            await db.execute(
                select(QuestionTranslation).where(QuestionTranslation.question_id.in_(ids))
            )
        ).scalars():
            trs[(t.lang, t.question_id)] = t
    languages = []
    for lang in TRANSLATION_LANGUAGES:
        row = {"lang": lang, "approved": 0, "in_review": 0, "draft": 0, "stale": 0, "missing": 0}
        for qid, version, _ in approved:
            tr = trs.get((lang, qid))
            if tr is None:
                row["missing"] += 1
            elif tr.hidden or tr.source_version < version:
                row["stale"] += 1
            else:
                row[tr.status] += 1
        languages.append(row)
    return {
        "approved_questions": len(approved),
        "flagged_missing": sum(1 for _, _, flagged in approved if flagged),
        "languages": languages,
    }


@router.get("/reports")
async def reports(
    user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(QuestionReport, Question)
            .join(Question, Question.id == QuestionReport.question_id)
            .where(QuestionReport.resolved_at.is_(None))
            .order_by(QuestionReport.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        {
            "id": str(r.id),
            "question_id": q.id,
            "scope": q.scope,
            "topic_code": q.topic_code,
            "lang": r.lang,
            "comment": r.comment,
            "created_at": r.created_at,
            "question_status": q.status,
        }
        for r, q in rows
    ]
