"""The public help chat on the guide site (D-067): a limited version of the help chat for
visitors who are not signed in. Same model, prompt and reference material as the app's help
chat (app.tutoring.help), but stateless: the browser sends the last few turns, nothing is
stored, and each visitor gets a few messages a day.

Limits: `PUBLIC_HELP_PER_IP_DAILY` messages per address a day (0 switches the chat off) and
`PUBLIC_HELP_DAILY_TOTAL` for all visitors together, so a burst cannot run up the bill. The
address is kept only as a hashed rate-limit key that expires after a day. The guide host
proxies `/api/public/*` to the API (infra/Caddyfile), so the call is same-origin; requests
from any other origin are refused."""

from __future__ import annotations

import hashlib
import logging
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ratelimit
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import client_ip
from app.llm import prompts, service
from app.llm.client import get_provider
from app.models import LANGUAGES
from app.tutoring.context import HELP_TOPIC, HELP_TOPIC_NAME

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

DAY = 24 * 3600
MAX_TURNS = 6  # turns of history sent to the model
PUBLIC_NOTE = (
    "The learner is a visitor on Viapunt's public guide site and is not signed in. Keep the "
    "answer short. Where it helps, mention once that a free Viapunt account has practice "
    "questions and a mock test."
)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class PublicHelpIn(BaseModel):
    lang: str = Field(default="en", max_length=5)
    messages: list[Turn] = Field(min_length=1, max_length=20)

    @field_validator("lang")
    @classmethod
    def _lang(cls, v: str) -> str:
        return v if v in LANGUAGES else "en"

    @model_validator(mode="after")
    def _ends_with_user(self) -> PublicHelpIn:
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be the visitor's")
        if len(self.messages[-1].content) > get_settings().public_help_max_chars:
            raise ValueError("message too long")
        return self


class PublicHelpOut(BaseModel):
    role: Literal["assistant", "notice"]
    content: str
    remaining: int


def _origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False
    settings = get_settings()
    allowed = {
        f"{p.scheme}://{p.netloc}"
        for p in (urlsplit(settings.guide_base_url), urlsplit(settings.app_base_url))
    }
    return origin.rstrip("/") in allowed


def _history(messages: list[Turn]) -> list[dict[str, str]]:
    """The last turns, starting with a visitor message and alternating, as the model needs."""
    turns: list[dict[str, str]] = []
    for m in messages[-MAX_TURNS:]:
        if turns and turns[-1]["role"] == m.role:
            turns[-1] = {"role": m.role, "content": m.content}
        else:
            turns.append({"role": m.role, "content": m.content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return turns


@router.post("/help", response_model=PublicHelpOut)
async def public_help(
    body: PublicHelpIn, request: Request, db: AsyncSession = Depends(get_db)
) -> PublicHelpOut:
    settings = get_settings()
    per_ip = settings.public_help_per_ip_daily
    if per_ip <= 0 or not get_provider().available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "help_unavailable")
    if not _origin_allowed(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "origin_not_allowed")

    ip_key = hashlib.sha256((settings.secret_key + client_ip(request)).encode()).hexdigest()[:24]
    count_key = f"public_help:ip:{ip_key}"
    if not await ratelimit.hit(count_key, per_ip, DAY):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily_limit_reached")
    used = await ratelimit.count(count_key)
    remaining = max(0, per_ip - used)
    day = utcnow().strftime("%Y-%m-%d")
    if not await ratelimit.hit(f"public_help:total:{day}", settings.public_help_daily_total, DAY):
        log.warning("Public help chat: daily total of %s reached", settings.public_help_daily_total)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "busy")

    history = _history(body.messages)
    text = history[-1]["content"]
    previous = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), None)
    gate = await service.classify_message(
        db,
        user_id=None,
        conversation_id=None,
        text=text,
        canton="zh",
        topic_name=HELP_TOPIC_NAME,
        previous_assistant=previous,
    )
    if gate.label in (service.GATE_OFF_TOPIC, service.GATE_OVERRIDE):
        await db.commit()
        return PublicHelpOut(
            role="notice", content=prompts.fixed_reply(gate.label, body.lang), remaining=remaining
        )

    note = PUBLIC_NOTE
    if gate.label == service.GATE_WELLBEING:
        note = (
            f"The latest message may indicate a wellbeing concern ({gate.wellbeing}). Follow the "
            "wellbeing and safety section of your instructions: respond with care, give the "
            "helpline 143, and do not continue with the topic in this reply."
        )
    elif gate.label == service.GATE_BORDERLINE:
        note += (
            " The latest message drifts from the test and the procedure, or asks about the "
            "visitor's own case: answer the general part from the reference material and say "
            "that only the commune or the canton can decide their own case."
        )
    ctx = service.TutorContext(
        canton="zh",
        language=body.lang,
        topic_code=HELP_TOPIC,
        topic_name=HELP_TOPIC_NAME,
        note=note,
        help=True,
    )
    outcome: service.ReplyOutcome | None = None
    async for item in service.stream_reply(ctx, history):
        if isinstance(item, service.ReplyOutcome):
            outcome = item
    completion = outcome.completion if outcome else None
    await service.record_call(
        db,
        user_id=None,
        conversation_id=None,
        purpose=service.PURPOSE_PUBLIC_HELP,
        model=outcome.model if outcome else settings.help_model,
        prompt_version=service.prompt_version(help=True),
        status=(
            "error"
            if completion is None
            else "refusal"
            if completion.stop_reason == "refusal"
            else "ok"
        ),
        usage=completion.usage if completion else None,
        latency_ms=outcome.latency_ms if outcome else 0,
    )
    await db.commit()
    if completion is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "help_error")
    if completion.stop_reason == "refusal" or not completion.text.strip():
        return PublicHelpOut(
            role="notice", content=prompts.fixed_reply("refusal", body.lang), remaining=remaining
        )
    return PublicHelpOut(role="assistant", content=completion.text, remaining=remaining)
