"""arq worker settings. Run with: arq worker.main.WorkerSettings"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app import observability
from app.config import get_settings
from worker.tasks import (
    check_source_links,
    log_expiring_entitlements,
    process_stripe_event,
    purge_sessions,
    send_daily_digest,
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
        check_source_links,
        send_daily_digest,
    ]
    cron_jobs = [
        cron(purge_sessions, minute=5),
        cron(log_expiring_entitlements, hour=3, minute=15),  # UTC
        cron(check_source_links, weekday=0, hour=4, minute=30),  # Mondays, UTC
        cron(send_daily_digest, hour=6, minute=0),  # UTC: 07:00 Zurich in winter, 08:00 in summer
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 600
