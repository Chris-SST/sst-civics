"""Explain this: a short chat bound to one question (task 1.10, D-057). Starting returns the
learner's open conversation for the question or creates one; messages go through the tutoring
message endpoint (`POST /api/tutor/conversations/{id}/messages`), which uses the question as
context for the reply and the gatekeeper. A pass is needed; the free tier has no Explain this.
Nothing here is reachable from the mock test."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.db import get_db
from app.deps import require_learner
from app.llm.client import get_provider
from app.models import (
    CONVERSATION_ACTIVE,
    LANGUAGES,
    Conversation,
    Message,
    Question,
    User,
)
from app.questions import bank
from app.study import selection
from app.tutoring import context
from app.tutoring.limits import usage_for
from app.tutoring.routes import ConversationDetail, MessageOut, conversation_out

router = APIRouter(prefix="/api/explain", tags=["explain"])


class ExplainStart(BaseModel):
    question_id: str = Field(max_length=80)
    lang: str | None = Field(default=None, max_length=5)

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str | None) -> str | None:
        if v is not None and v not in LANGUAGES:
            raise ValueError("unknown language")
        return v


class ExplainOut(ConversationDetail):
    tutor_enabled: bool
    usage: dict[str, Any]


@router.post("/start", response_model=ExplainOut)
async def start(
    body: ExplainStart,
    response: Response,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> ExplainOut:
    """The learner's open conversation about this question, or a new one."""
    if not has_access(user, user.canton):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
    q = await db.get(Question, body.question_id)
    if q is None or not selection.servable_for(q, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if await context.mock_running(db, user):
        raise HTTPException(status.HTTP_409_CONFLICT, "mock_in_progress")
    lang = body.lang or user.study_language
    conv = (
        (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.question_id == q.id,
                    Conversation.status == CONVERSATION_ACTIVE,
                )
                .order_by(Conversation.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if conv is None:
        topic = await bank.get_topic(db, user.canton, q.topic_code)
        topic_name = (topic.display(lang) if topic else q.topic_code)[:160]
        conv = Conversation(
            user_id=user.id,
            canton=user.canton,
            topic_code=q.topic_code,
            topic_name=topic_name,
            question_id=q.id,
            language=lang,
            title=topic_name,
        )
        db.add(conv)
        response.status_code = status.HTTP_201_CREATED
    else:
        conv.language = lang  # the reply language follows the learner's current choice
    await db.commit()
    await db.refresh(conv)
    messages = (
        (
            await db.execute(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.seq)
            )
        )
        .scalars()
        .all()
    )
    return ExplainOut(
        **conversation_out(conv).model_dump(),
        messages=[
            MessageOut(id=m.id, seq=m.seq, role=m.role, content=m.content, created_at=m.created_at)
            for m in messages
        ],
        tutor_enabled=get_provider().available,
        usage=(await usage_for(db, user)).to_dict(),
    )
