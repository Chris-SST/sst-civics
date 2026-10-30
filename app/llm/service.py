"""High-level AI operations: tutor reply streaming, the gatekeeper classification, running
summaries, and cost logging with alerts. Callers never see the SDK.

Data sent to the provider: course context, topic, the conversation and photos. Never a name,
email, username or any identifier; `user_id` is used only in our own cost log."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.llm import prompts
from app.llm.client import Completion, LLMError, Usage, get_provider
from app.llm.pricing import cost_usd
from app.models import ROLE_ADMIN, CostAlert, LlmCall, User

log = logging.getLogger(__name__)

PURPOSE_REPLY = "tutor_reply"
PURPOSE_GATE = "gatekeeper"
PURPOSE_SUMMARY = "summary"

GATE_ON_TOPIC = "on_topic"
GATE_BORDERLINE = "borderline"
GATE_OFF_TOPIC = "off_topic"
GATE_OVERRIDE = "override"
GATE_WELLBEING = "wellbeing"
GATE_LABELS = (GATE_ON_TOPIC, GATE_BORDERLINE, GATE_OFF_TOPIC, GATE_OVERRIDE, GATE_WELLBEING)
WELLBEING_KINDS = ("none", "self_harm", "abuse", "sexual", "bullying", "danger")

GATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(GATE_LABELS)},
        "wellbeing": {"type": "string", "enum": list(WELLBEING_KINDS)},
        "coursework": {"type": "boolean"},
    },
    "required": ["label", "wellbeing", "coursework"],
    "additionalProperties": False,
}

LANGUAGE_NAMES = {"en": "English (British spelling)", "de": "German", "fr": "French"}


@dataclass
class GateResult:
    label: str
    wellbeing: str = "none"
    coursework: bool = False
    failed_open: bool = False  # the check did not run; the message went through


@dataclass
class TutorContext:
    course_key: str
    language: str
    topic_code: str
    topic_name: str
    summary: str | None = None
    note: str | None = None  # borderline or wellbeing steer for this turn
    mastery: int | None = None  # 0 to 100 on this topic, if the student has been tested
    misses: list[dict[str, str]] | None = None  # recent wrong answers on this topic


# --- Prompt assembly -----------------------------------------------------------------


def _course_label(course_key: str, locale: str = "en") -> str:
    module = prompts.course_module_key(course_key)
    info = prompts.course_info(module)
    level = prompts.course_level(course_key)
    if info is None:
        return course_key
    name = info.display("en")
    level_name = info.level_display(level, "en")
    return f"{name}, {level_name}" if level_name else name


def prompt_version(course_key: str) -> str:
    base = prompts.load("base")
    module = prompts.course_module_key(course_key)
    course = prompts.load(f"courses/{module}")
    figures = prompts.load("figures")
    return f"{base.label}+{figures.label}+{course.label}"


def build_system(ctx: TutorContext) -> list[dict[str, Any]]:
    """Layers 1 and 2 are cached (one breakpoint after the course module); layer 3 is the
    per-session context and changes every turn."""
    base = prompts.load("base")
    module = prompts.course_module_key(ctx.course_key)
    course = prompts.load(f"courses/{module}")
    lines = [
        "Student context (no personal details are ever provided):",
        f"- Course: {_course_label(ctx.course_key)}",
        f"- Reply language: {LANGUAGE_NAMES.get(ctx.language, 'English (British spelling)')}",
        f"- Session topic: {ctx.topic_name} (topic code {ctx.topic_code})",
    ]
    if ctx.summary:
        lines.append("- Summary of the earlier part of this conversation: " + ctx.summary)
    if ctx.mastery is not None:
        band = "weak" if ctx.mastery < 40 else "developing" if ctx.mastery < 70 else "strong"
        lines.append(f"- Mastery on this topic from practice questions: {ctx.mastery}/100 ({band})")
    if ctx.misses:
        lines.append(
            "- Recent practice questions the student got wrong on this topic. Start by finding "
            "out what went wrong with the first one, then teach the idea behind it; do not "
            "simply give the correct answer:"
        )
        for i, m in enumerate(ctx.misses, 1):
            lines.append(
                f"  {i}. Question: {m['question']}\n     Student's answer: {m['student_answer']}"
                f"\n     Correct answer: {m['correct_answer']}"
            )
    if ctx.note:
        lines.append("- Note for this turn: " + ctx.note)
    figures = prompts.load("figures")
    return [
        {"type": "text", "text": base.text},
        {"type": "text", "text": figures.text},
        {"type": "text", "text": course.text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "\n".join(lines)},
    ]


# --- Cost logging and alerts -------------------------------------------------------------


async def record_call(
    db: AsyncSession,
    *,
    user_id: Any | None,
    conversation_id: Any | None,
    purpose: str,
    model: str,
    prompt_version: str,
    status: str,
    usage: Usage | None,
    latency_ms: int,
) -> LlmCall:
    settings = get_settings()
    usage = usage or Usage()
    usd = cost_usd(
        model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
    )
    row = LlmCall(
        user_id=user_id,
        conversation_id=conversation_id,
        purpose=purpose,
        model=model,
        prompt_version=prompt_version,
        status=status,
        input_tokens=usage.input_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=usd,
        cost_chf=usd * settings.usd_chf_rate,
        latency_ms=latency_ms,
    )
    db.add(row)
    await db.flush()
    if user_id is not None and usd > 0:
        await check_cost_alerts(db, user_id)
    return row


def month_start(now: datetime | None = None) -> datetime:
    now = now or utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def month_cost_chf(db: AsyncSession, user_id: Any | None = None) -> float:
    stmt = select(func.coalesce(func.sum(LlmCall.cost_chf), 0.0)).where(
        LlmCall.created_at >= month_start()
    )
    if user_id is not None:
        stmt = stmt.where(LlmCall.user_id == user_id)
    return float((await db.execute(stmt)).scalar_one())


async def _admin_recipients(db: AsyncSession) -> list[tuple[str, str]]:
    rows = (
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
    return [(u.email, u.locale) for u in rows if u.email]


async def _alert_once(
    db: AsyncSession, *, kind: str, scope: str, amount_chf: float, threshold_chf: float
) -> bool:
    period = utcnow().strftime("%Y-%m")
    exists = await db.execute(
        select(CostAlert.id).where(
            CostAlert.kind == kind, CostAlert.scope == scope, CostAlert.period == period
        )
    )
    if exists.first() is not None:
        return False
    db.add(CostAlert(kind=kind, scope=scope, period=period, amount_chf=amount_chf))
    await db.flush()
    from app.jobs import send_email_job

    for to, locale in await _admin_recipients(db):
        await send_email_job(
            "cost_alert",
            locale,
            to,
            scope=kind,
            amount=f"{amount_chf:.2f}",
            threshold=f"{threshold_chf:.2f}",
            period=period,
            link=get_settings().app_base_url.rstrip("/") + "/admin?tab=usage",
        )
    return True


async def check_cost_alerts(db: AsyncSession, user_id: Any) -> None:
    settings = get_settings()
    if settings.ai_learner_alert_chf > 0:
        spent = await month_cost_chf(db, user_id)
        if spent >= settings.ai_learner_alert_chf:
            await _alert_once(
                db,
                kind="learner",
                scope=str(user_id),
                amount_chf=spent,
                threshold_chf=settings.ai_learner_alert_chf,
            )
    if settings.ai_monthly_budget_chf > 0:
        total = await month_cost_chf(db)
        if total >= settings.ai_monthly_budget_chf:
            await _alert_once(
                db,
                kind="budget",
                scope="all",
                amount_chf=total,
                threshold_chf=settings.ai_monthly_budget_chf,
            )


# --- Gatekeeper -------------------------------------------------------------------------


async def classify_message(
    db: AsyncSession,
    *,
    user_id: Any,
    conversation_id: Any,
    text: str,
    course_key: str,
    topic_name: str,
    previous_assistant: str | None,
) -> GateResult:
    """Label a student message before the tutor sees it. If the check fails or times out
    the message is passed through as on topic (the tutor still has its own scope rules)."""
    settings = get_settings()
    gate = prompts.load("gatekeeper")
    system = gate.text
    context = [
        f"Course: {_course_label(course_key)}",
        f"Session topic: {topic_name}",
    ]
    if previous_assistant:
        context.append("Tutor's previous reply (for context only):\n" + previous_assistant[:1500])
    user_block = (
        "\n".join(context) + "\n\nStudent message to label:\n<message>\n" + text + "\n</message>"
    )
    started = time.monotonic()
    try:
        data, completion = await get_provider().structured(
            model=settings.fast_model,
            system=system,
            messages=[{"role": "user", "content": user_block}],
            schema=GATE_SCHEMA,
            max_tokens=200,
            effort="low",
            timeout=settings.fast_timeout_seconds,
        )
    except LLMError:
        await record_call(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            purpose=PURPOSE_GATE,
            model=settings.fast_model,
            prompt_version=gate.label,
            status="error",
            usage=None,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return GateResult(label=GATE_ON_TOPIC, failed_open=True)
    await record_call(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        purpose=PURPOSE_GATE,
        model=completion.model,
        prompt_version=gate.label,
        status="ok",
        usage=completion.usage,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    label = data.get("label") if data.get("label") in GATE_LABELS else GATE_ON_TOPIC
    wellbeing = data.get("wellbeing") if data.get("wellbeing") in WELLBEING_KINDS else "none"
    if wellbeing != "none":
        label = GATE_WELLBEING
    return GateResult(label=label, wellbeing=wellbeing, coursework=bool(data.get("coursework")))


# --- Tutor reply --------------------------------------------------------------------------


@dataclass
class ReplyOutcome:
    completion: Completion | None
    error: LLMError | None
    latency_ms: int


async def stream_reply(
    ctx: TutorContext, messages: list[dict[str, Any]]
) -> AsyncIterator[str | ReplyOutcome]:
    """Yields text deltas, then one ReplyOutcome. The caller records the call and stores
    the message; this function only talks to the provider."""
    settings = get_settings()
    started = time.monotonic()
    system = build_system(ctx)
    try:
        async for item in get_provider().stream(
            model=settings.tutor_model,
            system=system,
            messages=messages,
            max_tokens=settings.tutor_max_output_tokens,
            effort=settings.tutor_effort,
            timeout=settings.tutor_timeout_seconds,
        ):
            if isinstance(item, Completion):
                yield ReplyOutcome(
                    completion=item,
                    error=None,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
                return
            yield item
    except LLMError as exc:
        yield ReplyOutcome(
            completion=None, error=exc, latency_ms=int((time.monotonic() - started) * 1000)
        )


# --- Running summary ------------------------------------------------------------------


async def summarise(
    db: AsyncSession,
    *,
    user_id: Any,
    conversation_id: Any,
    previous_summary: str | None,
    transcript: str,
) -> str | None:
    """Fold older turns into the running summary with the fast model. Returns None when the
    call fails; the caller keeps the previous summary and tries again later."""
    settings = get_settings()
    spec = prompts.load("summary")
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
        "additionalProperties": False,
    }
    body = (
        "Previous summary:\n"
        + (previous_summary or "(none)")
        + "\n\nTurns to fold in:\n"
        + transcript
    )
    started = time.monotonic()
    try:
        data, completion = await get_provider().structured(
            model=settings.fast_model,
            system=spec.text,
            messages=[{"role": "user", "content": body}],
            schema=schema,
            max_tokens=600,
            effort="low",
            timeout=20,
        )
    except LLMError:
        await record_call(
            db,
            user_id=user_id,
            conversation_id=conversation_id,
            purpose=PURPOSE_SUMMARY,
            model=settings.fast_model,
            prompt_version=spec.label,
            status="error",
            usage=None,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return None
    await record_call(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        purpose=PURPOSE_SUMMARY,
        model=completion.model,
        prompt_version=spec.label,
        status="ok",
        usage=completion.usage,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    summary = str(data.get("summary", "")).strip()
    return summary[:4000] or None
