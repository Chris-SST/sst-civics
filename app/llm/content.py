"""AI calls of the content pipeline (scripts/content/, task 1.5): drafting, the independent
answer, the source check, translation and back-translation.

Each step sends one structured-output request per item with a versioned prompt from
`prompts/content/` as the system prompt and the item as the user message. The batch API is
the default (half the price, results within 24 hours); `direct=True` sends the requests one
by one for small runs. Every request is written to the AI call log with its cost; batch
calls at the batch price. No personal data is ever part of a request: the pipeline only
sends question text and public pages."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.llm import prompts, service
from app.llm.client import BatchRequest, LLMError, get_provider
from app.llm.pricing import BATCH_PRICE_FACTOR

log = logging.getLogger(__name__)

PURPOSE_DRAFT = "content_draft"
PURPOSE_ANSWER = "content_answer"
PURPOSE_SOURCE = "content_source_check"
PURPOSE_TRANSLATE = "content_translate"
PURPOSE_BACK = "content_back_translate"
PURPOSE_COMPARE = "content_compare"


class BudgetExceeded(Exception):
    """This month's AI spend has reached AI_MONTHLY_BUDGET_CHF; the pipeline does not start."""


@dataclass
class Job:
    key: str  # the caller's key: a question id, "<lang>/<id>", "draft-3", ...
    text: str  # the user message


@dataclass
class Outcome:
    key: str
    data: dict[str, Any] | None
    model: str
    error: str | None = None


@dataclass
class RunOptions:
    model: str
    direct: bool = False
    effort: str = "medium"
    max_tokens: int = 2000
    timeout: float = 180.0
    poll_seconds: float = 30.0
    max_wait_seconds: float = 26 * 3600
    max_requests: int = 500
    resume_batch: str | None = None  # collect the results of a batch sent earlier
    state_dir: Path | None = None  # where the custom id -> key map of each batch is kept
    allow_over_budget: bool = False
    concurrency: int = 4


def prompt_label(name: str) -> str:
    return prompts.load(name).label


async def check_budget(db: AsyncSession) -> None:
    budget = get_settings().ai_monthly_budget_chf
    if budget > 0:
        spent = await service.month_cost_chf(db)
        if spent >= budget:
            raise BudgetExceeded(f"AI spend this month is CHF {spent:.2f} (budget {budget:.2f})")


def _custom_id(i: int) -> str:
    return f"r{i:05d}"  # the provider allows [a-zA-Z0-9_-]{1,64}; our keys may be longer


