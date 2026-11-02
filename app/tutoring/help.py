"""The help chat (D-066): one open conversation per learner for any question about the
knowledge test, its topics, the trainer or the naturalisation procedure. Replies come from the
fast model and are grounded in Viapunt's reference material (content/help, built from the
guide pages and the fact checklist). Messages go through the tutoring message endpoint
(`POST /api/tutor/conversations/{id}/messages`).

Learners with a pass share their daily AI messages with Explain this; learners without one
get the smaller free allowance (`AI_FREE_DAILY_MESSAGE_LIMIT`, 0 switches the free chat off).
Not available while a mock test is open."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import has_access
from app.config import get_settings
from app.db import get_db
from app.deps import require_learner
from app.llm.client import get_provider
from app.models import (
    CONVERSATION_ACTIVE,
    CONVERSATION_ENDED,
    LANGUAGES,
    Conversation,
    Message,
    User,
)
from app.tutoring import context
from app.tutoring.context import HELP_TOPIC, HELP_TOPIC_NAME
from app.tutoring.limits import usage_for
from app.tutoring.routes import ConversationDetail, MessageOut, conversation_out

router = APIRouter(prefix="/api/help", tags=["help"])


class HelpStart(BaseModel):
    lang: str | None = Field(default=None, max_length=5)
    new: bool = False  # end the open conversation and start a fresh one

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str | None) -> str | None:
        if v is not None and v not in LANGUAGES:
            raise ValueError("unknown language")
        return v


class HelpOut(ConversationDetail):
    tutor_enabled: bool
    paid: bool
    usage: dict[str, Any]


def help_allowed(user: User) -> bool:
    return has_access(user, user.canton) or get_settings().ai_free_daily_message_limit > 0


@router.post("/start", response_model=HelpOut)
async def start(
    body: HelpStart,
    response: Response,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> HelpOut:
    """The learner's open help conversation, or a new one."""
    if not help_allowed(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
    if await context.mock_running(db, user):
        raise HTTPException(status.HTTP_409_CONFLICT, "mock_in_progress")
    lang = body.lang or user.study_language
    conv = (
        (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.topic_code == HELP_TOPIC,
                    Conversation.status == CONVERSATION_ACTIVE,
                )
                .order_by(Conversation.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if conv is not None and body.new:
        conv.status = CONVERSATION_ENDED
        conv = None
    if conv is None:
        conv = Conversation(
            user_id=user.id,
            canton=user.canton,
            topic_code=HELP_TOPIC,
            topic_name=HELP_TOPIC_NAME,
            language=lang,
            title=HELP_TOPIC_NAME[:120],
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
    return HelpOut(
        **conversation_out(conv).model_dump(),
        messages=[
            MessageOut(id=m.id, seq=m.seq, role=m.role, content=m.content, created_at=m.created_at)
            for m in messages
        ],
        tutor_enabled=get_provider().available,
        paid=has_access(user, user.canton),
        usage=(await usage_for(db, user)).to_dict(),
    )
