"""Database models. Portable column types so tests can run on SQLite and
production on PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto import EncryptedString
from app.db import Base, TZDateTime, utcnow

ROLE_LEARNER = "learner"
ROLE_ADMIN = "admin"
ROLES = (ROLE_LEARNER, ROLE_ADMIN)
# Languages with tutor topic names and email texts today; others fall back to English.
LOCALES = ("en", "de", "fr")
# Interface and study languages a learner can choose (D-014, widening D-020).
LANGUAGES = ("de", "en", "fr", "it", "pt", "es", "sq", "tr")
STUDY_LANGUAGES = LANGUAGES
# Two-letter canton codes, lower case.
CANTONS = (
    "ag", "ai", "ar", "be", "bl", "bs", "fr", "ge", "gl", "gr", "ju", "lu", "ne",
    "nw", "ow", "sg", "sh", "so", "sz", "tg", "ti", "ur", "vd", "vs", "zg", "zh",
)  # fmt: skip
DEFAULT_CANTON = "zh"

TOKEN_VERIFY_EMAIL = "verify_email"  # noqa: S105
TOKEN_RESET_PASSWORD = "reset_password"  # noqa: S105
TOKEN_SIGN_IN = "sign_in"  # noqa: S105

ENTITLEMENT_STRIPE = "stripe"
ENTITLEMENT_ADMIN = "admin"
ENTITLEMENT_TRIAL = "trial"
ENTITLEMENT_SOURCES = (ENTITLEMENT_STRIPE, ENTITLEMENT_ADMIN, ENTITLEMENT_TRIAL)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class User(TimestampMixin, Base):
    """A learner (who signs up and pays for themselves) or an admin. Holds only email,
    interface language, study language, canton and the age declaration."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    role: Mapped[str] = mapped_column(String(16), index=True, default=ROLE_LEARNER)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(5), default="en")
    study_language: Mapped[str] = mapped_column(String(5), default="en")
    canton: Mapped[str] = mapped_column(String(2), default=DEFAULT_CANTON)
    # Self-declared "16 or older" at sign-up. No date of birth is ever stored.
    age_confirmed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    terms_version: Mapped[str | None] = mapped_column(String(40))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # Two-factor authentication (TOTP). Mandatory for admins. The secret is encrypted at
    # rest (D-011); the attribute holds the plain secret, the column the ciphertext.
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString(255))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    entitlements: Mapped[list[Entitlement]] = relationship(
        back_populates="user",
        lazy="selectin",
        order_by="Entitlement.expires_at",
        cascade="all, delete-orphan",
    )

    @property
    def is_staff(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_learner(self) -> bool:
        return self.role == ROLE_LEARNER


class Entitlement(Base):
    """Access to one canton's content for a period: bought, granted by an admin, or a trial."""

    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canton: Mapped[str] = mapped_column(String(2), index=True)
    starts_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime)
    source: Mapped[str] = mapped_column(String(16))  # stripe | admin | trial
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="entitlements")


class Session(Base):
    """Server-side session. The cookie carries a random token; we store its hash."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of the token
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    mfa_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    # When this session was opened from a one-time email link. Account deletion accepts a
    # link consumed in the last 10 minutes as re-authentication.
    email_link_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # Set when an admin is viewing the app as this user (never in production).
    impersonator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class OneTimeToken(Base):
    """Single-use tokens for email verification, sign-in links and password reset."""

    __tablename__ = "one_time_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime)
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class StripeEvent(Base):
    """Every webhook event we have accepted, for idempotency and audit."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class Payment(Base):
    """One paid Civics Pass or extension, from a Stripe Checkout Session in payment mode."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    # Billing records survive account deletion.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # The entitlement this payment created or extended; a refund shortens it.
    entitlement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entitlements.id", ondelete="SET NULL"), index=True
    )
    product: Mapped[str] = mapped_column(String(40))  # Stripe lookup key
    canton: Mapped[str] = mapped_column(String(2))
    months: Mapped[int] = mapped_column(Integer)  # access the payment added
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(255), unique=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    paid_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    amount_refunded_cents: Mapped[int] = mapped_column(Integer, default=0)
    refunded_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # Set when the account is deleted: a keyed hash of the email address, so the record can
    # still be matched to the person if they ask, without keeping the address itself.
    email_hash: Mapped[str | None] = mapped_column(String(64))


class AuditLog(Base):
    """Admin and support actions. Never contains message content."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


# --- Phase 1: tutor conversations and AI call log -----------------------------------------

