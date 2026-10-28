"""Fixed-window rate limiter on Redis, with an in-memory fallback for tests and
single-process development."""

from __future__ import annotations

import logging
import time

from app.config import get_settings

log = logging.getLogger(__name__)

_memory: dict[str, tuple[int, float]] = {}
_redis = None
_redis_failed = False


async def _get_redis():
    global _redis, _redis_failed
    settings = get_settings()
    if settings.jobs_inline or _redis_failed:
        return None
    if _redis is None:
        try:
            import redis.asyncio as aioredis

            _redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=1)
            await _redis.ping()
        except Exception as exc:  # noqa: BLE001
            log.warning("Rate limiter falling back to memory: %s", exc.__class__.__name__)
            _redis_failed = True
            _redis = None
    return _redis


async def hit(key: str, limit: int, window_seconds: int) -> bool:
    """Record one hit. Returns True if the caller is still within the limit."""
    r = await _get_redis()
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            count, _ = await pipe.execute()
            return int(count) <= limit
        except Exception as exc:  # noqa: BLE001
            log.warning("Rate limiter Redis error, allowing request: %s", exc.__class__.__name__)
            return True
    now = time.monotonic()
    count, reset_at = _memory.get(key, (0, now + window_seconds))
    if now > reset_at:
        count, reset_at = 0, now + window_seconds
    count += 1
    _memory[key] = (count, reset_at)
    return count <= limit


def reset_memory() -> None:
    _memory.clear()
