"""Admin: safeguarding queue and AI usage. Admin only; every transcript view is audited."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, utcnow
from app.deps import require_admin
from app.llm.service import month_start
from app.models import (
    FLAG_DISMISSED,
    FLAG_OPEN,
    FLAG_REVIEWED,
    AuditLog,
    Conversation,
    LlmCall,
    Message,
    SafetyFlag,
    User,
)

router = APIRouter(prefix="/api/admin", tags=["admin-tutor"])


class FlagPatch(BaseModel):
    status: Literal["open", "reviewed", "dismissed"]
    notes: str | None = Field(default=None, max_length=4000)


def _flag_out(flag: SafetyFlag, student: User | None, conv: Conversation | None) -> dict[str, Any]:
    return {
        "id": str(flag.id),
        "kind": flag.kind,
        "detail": flag.detail,
        "status": flag.status,
        "notes": flag.notes,
        "created_at": flag.created_at,
        "reviewed_at": flag.reviewed_at,
        "student_id": str(flag.student_id),
        "student_first_name": student.first_name if student else "",
        "conversation_id": str(flag.conversation_id),
        "course_key": conv.course_key if conv else None,
        "topic_name": conv.topic_name if conv else None,
    }


@router.get("/safety-flags")
async def list_flags(
    flag_status: str | None = None,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(SafetyFlag, User, Conversation)
        .join(User, User.id == SafetyFlag.student_id, isouter=True)
        .join(Conversation, Conversation.id == SafetyFlag.conversation_id, isouter=True)
        .order_by(SafetyFlag.created_at.desc())
        .limit(200)
    )
    if flag_status in (FLAG_OPEN, FLAG_REVIEWED, FLAG_DISMISSED):
        stmt = stmt.where(SafetyFlag.status == flag_status)
    rows = (await db.execute(stmt)).all()
    return [_flag_out(f, u, c) for f, u, c in rows]


@router.get("/safety-flags/{flag_id}/conversation")
async def flag_conversation(
    flag_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    flag = await db.get(SafetyFlag, flag_id)
    if flag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    messages = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == flag.conversation_id)
                .order_by(Message.seq)
            )
        )
        .scalars()
        .all()
    )
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="safety.view_conversation",
            target_type="conversation",
            target_id=str(flag.conversation_id),
            meta={"flag_id": str(flag.id)},
        )
    )
    await db.commit()
    return {
        "flag_id": str(flag.id),
        "flagged_message_id": str(flag.message_id) if flag.message_id else None,
        "messages": [
            {
                "id": str(m.id),
                "seq": m.seq,
                "role": m.role,
                "content": m.content,
                "gate_label": m.gate_label,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


@router.patch("/safety-flags/{flag_id}")
async def patch_flag(
    flag_id: uuid.UUID,
    body: FlagPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    flag = await db.get(SafetyFlag, flag_id)
    if flag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    flag.status = body.status
    if body.notes is not None:
        flag.notes = body.notes
    if body.status != FLAG_OPEN:
        flag.reviewed_by = admin.id
        flag.reviewed_at = utcnow()
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="safety.update_flag",
            target_type="safety_flag",
            target_id=str(flag.id),
            meta={"status": body.status},
        )
    )
    await db.commit()
    student = await db.get(User, flag.student_id)
    conv = await db.get(Conversation, flag.conversation_id)
    return _flag_out(flag, student, conv)


@router.get("/ai-usage")
async def ai_usage(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    since = month_start()
    totals = (
        await db.execute(
            select(
                func.count(LlmCall.id),
                func.coalesce(func.sum(LlmCall.cost_chf), 0.0),
                func.coalesce(func.sum(LlmCall.input_tokens), 0),
                func.coalesce(func.sum(LlmCall.cache_read_tokens), 0),
                func.coalesce(func.sum(LlmCall.output_tokens), 0),
            ).where(LlmCall.created_at >= since)
        )
    ).one()
    by_purpose = (
        await db.execute(
            select(
                LlmCall.purpose,
                func.count(LlmCall.id),
                func.coalesce(func.sum(LlmCall.cost_chf), 0.0),
                func.coalesce(func.avg(LlmCall.latency_ms), 0),
                func.sum(case((LlmCall.status == "error", 1), else_=0)),
            )
            .where(LlmCall.created_at >= since)
            .group_by(LlmCall.purpose)
        )
    ).all()
    per_student = (
        await db.execute(
            select(
                LlmCall.student_id,
                User.first_name,
                func.count(LlmCall.id),
                func.coalesce(func.sum(LlmCall.cost_chf), 0.0),
            )
            .join(User, User.id == LlmCall.student_id, isouter=True)
            .where(LlmCall.created_at >= since, LlmCall.student_id.is_not(None))
            .group_by(LlmCall.student_id, User.first_name)
            .order_by(func.sum(LlmCall.cost_chf).desc())
            .limit(25)
        )
    ).all()
    messages_this_month = (
        await db.execute(
            select(func.count(Message.id)).where(
                Message.created_at >= since, Message.role == "user", Message.counted.is_(True)
            )
        )
    ).scalar_one()
    return {
        "period_start": since,
        "calls": totals[0],
        "cost_chf": round(float(totals[1]), 4),
        "input_tokens": int(totals[2]),
        "cache_read_tokens": int(totals[3]),
        "output_tokens": int(totals[4]),
        "student_messages": int(messages_this_month),
        "by_purpose": [
            {
                "purpose": p,
                "calls": n,
                "cost_chf": round(float(c), 4),
                "avg_latency_ms": int(lat or 0),
                "errors": int(err or 0),
            }
            for p, n, c, lat, err in by_purpose
        ],
        "top_students": [
            {
                "student_id": str(sid),
                "first_name": name or "",
                "calls": n,
                "cost_chf": round(float(c), 4),
            }
            for sid, name, n, c in per_student
        ],
    }
