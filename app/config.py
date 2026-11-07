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
    session_cookie_name: str = "viapunt_session"
    csrf_cookie_name: str = "viapunt_csrf"
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
    # Cantons whose Viapunt Pass is on sale, comma-separated lower-case codes. A canton is
    # added once its question content exists.
    cantons_for_sale: str = "zh,ch"  # "ch": Rest of Switzerland, federal questions only
    # Refund rule (plan, "Payments and pricing"): within this many days of purchase, if
    # fewer than this many questions have been studied since.
    refund_window_days: int = 14
    refund_max_questions_studied: int = 50
    # An extension may be bought while a pass is active or up to this many days after it
    # expired.
    extension_grace_days: int = 90

    # Email
    email_backend: Literal["console", "smtp", "memory"] = "console"
    email_from: str = "Viapunt <noreply@viapunt.ch>"
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
    # Explain this and the help chat are grounded in our own material, so the fast model
    # is enough (D-066); `tutor_model` is left for the general topic chat.
    explain_model: str = "claude-haiku-5-5"
    help_model: str = "claude-haiku-5-5"
    chat_effort: Literal["low", "medium", "high"] = "low"  # for those two: quick replies
    tutor_effort: Literal["low", "medium", "high"] = "medium"
    tutor_max_output_tokens: int = 1500
    tutor_timeout_seconds: float = 90
    fast_timeout_seconds: float = 6
    tutor_name: str = "Viapunt"
    disclose_model_provider: bool = True
    prompts_dir: str = "prompts"
    content_dir: str = "content"  # question, topic and translation files (D-041)
    usd_chf_rate: float = 0.80  # for cost logging only; update occasionally
    ai_monthly_budget_chf: float = 300
    ai_learner_alert_chf: float = 8
    max_student_message_chars: int = 2000
    # AI messages a day. With an active entitlement: Explain this and the help chat together.
    # Without one, two separate allowances: the help chat (0 switches it off) and Explain this
    # on the free sample questions (0 switches it off).
    ai_daily_message_limit: int = 20
    ai_free_daily_message_limit: int = 5
    ai_free_explain_daily_limit: int = 3
    # The public help chat on the guide site (D-067): messages per visitor address a day
    # (0 switches it off), all visitors together a day, and the longest message accepted.
    public_help_per_ip_daily: int = 5
    public_help_daily_total: int = 300
    public_help_max_chars: int = 600
    # The public guide site; the help chat links to its pages.
    guide_base_url: str = "https://viapunt.ch"
    # Daily operations digest for the owner (D-072): yesterday's numbers, service checks and
    # a short summary from the fast model, emailed each morning by the worker. Recipients are
    # comma-separated; empty means every active admin.
    digest_enabled: bool = True
    digest_to: str = ""
    # Read access to the Umami database for visit counts; empty skips the visits section.
    umami_database_url: str = ""
    umami_website_id: str = ""
    umami_heartbeat_url: str = "http://umami:3000/api/heartbeat"
    backup_dir: str = "/backups"  # the backup volume, mounted read-only into the worker
    # Article pipeline (D-073, docs/articles-contract.md): the worker writes, fact-checks,
    # translates and publishes the articles of content/articles/plan.yaml. Off unless enabled.
    # The proposal email goes to ARTICLES_REVIEW_TO (comma-separated), else to the digest
    # recipients. The worker needs ARTICLES_DIR read-write and the builder's status file.
    articles_enabled: bool = False
    articles_dir: str = "/srv/articles"
    sitebuild_status_file: str = "/srv/site-releases/build-status.json"
    articles_review_to: str = ""
    articles_write_model: str = "claude-opus-5-5"  # writing and the fix rounds
    articles_review_model: str = "claude-opus-5-5"  # the independent fact review
    articles_translate_model: str = "claude-sonnet-5-5"
    articles_translation_review_model: str = "claude-opus-5-5"
    articles_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    articles_translate_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    articles_cost_cap_chf: float = 6.0  # per production run (first version or one revision)
    articles_lead_days: int = 4  # production starts this long before publish_at
    articles_proposal_hours: int = 24  # the proposal goes out this long before publication
    articles_languages: str = "de,fr,it,pt,es,sq,tr"  # translations; English always exists
    articles_build_timeout_minutes: int = 20  # waiting for the site builder
    articles_indexnow: bool = True  # ping IndexNow after publishing (production only)
    # Politics in your canton (D-074, docs/politics-contract.md): weekly round-ups, vote
    # explainers and the who's who, found on the authorities' pages and published without a
    # proposal email once the neutrality and fact reviews pass. Off unless enabled.
    politics_enabled: bool = False
    politics_cantons: str = "zh"  # cantons with a block in content/politics/sources.yaml
    politics_cost_cap_chf: float = 4.0  # per production run of one page
    politics_write_model: str = "claude-opus-5-5"  # writing and fixes
    politics_review_model: str = "claude-opus-5-5"  # neutrality and fact reviews
    politics_select_model: str = "claude-sonnet-5-5"  # picking the items of the week
    politics_extract_model: str = "claude-haiku-5-5"  # links, proposals, results, rosters
    politics_question_model: str = "claude-opus-5-5"  # the practice questions
    politics_question_check_model: str = "claude-sonnet-5-5"  # their independent check
    politics_vote_lead_days: int = 28  # vote explainers go out this long before the vote
    serve_unreviewed_questions: bool = False  # staging/dev: also serve in_review questions
    practice_round_size: int = 5  # questions per Practise round
    conversation_window_turns: int = 20

    @field_validator(
        "tutor_model",
        "fast_model",
        "explain_model",
        "help_model",
        "tutor_effort",
        "chat_effort",
        "articles_write_model",
        "articles_review_model",
        "articles_translate_model",
        "articles_translation_review_model",
        "articles_effort",
        "articles_translate_effort",
        "politics_write_model",
        "politics_review_model",
        "politics_select_model",
        "politics_extract_model",
        "politics_question_model",
        "politics_question_check_model",
        mode="before",
    )
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
    def article_languages(self) -> tuple[str, ...]:
        """Translation languages, in the order given, without English or unknown codes."""
        known = ("de", "fr", "it", "pt", "es", "sq", "tr")
        out = [c.strip().lower() for c in self.articles_languages.split(",")]
        return tuple(dict.fromkeys(c for c in out if c in known))

    @property
    def politics_canton_codes(self) -> tuple[str, ...]:
        return tuple(c.strip().lower() for c in self.politics_cantons.split(",") if c.strip())

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
