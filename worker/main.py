"""arq worker settings. Run with: arq worker.main.WorkerSettings"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app import observability
from app.config import get_settings
from worker.tasks import (
    log_expiring_entitlements,
    process_stripe_event,
    purge_sessions,
    send_email,
    send_sign_in_link,
)


async def startup(ctx: dict) -> None:
    observability.configure()


class WorkerSettings:
    functions = [
        send_email,
        send_sign_in_link,
        process_stripe_event,
        purge_sessions,
        log_expiring_entitlements,
    ]
    cron_jobs = [
        cron(purge_sessions, minute=5),
        cron(log_expiring_entitlements, hour=3, minute=15),  # UTC
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 600
