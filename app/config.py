"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
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

    # AI tutor. Every call goes through app/llm; an empty key disables the tutor.
    anthropic_api_key: str = ""
    llm_fake: bool = False  # dev and test only: canned replies, no provider call
    tutor_model: str = "claude-sonnet-5-5"
    fast_model: str = "claude-haiku-5-5"
    tutor_effort: Literal["low", "medium", "high"] = "medium"
    tutor_max_output_tokens: int = 1500
    tutor_timeout_seconds: float = 90
    fast_timeout_seconds: float = 6
    tutor_name: str = "SST Virtual Tutor"
    disclose_model_provider: bool = True
    prompts_dir: str = "prompts"
    usd_chf_rate: float = 0.80  # for cost logging only; update occasionally
    ai_monthly_budget_chf: float = 300
    ai_student_alert_chf: float = 8
    safeguarding_email: str = ""  # empty: every admin account is notified
    max_student_message_chars: int = 2000
    conversation_window_turns: int = 20

    # Other providers (later phases)
    screening_api_key: str = ""
    tutorcruncher_api_key: str = ""
    tutorcruncher_sso_key: str = ""

    @field_validator("tutor_model", "fast_model", "tutor_effort", mode="before")
    @classmethod
    def _empty_means_default(cls, v: object, info) -> object:
        """`TUTOR_MODEL=` in a .env file must not override the default with an empty name."""
        if isinstance(v, str) and not v.strip():
            return cls.model_fields[info.field_name].default
        return v

    @property
    def cookies_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env not in ("dev", "test")

    @property
    def impersonation_enabled(self) -> bool:
        """Admin "view as" is a staging and development aid only."""
        return self.app_env in ("dev", "test", "staging")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
