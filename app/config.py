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
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # Data stores
    database_url: str = "postgresql+asyncpg://sst:sst@localhost:5432/sst"
    redis_url: str = "redis://localhost:6379/0"
    jobs_inline: bool = False  # run background jobs in-process (dev without Redis, tests)

    # Sessions and security
    session_cookie_name: str = "sst_session"
    csrf_cookie_name: str = "sst_csrf"
    session_ttl_hours: int = 24 * 14  # learners
    staff_session_ttl_hours: int = 12  # admins
    cookie_secure: bool | None = None  # None means secure unless app_env is dev or test
    terms_version: str = "2026-10-draft"
    login_rate_limit: int = 10  # attempts per window per identifier and per IP
    login_rate_window_seconds: int = 900
    # One-time sign-in links: requests per hour per email address and per IP address.
    link_rate_limit_per_email: int = 5
    link_rate_limit_per_ip: int = 20
    link_consume_rate_limit: int = 30  # per IP per 15 minutes
    # Key material for encrypting TOTP secrets at rest. Empty means derived from SECRET_KEY.
    # Changing either one makes stored secrets unreadable: admins must set up 2FA again.
    totp_encryption_key: str = ""

    # Stripe (test mode until go-live is approved)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_version: str = "2026-05-27.dahlia"
    # Cantons whose Civics Pass is on sale, comma-separated lower-case codes. A canton is
    # added once its question content exists.
    cantons_for_sale: str = "zh"
    # Refund rule (plan, "Payments and pricing"): within this many days of purchase, if
    # fewer than this many questions have been studied since.
    refund_window_days: int = 14
    refund_max_questions_studied: int = 50
    # An extension may be bought while a pass is active or up to this many days after it
    # expired.
    extension_grace_days: int = 90

    # Email
    email_backend: Literal["console", "smtp", "memory"] = "console"
    email_from: str = "Civics Trainer <noreply@example.ch>"
    email_outbox_dir: str = "var/outbox"
    email_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # AI tutor. Every call goes through app/llm; an empty key disables the tutor.
    anthropic_api_key: str = ""
    llm_fake: bool = False  # dev and test only: canned replies, no provider call
    tutor_model: str = "claude-sonnet-5-5"
    fast_model: str = "claude-haiku-5-5"
    tutor_effort: Literal["low", "medium", "high"] = "medium"
    tutor_max_output_tokens: int = 1500
    tutor_timeout_seconds: float = 90
    fast_timeout_seconds: float = 6
    tutor_name: str = "Civics Trainer"
    disclose_model_provider: bool = True
    prompts_dir: str = "prompts"
    content_dir: str = "content"  # question, topic and translation files (D-041)
    usd_chf_rate: float = 0.80  # for cost logging only; update occasionally
    ai_monthly_budget_chf: float = 300
    ai_learner_alert_chf: float = 8
    max_student_message_chars: int = 2000
    # "Explain this" messages a day for every learner with an active entitlement.
    ai_daily_message_limit: int = 20
    serve_unreviewed_questions: bool = False  # staging/dev: also serve in_review questions
    diagnostic_questions_per_topic: int = 1
    practice_round_size: int = 5
    conversation_window_turns: int = 20

    @field_validator("tutor_model", "fast_model", "tutor_effort", mode="before")
    @classmethod
    def _empty_means_default(cls, v: object, info) -> object:
        """`TUTOR_MODEL=` in a .env file must not override the default with an empty name."""
        if isinstance(v, str) and not v.strip():
            return cls.model_fields[info.field_name].default
        return v

    @property
    def unreviewed_questions_allowed(self) -> bool:
        return self.serve_unreviewed_questions and self.app_env != "production"

    @property
    def cantons_on_sale(self) -> tuple[str, ...]:
        return tuple(c.strip().lower() for c in self.cantons_for_sale.split(",") if c.strip())

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
