"""Enqueue background jobs. With JOBS_INLINE=true (tests, dev without Redis) the job
function runs immediately in-process; otherwise it goes to the arq queue on Redis."""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)
_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue(job_name: str, **kwargs: Any) -> None:
    if get_settings().jobs_inline:
        from worker import tasks

        fn = getattr(tasks, job_name)
        await fn({}, **kwargs)
        return
    pool = await _get_pool()
    await pool.enqueue_job(job_name, **kwargs)


async def send_email_job(kind: str, locale: str, to: str, **params: str) -> None:
    await enqueue("send_email", kind=kind, locale=locale, to=to, params=params)