def _parse(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def run_jobs(
    db: AsyncSession,
    *,
    purpose: str,
    prompt_name: str,
    schema: dict[str, Any],
    jobs: list[Job],
    options: RunOptions,
    say: Callable[[str], None] = print,
) -> dict[str, Outcome]:
    """Send `jobs` with the system prompt `prompt_name` and return an outcome per key."""
    if not jobs:
        return {}
    if len(jobs) > options.max_requests:
        raise ValueError(
            f"{len(jobs)} requests is more than --max-requests {options.max_requests}; "
            "narrow the run or raise the limit"
        )
    if not options.allow_over_budget:
        await check_budget(db)
    spec = prompts.load(prompt_name)
    if options.direct:
        outcomes = await _run_direct(db, purpose, spec, schema, jobs, options, say)
    else:
        outcomes = await _run_batch(db, purpose, spec, schema, jobs, options, say)
    await db.commit()  # the cost log is kept even if a later step fails
    failed = [o for o in outcomes.values() if o.data is None]
    if failed:
        say(f"{len(failed)} of {len(jobs)} request(s) gave no usable reply ({failed[0].error})")
    return outcomes


async def _run_direct(
    db: AsyncSession,
    purpose: str,
    spec: prompts.PromptFile,
    schema: dict[str, Any],
    jobs: list[Job],
    options: RunOptions,
    say: Callable[[str], None],
) -> dict[str, Outcome]:
    provider = get_provider()
    sem = asyncio.Semaphore(max(1, options.concurrency))
    results: dict[str, Outcome] = {}

    async def one(job: Job) -> tuple[Job, Outcome, Any, int, str]:
        started = time.monotonic()
        async with sem:
            try:
                data, completion = await provider.structured(
                    model=options.model,
                    system=spec.text,
                    messages=[{"role": "user", "content": job.text}],
                    schema=schema,
                    max_tokens=options.max_tokens,
                    effort=options.effort,
                    timeout=options.timeout,
                )
            except LLMError as exc:
                ms = int((time.monotonic() - started) * 1000)
                outcome = Outcome(job.key, None, options.model, f"{exc.code} {exc.detail}".strip())
                return job, outcome, None, ms, "error"
        ms = int((time.monotonic() - started) * 1000)
        ok = isinstance(data, dict)
        outcome = Outcome(
            job.key, data if ok else None, completion.model, None if ok else "invalid json"
        )
        return job, outcome, completion.usage, ms, "ok"

    say(f"Sending {len(jobs)} request(s) directly ({spec.label}, {options.model})")
    for job, outcome, usage, ms, status in await asyncio.gather(*(one(j) for j in jobs)):
        await service.record_call(
            db,
            user_id=None,
            conversation_id=None,
            purpose=purpose,
            model=outcome.model,
            prompt_version=spec.label,
            status=status,
            usage=usage,
            latency_ms=ms,
        )
        results[job.key] = outcome
    return results


def _state_path(options: RunOptions, batch_id: str) -> Path | None:
    if options.state_dir is None:
        return None
    return options.state_dir / f"{batch_id}.json"


async def _run_batch(
    db: AsyncSession,
    purpose: str,
    spec: prompts.PromptFile,
    schema: dict[str, Any],
    jobs: list[Job],
    options: RunOptions,
    say: Callable[[str], None],
) -> dict[str, Outcome]:
    provider = get_provider()
    by_key = {j.key: j for j in jobs}
    if options.resume_batch:
        batch_id = options.resume_batch
        path = _state_path(options, batch_id)
        if path is None or not path.is_file():
            raise FileNotFoundError(f"no saved request map for batch {batch_id} in {path}")
        id_map: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))["requests"]
        say(f"Collecting batch {batch_id} ({len(id_map)} request(s))")
    else:
        id_map = {_custom_id(i): j.key for i, j in enumerate(jobs)}
        requests = [
            BatchRequest(
                custom_id=cid,
                system=spec.text,
                messages=[{"role": "user", "content": by_key[key].text}],
                schema=schema,
                max_tokens=options.max_tokens,
                effort=options.effort,
            )
            for cid, key in id_map.items()
        ]
        batch_id = await provider.batch_create(model=options.model, requests=requests)
        path = _state_path(options, batch_id)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "batch_id": batch_id,
                "purpose": purpose,
                "prompt": spec.label,
                "model": options.model,
                "requests": id_map,
            }
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        say(
            f"Batch {batch_id} sent: {len(requests)} request(s) ({spec.label}, {options.model}). "
            "If this run is interrupted, repeat the command with --resume " + batch_id
        )
    started = time.monotonic()
    while True:
        status = await provider.batch_status(batch_id)
        if status == "ended":
            break
        if time.monotonic() - started > options.max_wait_seconds:
            raise TimeoutError(f"batch {batch_id} has not ended; collect it later with --resume")
        say(f"Batch {batch_id}: {status}; next check in {options.poll_seconds:.0f} s")
        await asyncio.sleep(options.poll_seconds)
    outcomes: dict[str, Outcome] = {}
    for res in await provider.batch_results(batch_id):
        key = id_map.get(res.custom_id)
        if key is None:
            continue
        data = _parse(res.text) if res.status == "succeeded" else None
        error = None if data is not None else (res.error or res.status)
        await service.record_call(
            db,
            user_id=None,
            conversation_id=None,
            purpose=purpose,
            model=res.model or options.model,
            prompt_version=spec.label,
            status="ok" if res.status == "succeeded" else "error",
            usage=res.usage,
            latency_ms=0,
            price_factor=BATCH_PRICE_FACTOR,
        )
        if key in by_key:  # a resumed batch may name items that are no longer pending
            outcomes[key] = Outcome(key, data, res.model or options.model, error)
    for key in by_key:
        outcomes.setdefault(key, Outcome(key, None, options.model, "no result"))
    return outcomes
