"""arq worker settings. Run with: arq worker.main.WorkerSettings"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app import observability
from app.config import get_settings
from worker.tasks import process_stripe_event, purge_sessions, reconcile_subscriptions, send_email


async def startup(ctx: dict) -> None:
    observability.configure()


class WorkerSettings:
    functions = [send_email, process_stripe_event, reconcile_subscriptions, purge_sessions]
    cron_jobs = [
        cron(reconcile_subscriptions, hour=3, minute=15),
        cron(purge_sessions, minute=5),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 120
