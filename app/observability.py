"""Logging and error tracking. Logs never carry message content or personal data."""

from __future__ import annotations

import logging

from app.config import get_settings


def configure() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            send_default_pii=False,
            traces_sample_rate=0.0,
        )
