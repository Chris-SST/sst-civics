"""Admin: AI usage and cost. Admin only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_admin
from app.llm.service import month_start
from app.models import LlmCall, Message, User

router = APIRouter(prefix="/api/admin", tags=["admin-tutor"])


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
    per_learner = (
        await db.execute(
            select(
                LlmCall.user_id,
                User.email,
                func.count(LlmCall.id),
                func.coalesce(func.sum(LlmCall.cost_chf), 0.0),
            )
            .join(User, User.id == LlmCall.user_id, isouter=True)
            .where(LlmCall.created_at >= since, LlmCall.user_id.is_not(None))
            .group_by(LlmCall.user_id, User.email)
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
        "learner_messages": int(messages_this_month),
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
        "top_learners": [
            {
                "user_id": str(uid),
                "email": email or "",
                "calls": n,
                "cost_chf": round(float(c), 4),
            }
            for uid, email, n, c in per_learner
        ],
    }
