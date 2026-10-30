"""Generation and verification pipeline (PLAN.md, Question bank pipeline).

generate (Batch API or direct) -> draft -> independent solve -> automatic checks
-> auto_verified (spot-checked for the first 50 per course, then 10%) or needs_review
-> tutor approves, fixes or retires.

Every provider call goes through app/llm and is logged. No student data is involved here
and none is sent."""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import utcnow
from app.llm import prompts, service
from app.llm.client import BatchRequest, LLMError, get_provider
from app.models import (
    Q_APPROVED,
    Q_AUTO_VERIFIED,
    Q_DRAFT,
    Q_NEEDS_REVIEW,
    QTYPE_MCQ,
    GenerationBatch,
    Question,
)
from app.questions import checks

log = logging.getLogger(__name__)

PURPOSE_GEN = "question_gen"
PURPOSE_SOLVE = "question_solve"

QUESTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic_code": {"type": "string"},
        "difficulty": {"type": "integer"},
        "question_text": {"type": "string"},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
                "required": ["key", "text"],
                "additionalProperties": False,
            },
        },
        "answer": {"type": "string"},
        "worked_solution": {"type": "string"},
    },
    "required": [
        "topic_code",
        "difficulty",
        "question_text",
        "options",
        "answer",
        "worked_solution",
    ],
    "additionalProperties": False,
}
GEN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": QUESTION_ITEM_SCHEMA}},
    "required": ["questions"],
    "additionalProperties": False,
}
SOLVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "final_answer": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "issue": {"type": "string"},
    },
    "required": ["final_answer", "confidence", "issue"],
    "additionalProperties": False,
}
LANGUAGE_NAMES = {"en": "English (British spelling)", "de": "German", "fr": "French"}


# --- Prompt assembly -----------------------------------------------------------------------


def course_examples(module_key: str) -> str:
    path = prompts.prompts_root() / "courses" / module_key / "examples.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _course_text(module_key: str) -> tuple[str, str]:
    module = prompts.load(f"courses/{module_key}")
    return module.text, module.label


def generation_prompt_version(module_key: str) -> str:
    gen = prompts.load("questions/generate")
    _, course_label = _course_text(module_key)
    return f"{gen.label}+{course_label}"


def _level_words(level: str) -> str:
    return {"sl": "Standard Level", "hl": "Higher Level"}.get(level, "Standard and Higher Level")


def build_generation_request(
    *,
    module_key: str,
    level: str,
    topic_code: str,
    difficulty: int,
    count: int,
    language: str,
    custom_id: str,
) -> BatchRequest:
    gen = prompts.load("questions/generate")
    course_text, _ = _course_text(module_key)
    info = prompts.course_info(module_key)
    topic = info.topic(topic_code) if info else None
    topic_name = topic.display("en") if topic else topic_code
    system = [
        {"type": "text", "text": course_text},
        {"type": "text", "text": gen.text, "cache_control": {"type": "ephemeral"}},
    ]
    examples = course_examples(module_key)
    user = (
        f"Course module: {info.display('en') if info else module_key}\n"
        f"Level: {_level_words(level)}\n"
        f"Topic: {topic_name} (topic code {topic_code})\n"
        f"Difficulty: {difficulty}\n"
        f"Language: {LANGUAGE_NAMES.get(language, 'English (British spelling)')}\n"
        f"Write {count} multiple-choice questions.\n"
        f'Use topic_code "{topic_code}" and difficulty {difficulty} for every question.\n'
        + (f"\nStyle examples (do not copy them):\n\n{examples}" if examples else "")
    )
    return BatchRequest(
        custom_id=custom_id,
        system=system,
        messages=[{"role": "user", "content": user}],
        schema=GEN_SCHEMA,
        max_tokens=8000,
        effort="medium",
    )


# --- Submitting generation -------------------------------------------------------------------


def custom_id(batch_id: uuid.UUID, topic: str, difficulty: int) -> str:
    """Provider custom ids allow only [a-zA-Z0-9_-], at most 64 characters."""
    safe_topic = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in topic)
    return f"{batch_id.hex}_{safe_topic}_{int(difficulty)}"[:64]


def _plan_requests(batch: GenerationBatch) -> list[tuple[str, str, int]]:
    out = []
    for topic in batch.topic_codes:
        for d in batch.difficulties:
            out.append((custom_id(batch.id, topic, int(d)), topic, int(d)))
    return out


