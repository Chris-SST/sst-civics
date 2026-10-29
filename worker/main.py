"""arq worker settings. Run with: arq worker.main.WorkerSettings"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app import observability
from app.config import get_settings
from worker.tasks import (
    generate_questions_direct,
    poll_generation_batches,
    process_stripe_event,
    purge_sessions,
    reconcile_subscriptions,
    send_email,
)


async def startup(ctx: dict) -> None:
    observability.configure()


class WorkerSettings:
    functions = [
        send_email,
        process_stripe_event,
        reconcile_subscriptions,
        purge_sessions,
        generate_questions_direct,
        poll_generation_batches,
    ]
    cron_jobs = [
        cron(reconcile_subscriptions, hour=3, minute=15),
        cron(purge_sessions, minute=5),
        cron(poll_generation_batches, minute={2, 12, 22, 32, 42, 52}),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 3600  # direct generation runs many provider calls