CONVERSATION_ACTIVE = "active"
CONVERSATION_ENDED = "ended"

MESSAGE_USER = "user"
MESSAGE_ASSISTANT = "assistant"
MESSAGE_NOTICE = "notice"  # fixed server replies (off topic, limits), never sent to the model


class Conversation(Base):
    """One tutoring session, always started from a course and topic."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_key: Mapped[str] = mapped_column(String(40))
    topic_code: Mapped[str] = mapped_column(String(20))
    topic_name: Mapped[str] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(5), default="en")
    title: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(16), default=CONVERSATION_ACTIVE)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_upto_seq: Mapped[int] = mapped_column(Integer, default=0)
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    off_topic_streak: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.seq"
    )


class Message(Base):
    """A turn in a conversation. Content lives only here, never in logs."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    gate_label: Mapped[str | None] = mapped_column(String(20))
    counted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class LlmCall(Base):
    """One call to the AI provider: tokens, cost and latency. No content."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    purpose: Mapped[str] = mapped_column(String(32))  # tutor_reply | gatekeeper | summary
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | refusal | error
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_chf: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class CostAlert(Base):
    """One alert email per threshold, scope and month."""

    __tablename__ = "cost_alerts"
    __table_args__ = (UniqueConstraint("kind", "scope", "period", name="uq_cost_alert"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))  # learner | budget
    scope: Mapped[str] = mapped_column(String(64))  # user id or "all"
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    amount_chf: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


# --- Phase 1: question bank, attempts, mastery -----------------------------------------

Q_DRAFT = "draft"
Q_AUTO_VERIFIED = "auto_verified"
Q_NEEDS_REVIEW = "needs_review"
Q_APPROVED = "approved"
Q_RETIRED = "retired"
QUESTION_STATUSES = (Q_DRAFT, Q_AUTO_VERIFIED, Q_NEEDS_REVIEW, Q_APPROVED, Q_RETIRED)

QTYPE_MCQ = "mcq"
QUESTION_TYPES = (QTYPE_MCQ,)  # multiple choice with four options is the only kind

ATTEMPT_DIAGNOSTIC = "diagnostic"
ATTEMPT_PRACTICE = "practice"
ATTEMPT_CHECK = "check"  # check questions at the end of a tutor session


class GenerationBatch(Base):
    """One request to generate questions, either through the provider's Batch API or
    directly in the worker."""

    __tablename__ = "generation_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    provider_batch_id: Mapped[str | None] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(10), default="batch")  # batch | direct
    module_key: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[str] = mapped_column(String(4), default="both")  # sl | hl | both
    topic_codes: Mapped[list[str]] = mapped_column(JSON)
    difficulties: Mapped[list[int]] = mapped_column(JSON)
    per_request: Mapped[int] = mapped_column(Integer, default=5)
    language: Mapped[str] = mapped_column(String(5), default="en")
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    requests: Mapped[int] = mapped_column(Integer, default=0)
    questions_created: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    module_key: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[str] = mapped_column(String(4), default="both")  # sl | hl | both
    topic_code: Mapped[str] = mapped_column(String(20), index=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)  # 1 to 5
    qtype: Mapped[str] = mapped_column(String(12), default=QTYPE_MCQ)
    language: Mapped[str] = mapped_column(String(5), default="en")
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON
    )  # [{key, text}], four entries
    answer: Mapped[str] = mapped_column(Text)
    worked_solution: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default=Q_DRAFT, index=True)
    spot_check: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(16), default="generated")
    prompt_version: Mapped[str] = mapped_column(String(80), default="")
    check_results: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    solve_answer: Mapped[str | None] = mapped_column(Text)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generation_batches.id", ondelete="SET NULL")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    review_minutes: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)


class QuestionReport(Base):
    __tablename__ = "question_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Attempt(Base):
    """A learner's answer to a question, in a diagnostic, in practice, or as a check at
    the end of a tutor session."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    course_key: Mapped[str] = mapped_column(String(40))
    topic_code: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(12), default=ATTEMPT_PRACTICE)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0 to 1
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    diagnostic_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class TopicMastery(Base):
    __tablename__ = "topic_mastery"
    __table_args__ = (UniqueConstraint("user_id", "course_key", "topic_code", name="uq_mastery"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_key: Mapped[str] = mapped_column(String(40))
    topic_code: Mapped[str] = mapped_column(String(20))
    rating: Mapped[float] = mapped_column(Float, default=1000.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    next_review_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class DiagnosticRun(Base):
    __tablename__ = "diagnostic_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    question_ids: Mapped[list[str]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
