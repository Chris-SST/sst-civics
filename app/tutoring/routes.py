"""Student-facing tutor API: courses and topics, conversations, streaming replies.

Replies stream as server-sent events over a POST:

    event: delta    data: {"text": "..."}
    event: notice   data: {"kind": "off_topic" | "override" | "wellbeing" | "ended"}
    event: message  data: {"id": ..., "role": "assistant" | "notice", "content": "..."}
    event: usage    data: {...UsageInfo}
    event: error    data: {"code": "timeout" | "rate_limited" | ...}
    event: done     data: {}
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.access import FULL, compute_access
from app.config import get_settings
from app.db import SessionLocal, get_db, utcnow
from app.deps import require_roles
from app.jobs import send_email_job
from app.llm import prompts, service
from app.llm.client import get_provider
from app.models import (
    CONVERSATION_ACTIVE,
    CONVERSATION_ENDED,
    LOCALES,
    MESSAGE_ASSISTANT,
    MESSAGE_NOTICE,
    MESSAGE_USER,
    ROLE_ADMIN,
    ROLE_ADULT,
    ROLE_STUDENT,
    Conversation,
    Family,
    Message,
    SafetyFlag,
    User,
)
from app.tutoring.limits import UsageInfo, usage_for

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tutor", tags=["tutor"])
require_learner = require_roles(ROLE_STUDENT, ROLE_ADULT)

OFF_TOPIC_STREAK_LIMIT = 3


# --- Schemas ---------------------------------------------------------------------------


class TopicOut(BaseModel):
    code: str
    name: str


class CourseOut(BaseModel):
    key: str
    name: str
    level: str
    topics: list[TopicOut]


class ConversationCreate(BaseModel):
    course_key: str
    topic_code: str
    language: Literal["en", "de", "fr"] | None = None


class ConversationOut(BaseModel):
    id: uuid.UUID
    course_key: str
    course_name: str
    topic_code: str
    topic_name: str
    language: str
    title: str
    status: str
    created_at: Any
    last_activity_at: Any


class MessageOut(BaseModel):
    id: uuid.UUID
    seq: int
    role: str
    content: str
    created_at: Any


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


# --- Helpers ---------------------------------------------------------------------------


def _course_out(course_key: str, locale: str) -> CourseOut | None:
    if not prompts.has_course_module(course_key):
        return None
    info = prompts.course_info(prompts.course_module_key(course_key))
    assert info is not None
    level = prompts.course_level(course_key)
    return CourseOut(
        key=course_key,
        name=info.display(locale),
        level=info.level_display(level, locale),
        topics=[TopicOut(code=t.code, name=t.display(locale)) for t in info.topics_for(level)],
    )


def _conversation_out(c: Conversation, locale: str) -> ConversationOut:
    info = prompts.course_info(prompts.course_module_key(c.course_key))
    return ConversationOut(
        id=c.id,
        course_key=c.course_key,
        course_name=info.display(locale) if info else c.course_key,
        topic_code=c.topic_code,
        topic_name=c.topic_name,
        language=c.language,
        title=c.title,
        status=c.status,
        created_at=c.created_at,
        last_activity_at=c.last_activity_at,
    )


async def _family(db: AsyncSession, user: User) -> Family | None:
    return await db.get(Family, user.family_id) if user.family_id else None


async def _own_conversation(
    db: AsyncSession, user: User, conversation_id: uuid.UUID
) -> Conversation:
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.student_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return conv


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# --- Endpoints ---------------------------------------------------------------------------


@router.get("/overview")
async def overview(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    family = await _family(db, user)
    courses = [c for c in (_course_out(k, user.locale) for k in (user.courses or [])) if c]
    usage = await usage_for(db, user, family)
    recent = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.student_id == user.id)
                .order_by(Conversation.last_activity_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )
    return {
        "tutor_name": get_settings().tutor_name,
        "tutor_enabled": get_provider().available,
        "access": compute_access(family),
        "notice_seen": user.tutor_notice_seen_at is not None,
        "courses": [c.model_dump() for c in courses],
        "usage": usage.to_dict(),
        "recent": [_conversation_out(c, user.locale).model_dump(mode="json") for c in recent],
    }


@router.post("/notice-seen", status_code=status.HTTP_204_NO_CONTENT)
async def notice_seen(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> None:
    if user.tutor_notice_seen_at is None:
        user.tutor_notice_seen_at = utcnow()
        await db.commit()


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    family = await _family(db, user)
    if compute_access(family) != FULL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
    if body.course_key not in (user.courses or []) or not prompts.has_course_module(
        body.course_key
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_course")
    info = prompts.course_info(prompts.course_module_key(body.course_key))
    assert info is not None
    topic = info.topic(body.topic_code)
    level = prompts.course_level(body.course_key)
    if topic is None or (level and level not in topic.levels):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_topic")
    language = body.language or (user.locale if user.locale in LOCALES else "en")
    conv = Conversation(
        student_id=user.id,
        course_key=body.course_key,
        topic_code=topic.code,
        topic_name=topic.display(language),
        language=language,
        title=topic.display(language),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return _conversation_out(conv, user.locale)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(require_learner), db: AsyncSession = Depends(get_db)
) -> list[ConversationOut]:
    rows = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.student_id == user.id)
                .order_by(Conversation.last_activity_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [_conversation_out(c, user.locale) for c in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conv = await _own_conversation(db, user, conversation_id)
    messages = (
        (
            await db.execute(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.seq)
            )
        )
        .scalars()
        .all()
    )
    out = _conversation_out(conv, user.locale)
    return ConversationDetail(
        **out.model_dump(),
        messages=[
            MessageOut(id=m.id, seq=m.seq, role=m.role, content=m.content, created_at=m.created_at)
            for m in messages
        ],
    )


@router.post("/conversations/{conversation_id}/end", response_model=ConversationOut)
async def end_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conv = await _own_conversation(db, user, conversation_id)
    conv.status = CONVERSATION_ENDED
    await db.commit()
    await db.refresh(conv)
    return _conversation_out(conv, user.locale)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageIn,
    user: User = Depends(require_learner),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    settings = get_settings()
    conv = await _own_conversation(db, user, conversation_id)
    if conv.status != CONVERSATION_ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "conversation_ended")
    if not get_provider().available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "tutor_unavailable")
    family = await _family(db, user)
    if compute_access(family) != FULL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_access")
    text = body.content.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty_message")
    if len(text) > settings.max_student_message_chars:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "message_too_long")
    usage = await usage_for(db, user, family)
    if usage.monthly_exhausted:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "monthly_limit_reached")
    if usage.daily_exhausted:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_limit_reached")

    return StreamingResponse(
        _reply_stream(conv.id, user.id, text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- The reply pipeline ------------------------------------------------------------------


async def _history(db: AsyncSession, conv: Conversation) -> list[dict[str, str]]:
    """Last N turns after the summarised prefix, in provider message format."""
    window = get_settings().conversation_window_turns
    rows = (
        (
            await db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.seq > conv.summary_upto_seq,
                    Message.role.in_((MESSAGE_USER, MESSAGE_ASSISTANT)),
                )
                .order_by(Message.seq)
            )
        )
        .scalars()
        .all()
    )
    rows = rows[-(2 * window) :]
    while rows and rows[0].role != MESSAGE_USER:
        rows = rows[1:]
    return [{"role": m.role, "content": m.content} for m in rows]


def _add_message(
    db: AsyncSession, conv: Conversation, role: str, content: str, **kw: Any
) -> Message:
    msg = Message(
        conversation_id=conv.id,
        student_id=conv.student_id,
        seq=conv.next_seq,
        role=role,
        content=content,
        **kw,
    )
    conv.next_seq += 1
    conv.last_activity_at = utcnow()
    db.add(msg)
    return msg


async def _notify_safeguarding(db: AsyncSession, flag: SafetyFlag) -> None:
    settings = get_settings()
    link = settings.app_base_url.rstrip("/") + "/admin?tab=safety"
    if settings.safeguarding_email:
        recipients = [(settings.safeguarding_email, "en")]
    else:
        admins = (
            (
                await db.execute(
                    select(User).where(
                        User.role == ROLE_ADMIN, User.is_active.is_(True), User.email.is_not(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        recipients = [(a.email, a.locale) for a in admins if a.email]
    for to, locale in recipients:
        await send_email_job(
            "safeguarding_alert", locale, to, link=link, reason=flag.detail or flag.kind
        )


async def _maybe_summarise(db: AsyncSession, conv: Conversation) -> None:
    window = get_settings().conversation_window_turns
    rows = (
        (
            await db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.seq > conv.summary_upto_seq,
                    Message.role.in_((MESSAGE_USER, MESSAGE_ASSISTANT)),
                )
                .order_by(Message.seq)
            )
        )
        .scalars()
        .all()
    )
    keep = 2 * window
    if len(rows) <= keep + 10:
        return
    fold = rows[: len(rows) - keep]
    transcript = "\n".join(
        f"{'Student' if m.role == MESSAGE_USER else 'Tutor'}: {m.content}" for m in fold
    )
    summary = await service.summarise(
        db,
        student_id=conv.student_id,
        conversation_id=conv.id,
        previous_summary=conv.summary,
        transcript=transcript,
    )
    if summary:
        conv.summary = summary
        conv.summary_upto_seq = fold[-1].seq


async def _reply_stream(
    conversation_id: uuid.UUID, student_id: uuid.UUID, text: str
) -> AsyncIterator[str]:
    async with SessionLocal() as db:
        conv = await db.get(Conversation, conversation_id)
        student = await db.get(User, student_id)
        if conv is None or student is None:
            yield _sse("error", {"code": "not_found"})
            return
        family = await db.get(Family, student.family_id) if student.family_id else None
        locale = conv.language

        previous_assistant = (
            await db.execute(
                select(Message.content)
                .where(Message.conversation_id == conv.id, Message.role == MESSAGE_ASSISTANT)
                .order_by(Message.seq.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        user_msg = _add_message(db, conv, MESSAGE_USER, text)
        await db.flush()

        gate = await service.classify_message(
            db,
            student_id=student.id,
            conversation_id=conv.id,
            text=text,
            course_key=conv.course_key,
            topic_name=conv.topic_name,
            previous_assistant=previous_assistant,
        )
        user_msg.gate_label = gate.label

        # Off topic or an override attempt: fixed reply, the tutor model is not called.
        if gate.label in (service.GATE_OFF_TOPIC, service.GATE_OVERRIDE):
            user_msg.counted = True  # counts towards the daily cap
            conv.off_topic_streak += 1
            if gate.label == service.GATE_OVERRIDE or gate.coursework:
                db.add(
                    SafetyFlag(
                        student_id=student.id,
                        conversation_id=conv.id,
                        message_id=user_msg.id,
                        kind="override",
                        detail="coursework" if gate.coursework else "override",
                    )
                )
            ended = conv.off_topic_streak >= OFF_TOPIC_STREAK_LIMIT
            reply_kind = "ended_off_topic" if ended else gate.label
            reply = prompts.fixed_reply(reply_kind, locale)
            notice = _add_message(db, conv, MESSAGE_NOTICE, reply)
            if ended:
                conv.status = CONVERSATION_ENDED
            await db.commit()
            yield _sse("notice", {"kind": gate.label})
            yield _sse(
                "message",
                {"id": str(notice.id), "role": MESSAGE_NOTICE, "content": reply},
            )
            if ended:
                yield _sse("notice", {"kind": "ended"})
            usage = await usage_for(db, student, family)
            yield _sse("usage", usage.to_dict())
            yield _sse("done", {})
            return

        conv.off_topic_streak = 0
        note = None
        if gate.label == service.GATE_BORDERLINE:
            note = (
                "The latest message drifts from the session topic. Help briefly if it is "
                "schoolwork, then steer back to the topic."
            )
        elif gate.label == service.GATE_WELLBEING:
            note = (
                "The latest message may indicate a wellbeing concern "
                f"({gate.wellbeing}). Follow the wellbeing and safety section of your "
                "instructions: respond with care, give the helpline 147, and do not continue "
                "tutoring in this reply."
            )
            flag = SafetyFlag(
                student_id=student.id,
                conversation_id=conv.id,
                message_id=user_msg.id,
                kind="wellbeing",
                detail=gate.wellbeing,
            )
            db.add(flag)
            await db.flush()
            await _notify_safeguarding(db, flag)
            yield _sse("notice", {"kind": "wellbeing"})
        await db.commit()

        ctx = service.TutorContext(
            course_key=conv.course_key,
            language=locale,
            topic_code=conv.topic_code,
            topic_name=conv.topic_name,
            summary=conv.summary,
            note=note,
        )
        history = await _history(db, conv)
        version = service.prompt_version(conv.course_key)
        collected: list[str] = []
        outcome: service.ReplyOutcome | None = None
        async for item in service.stream_reply(ctx, history):
            if isinstance(item, service.ReplyOutcome):
                outcome = item
                break
            collected.append(item)
            yield _sse("delta", {"text": item})

        settings = get_settings()
        if outcome is None or outcome.error is not None:
            code = outcome.error.code if outcome and outcome.error else "api"
            await service.record_call(
                db,
                student_id=student.id,
                conversation_id=conv.id,
                purpose=service.PURPOSE_REPLY,
                model=settings.tutor_model,
                prompt_version=version,
                status="error",
                usage=None,
                latency_ms=outcome.latency_ms if outcome else 0,
            )
            user_msg.counted = False
            await db.commit()
            yield _sse("error", {"code": code, "message": prompts.fixed_reply("error", locale)})
            yield _sse("done", {})
            return

        completion = outcome.completion
        assert completion is not None
        await service.record_call(
            db,
            student_id=student.id,
            conversation_id=conv.id,
            purpose=service.PURPOSE_REPLY,
            model=completion.model,
            prompt_version=version,
            status="refusal" if completion.stop_reason == "refusal" else "ok",
            usage=completion.usage,
            latency_ms=outcome.latency_ms,
        )
        if completion.stop_reason == "refusal":
            reply = prompts.fixed_reply("refusal", locale)
            notice = _add_message(db, conv, MESSAGE_NOTICE, reply)
            user_msg.counted = False
            await db.commit()
            yield _sse("notice", {"kind": "refusal"})
            yield _sse("message", {"id": str(notice.id), "role": MESSAGE_NOTICE, "content": reply})
            yield _sse("done", {})
            return

        reply_text = completion.text or "".join(collected)
        assistant = _add_message(db, conv, MESSAGE_ASSISTANT, reply_text)
        user_msg.counted = True
        await db.commit()
        yield _sse(
            "message", {"id": str(assistant.id), "role": MESSAGE_ASSISTANT, "content": reply_text}
        )
        usage: UsageInfo = await usage_for(db, student, family)
        yield _sse("usage", usage.to_dict())
        yield _sse("done", {})

        try:
            await _maybe_summarise(db, conv)
            await db.commit()
        except Exception:  # noqa: BLE001
            log.exception("Summary step failed")
            await db.rollback()