async def submit_generation(
    db: AsyncSession,
    *,
    module_key: str,
    level: str,
    topic_codes: list[str],
    difficulties: list[int],
    per_request: int,
    language: str,
    mode: str,
    requested_by: uuid.UUID | None,
) -> GenerationBatch:
    batch = GenerationBatch(
        mode=mode,
        module_key=module_key,
        level=level,
        topic_codes=topic_codes,
        difficulties=difficulties,
        per_request=per_request,
        language=language,
        requested_by=requested_by,
        status="submitted",
    )
    db.add(batch)
    await db.flush()
    plan = _plan_requests(batch)
    batch.requests = len(plan)
    if mode == "batch":
        requests = [
            build_generation_request(
                module_key=module_key,
                level=level,
                topic_code=topic,
                difficulty=d,
                count=per_request,
                language=language,
                custom_id=cid,
            )
            for cid, topic, d in plan
        ]
        try:
            batch.provider_batch_id = await get_provider().batch_create(
                model=get_settings().tutor_model, requests=requests
            )
        except LLMError as exc:
            batch.status = "failed"
            batch.error = f"{exc.code} {exc.detail}".strip()
    await db.flush()
    return batch


async def generate_direct(db: AsyncSession, batch: GenerationBatch) -> int:
    """Direct mode: one structured call per (topic, difficulty), run in the worker."""
    settings = get_settings()
    created = 0
    version = generation_prompt_version(batch.module_key)
    for cid, topic, d in _plan_requests(batch):
        req = build_generation_request(
            module_key=batch.module_key,
            level=batch.level,
            topic_code=topic,
            difficulty=d,
            count=batch.per_request,
            language=batch.language,
            custom_id=cid,
        )
        system_text = (
            "\n\n".join(b["text"] for b in req.system)
            if isinstance(req.system, list)
            else req.system
        )
        started = time.monotonic()
        try:
            data, completion = await get_provider().structured(
                model=settings.tutor_model,
                system=system_text,
                messages=req.messages,
                schema=GEN_SCHEMA,
                max_tokens=req.max_tokens,
                effort=req.effort,
                timeout=180,
            )
        except LLMError as exc:
            await service.record_call(
                db,
                user_id=None,
                conversation_id=None,
                purpose=PURPOSE_GEN,
                model=settings.tutor_model,
                prompt_version=version,
                status="error",
                usage=None,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            batch.error = f"{exc.code} {exc.detail}".strip()
            continue
        await service.record_call(
            db,
            user_id=None,
            conversation_id=None,
            purpose=PURPOSE_GEN,
            model=completion.model,
            prompt_version=version,
            status="ok",
            usage=completion.usage,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        created += await _store_generated(db, batch, data, topic, d, version)
        await db.commit()
    batch.questions_created = created
    batch.status = "processed"
    batch.ended_at = utcnow()
    await db.commit()
    return created


async def process_batch(db: AsyncSession, batch: GenerationBatch) -> int:
    """Batch mode: fetch results once the provider reports the batch ended."""
    if not batch.provider_batch_id:
        return 0
    provider = get_provider()
    status = await provider.batch_status(batch.provider_batch_id)
    if status != "ended":
        return 0
    version = generation_prompt_version(batch.module_key)
    results = await provider.batch_results(batch.provider_batch_id)
    plan = {cid: (topic, d) for cid, topic, d in _plan_requests(batch)}
    created = 0
    errors = 0
    first_error: str | None = None
    for res in results:
        topic, d = plan.get(res.custom_id, (None, None))
        if res.status != "succeeded" or not res.text or topic is None:
            errors += 1
            first_error = first_error or res.error or res.status
            continue
        await service.record_call(
            db,
            user_id=None,
            conversation_id=None,
            purpose=PURPOSE_GEN,
            model=res.model,
            prompt_version=version,
            status="ok",
            usage=res.usage,
            latency_ms=0,
        )
        try:
            data = json.loads(res.text)
        except json.JSONDecodeError:
            errors += 1
            first_error = first_error or "invalid JSON in result"
            continue
        created += await _store_generated(db, batch, data, topic, d, version)
        batch.questions_created = created
        await db.commit()
    batch.questions_created = created
    batch.status = "processed"
    batch.ended_at = utcnow()
    if errors:
        batch.error = f"{errors} request(s) failed: {first_error}"
    await db.commit()
    return created


async def _store_generated(
    db: AsyncSession,
    batch: GenerationBatch,
    data: dict[str, Any],
    topic: str,
    difficulty: int,
    version: str,
) -> int:
    created = 0
    for item in data.get("questions", []) or []:
        q = _question_from_item(item, batch, topic, difficulty, version)
        if q is None:
            continue
        db.add(q)
        await db.flush()
        await run_checks(db, q)
        created += 1
    return created


def _question_from_item(
    item: dict[str, Any], batch: GenerationBatch, topic: str, difficulty: int, version: str
) -> Question | None:
    text = str(item.get("question_text", "")).strip()
    answer = str(item.get("answer", "")).strip()
    if not text or not answer:
        return None
    options = item.get("options") or None
    if not options or len(options) < 2:
        return None
    return Question(
        module_key=batch.module_key,
        level=batch.level,
        topic_code=topic,
        difficulty=difficulty,
        qtype=QTYPE_MCQ,
        language=batch.language,
        question_text=text,
        options=options,
        answer=answer,
        worked_solution=str(item.get("worked_solution", "")).strip(),
        status=Q_DRAFT,
        source="generated",
        prompt_version=version,
        batch_id=batch.id,
    )


# --- Checks ------------------------------------------------------------------------------------


def _question_for_solver(q: Question) -> str:
    parts = [q.question_text]
    if q.options:
        parts.append("\n".join(f"{o['key']}. {o['text']}" for o in q.options))
    return "\n\n".join(parts)


async def independent_solve(db: AsyncSession, q: Question) -> dict[str, Any] | None:
    settings = get_settings()
    solve = prompts.load("questions/solve")
    course_text, course_label = _course_text(q.module_key)
    started = time.monotonic()
    try:
        data, completion = await get_provider().structured(
            model=settings.tutor_model,
            system=course_text + "\n\n" + solve.text,
            messages=[
                {
                    "role": "user",
                    "content": _question_for_solver(q),
                }
            ],
            schema=SOLVE_SCHEMA,
            max_tokens=4000,
            effort="high",
            timeout=120,
        )
    except LLMError:
        await service.record_call(
            db,
            user_id=None,
            conversation_id=q.id,
            purpose=PURPOSE_SOLVE,
            model=settings.tutor_model,
            prompt_version=f"{solve.label}+{course_label}",
            status="error",
            usage=None,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return None
    await service.record_call(
        db,
        user_id=None,
        conversation_id=q.id,
        purpose=PURPOSE_SOLVE,
        model=completion.model,
        prompt_version=f"{solve.label}+{course_label}",
        status="ok",
        usage=completion.usage,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    return data


async def _duplicate_check(db: AsyncSession, q: Question) -> tuple[bool, float]:
    others = (
        (
            await db.execute(
                select(Question.question_text).where(
                    Question.module_key == q.module_key,
                    Question.topic_code == q.topic_code,
                    Question.id != q.id,
                    Question.status != "retired",
                )
            )
        )
        .scalars()
        .all()
    )
    return checks.is_near_duplicate(q.question_text, list(others))


async def _spot_check_due(db: AsyncSession, module_key: str) -> bool:
    settings = get_settings()
    n = (
        await db.execute(
            select(func.count(Question.id)).where(
                Question.module_key == module_key,
                Question.status.in_((Q_AUTO_VERIFIED, Q_APPROVED)),
            )
        )
    ).scalar_one()
    if n < settings.question_spot_check_first:
        return True
    return random.random() < settings.question_spot_check_rate  # noqa: S311


async def run_checks(db: AsyncSession, q: Question) -> None:
    """Independent solve plus automatic checks. Sets status and check_results."""
    issues: list[str] = []
    results: dict[str, Any] = {}

    solved = await independent_solve(db, q)
    if solved is None:
        issues.append("solve_failed")
        results["solve"] = "error"
    else:
        q.solve_answer = str(solved.get("final_answer", ""))
        results["solve_confidence"] = solved.get("confidence")
        results["solve_issue"] = solved.get("issue") or ""
        if solved.get("confidence") == "low":
            issues.append("solver_low_confidence")
        outcome = checks.check_answer(q.solve_answer, q.answer)
        results["answer_match"] = outcome.correct
        results["answer_method"] = outcome.method
        if not outcome.correct:
            issues.append("answers_differ")

    if not checks.options_valid(q.options, q.answer):
        issues.append("mcq_options_invalid")
    if not q.worked_solution:
        issues.append("no_solution")

    dup, best = await _duplicate_check(db, q)
    results["max_similarity"] = round(best, 2)
    if dup:
        issues.append("near_duplicate")

    results["issues"] = issues
    results["checked_at"] = utcnow().isoformat()
    q.check_results = results
    if issues:
        q.status = Q_NEEDS_REVIEW
        q.spot_check = False
    else:
        q.status = Q_AUTO_VERIFIED
        q.spot_check = await _spot_check_due(db, q.module_key)
    await db.flush()
