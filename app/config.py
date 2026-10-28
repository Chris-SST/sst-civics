"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Runtime
    app_env: Literal["dev", "test", "staging", "production"] = "dev"
    secret_key: str = Field(default="dev-only-change-me", min_length=16)
    app_base_url: str = "http://localhost:5173"
    main_site_url: str = "https://swisssciencetutors.ch"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # Data stores
    database_url: str = "postgresql+asyncpg://sst:sst@localhost:5432/sst"
    redis_url: str = "redis://localhost:6379/0"
    jobs_inline: bool = False  # run background jobs in-process (dev without Redis, tests)

    # Sessions and security
    session_cookie_name: str = "sst_session"
    csrf_cookie_name: str = "sst_csrf"
    session_ttl_hours: int = 24 * 14  # parents, students, adult learners
    staff_session_ttl_hours: int = 12  # tutors and admin
    cookie_secure: bool | None = None  # None means secure unless app_env is dev or test
    terms_version: str = "2026-10-draft"
    login_rate_limit: int = 10  # attempts per window per identifier and per IP
    login_rate_window_seconds: int = 900

    # Stripe (test mode until go-live is approved)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_version: str = "2026-05-27.dahlia"
    stripe_trial_days: int = 7

    # Email
    email_backend: Literal["console", "smtp", "memory"] = "console"
    email_from: str = "SST Virtual Tutor <tutor@swisssciencetutors.ch>"
    email_outbox_dir: str = "var/outbox"
    email_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # Photo storage (Phase 1)
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # AI (Phase 1). No AI calls are made in Phase 0.
    anthropic_api_key: str = ""
    tutor_model: str = ""
    fast_model: str = ""
    tutor_name: str = "SST Virtual Tutor"
    disclose_model_provider: bool = True
    ai_monthly_budget_chf: float = 0
    ai_student_alert_chf: float = 8

    # Other providers (later phases)
    screening_api_key: str = ""
    tutorcruncher_api_key: str = ""
    tutorcruncher_sso_key: str = ""

    @property
    def cookies_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env not in ("dev", "test")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
