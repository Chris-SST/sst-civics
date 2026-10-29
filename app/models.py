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

from app.db import Base, TZDateTime, utcnow

ROLE_PARENT = "parent"
ROLE_STUDENT = "student"
ROLE_ADULT = "adult"
ROLE_TUTOR = "tutor"
ROLE_ADMIN = "admin"
ROLES = (ROLE_PARENT, ROLE_STUDENT, ROLE_ADULT, ROLE_TUTOR, ROLE_ADMIN)
STAFF_ROLES = (ROLE_TUTOR, ROLE_ADMIN)
PAYER_ROLES = (ROLE_PARENT, ROLE_ADULT)
LOCALES = ("en", "de", "fr")

TOKEN_VERIFY_EMAIL = "verify_email"  # noqa: S105
TOKEN_RESET_PASSWORD = "reset_password"  # noqa: S105
TOKEN_STUDENT_INVITE = "student_invite"  # noqa: S105
TOKEN_STAFF_INVITE = "staff_invite"  # noqa: S105


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class Family(TimestampMixin, Base):
    """One paying household (or one adult learner). Maps to one Stripe customer."""

    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    locale: Mapped[str] = mapped_column(String(5), default="en")
    terms_version: Mapped[str | None] = mapped_column(String(40))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    guardian_confirmed_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    plan_key: Mapped[str | None] = mapped_column(String(40))
    subscription_status: Mapped[str | None] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    current_period_end: Mapped[datetime | None] = mapped_column(TZDateTime)
    trial_end: Mapped[datetime | None] = mapped_column(TZDateTime)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    past_due_since: Mapped[datetime | None] = mapped_column(TZDateTime)
    payment_warning: Mapped[bool] = mapped_column(Boolean, default=False)

    free_access_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    free_access_reason: Mapped[str | None] = mapped_column(String(200))
    tutor_credits: Mapped[int] = mapped_column(Integer, default=0)
    exam_sprint_purchased_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    users: Mapped[list[User]] = relationship(back_populates="family")
    payments: Mapped[list[Payment]] = relationship(back_populates="family")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("families.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    username: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(80), default="")
    locale: Mapped[str] = mapped_column(String(5), default="en")

    # Student details (year of birth only, never a full date of birth)
    year_of_birth: Mapped[int | None] = mapped_column(Integer)
    curriculum: Mapped[str | None] = mapped_column(String(40))
    courses: Mapped[list[str] | None] = mapped_column(JSON)

    # Two-factor authentication (TOTP). Mandatory for tutors and admin.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    # Tutor profile (Phase 1 fills this in)
    tagged_courses: Mapped[list[str] | None] = mapped_column(JSON)
    available: Mapped[bool] = mapped_column(Boolean, default=True)

    # One-time notice shown the first time a student opens the tutor (D-025)
    tutor_notice_seen_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    family: Mapped[Family | None] = relationship(back_populates="users")

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_payer(self) -> bool:
        return self.role in PAYER_ROLES


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
    # Set when an admin is viewing the app as this user (never in production).
    impersonator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class OneTimeToken(Base):
    """Single-use tokens for email verification, password reset and student invites."""

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


class Plan(Base):
    """Plan limits, editable by admin. Prices live in Stripe and are looked up by key."""

    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # subscription | addon
    monthly_message_limit: Mapped[int | None] = mapped_column(Integer)
    daily_message_limit: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


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
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("families.id"), index=True)
    stripe_invoice_id: Mapped[str] = mapped_column(String(64), unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    paid_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    family: Mapped[Family] = relationship(back_populates="payments")


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


# --- Phase 1: tutor conversations, AI call log, safeguarding ---------------------------

CONVERSATION_ACTIVE = "active"
CONVERSATION_ENDED = "ended"

MESSAGE_USER = "user"
MESSAGE_ASSISTANT = "assistant"
MESSAGE_NOTICE = "notice"  # fixed server replies (off topic, limits), never sent to the model

FLAG_OPEN = "open"
FLAG_REVIEWED = "reviewed"
FLAG_DISMISSED = "dismissed"


class Conversation(Base):
    """One tutoring session, always started from a course and topic."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    student_id: Mapped[uuid.UUID] = mapped_column(
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
    student_id: Mapped[uuid.UUID] = mapped_column(
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
    student_id: Mapped[uuid.UUID | None] = mapped_column(
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


class SafetyFlag(Base):
    """A conversation flagged for the safeguarding lead. Admin only."""

    __tablename__ = "safety_flags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(32))  # wellbeing | override | abuse_material
    detail: Mapped[str | None] = mapped_column(String(64))  # self_harm, abuse, sexual, ...
    status: Mapped[str] = mapped_column(String(16), default=FLAG_OPEN)
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class CostAlert(Base):
    """One alert email per threshold, scope and month."""

    __tablename__ = "cost_alerts"
    __table_args__ = (UniqueConstraint("kind", "scope", "period", name="uq_cost_alert"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16))  # student | budget
    scope: Mapped[str] = mapped_column(String(64))  # student id or "all"
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
QTYPE_NUMERIC = "numeric"
QTYPE_SHORT = "short"  # an expression or short exact answer
QTYPE_STRUCTURED = "structured"  # marked against a mark scheme
QUESTION_TYPES = (QTYPE_MCQ, QTYPE_NUMERIC, QTYPE_SHORT, QTYPE_STRUCTURED)

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
    qtype: Mapped[str] = mapped_column(String(12), default=QTYPE_SHORT)
    calculator_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(5), default="en")
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict[str, str]] | None] = mapped_column(JSON)  # mcq: [{key, text}]
    answer: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(40))
    tolerance: Mapped[float | None] = mapped_column(Float)  # relative, numeric questions
    worked_solution: Mapped[str] = mapped_column(Text, default="")
    mark_scheme: Mapped[str | None] = mapped_column(Text)
    marks: Mapped[int] = mapped_column(Integer, default=1)
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
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Attempt(Base):
    """A student's answer to a question, in a diagnostic, in practice, or as a check at
    the end of a tutor session."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    student_id: Mapped[uuid.UUID] = mapped_column(
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
    feedback: Mapped[str | None] = mapped_column(Text)  # AI marking comment
    ai_marked: Mapped[bool] = mapped_column(Boolean, default=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    diagnostic_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class TopicMastery(Base):
    __tablename__ = "topic_mastery"
    __table_args__ = (
        UniqueConstraint("student_id", "course_key", "topic_code", name="uq_mastery"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    student_id: Mapped[uuid.UUID] = mapped_column(
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
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    question_ids: Mapped[list[str]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
