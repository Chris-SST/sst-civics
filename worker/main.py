"""arq worker settings. Run with: arq worker.main.WorkerSettings"""

from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import func

from app import observability
from app.config import get_settings
from worker.tasks import (
    articles_tick,
    check_source_links,
    log_expiring_entitlements,
    politics_questions,
    politics_tick,
    process_stripe_event,
    produce_article,
    produce_politics_page,
    publish_article,
    publish_politics_page,
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
        articles_tick,
        # Article production (D-073): AI writing, review and seven translations can take
        # half an hour; publication waits for the site builder. No retries (each run costs
        # money and the database claim stops a second run); results are not kept, so the
        # same job id can be queued again as soon as a run ends.
        func(produce_article, timeout=3600, max_tries=1, keep_result=0),
        func(publish_article, timeout=1800, max_tries=1, keep_result=0),
        # Politics in your canton (D-074): the same, plus the practice questions.
        politics_tick,
        func(produce_politics_page, timeout=3600, max_tries=1, keep_result=0),
        func(publish_politics_page, timeout=1800, max_tries=1, keep_result=0),
        func(politics_questions, timeout=900, max_tries=1, keep_result=0),
    ]
    cron_jobs = [
        cron(purge_sessions, minute=5),
        cron(log_expiring_entitlements, hour=3, minute=15),  # UTC
        cron(check_source_links, weekday=0, hour=4, minute=30),  # Mondays, UTC
        cron(send_daily_digest, hour=6, minute=0),  # UTC: 07:00 Zurich in winter, 08:00 in summer
        # Articles (D-073): only acts when ARTICLES_ENABLED is true.
        cron(articles_tick, minute={0, 15, 30, 45}, keep_result=0),
        # Politics (D-074): only acts when POLITICS_ENABLED is true.
        cron(politics_tick, minute={1, 16, 31, 46}, keep_result=0, timeout=1500),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 600
