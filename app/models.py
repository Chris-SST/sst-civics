"""Database models. Portable column types so tests can run on SQLite and
production on PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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


# --- Chat conversations and AI call log ------------------------------------------------

CONVERSATION_ACTIVE = "active"
CONVERSATION_ENDED = "ended"

MESSAGE_USER = "user"
MESSAGE_ASSISTANT = "assistant"
MESSAGE_NOTICE = "notice"  # fixed server replies (off topic, limits), never sent to the model


class Conversation(Base):
    """One chat session, always started from a topic of the learner's canton."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canton: Mapped[str] = mapped_column(String(2))
    topic_code: Mapped[str] = mapped_column(String(80))
    topic_name: Mapped[str] = mapped_column(String(200))
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


# --- Question bank (filled from content/ on deploy), attempts, progress, mock tests ------

# Status of a question in its file (content/questions/) and, after admin review, in the
# database. Only approved questions are served (in_review too on staging, see settings).
# needs_fix: the content pipeline or a reviewer found a problem (never served).
Q_DRAFT = "draft"
Q_NEEDS_FIX = "needs_fix"
Q_IN_REVIEW = "in_review"
Q_APPROVED = "approved"
Q_RETIRED = "retired"
QUESTION_STATUSES = (Q_DRAFT, Q_NEEDS_FIX, Q_IN_REVIEW, Q_APPROVED, Q_RETIRED)

# flagged: the back-translation differs in meaning; a reviewer must look (never served).
T_DRAFT = "draft"
T_FLAGGED = "flagged"
T_IN_REVIEW = "in_review"
T_APPROVED = "approved"
TRANSLATION_STATUSES = (T_DRAFT, T_FLAGGED, T_IN_REVIEW, T_APPROVED)

SCOPE_FEDERAL = "federal"
SCOPE_CANTON = "canton"
SCOPE_COMMUNE = "commune"
TOPIC_SCOPES = (SCOPE_FEDERAL, SCOPE_CANTON, SCOPE_COMMUNE)

OPTION_KEYS = ("a", "b", "c", "d")
# Content languages: German is the master, every other launch language is a translation.
CONTENT_MASTER_LANGUAGE = "de"
TRANSLATION_LANGUAGES = tuple(lang for lang in LANGUAGES if lang != CONTENT_MASTER_LANGUAGE)

ATTEMPT_PRACTICE = "practice"
ATTEMPT_MOCK = "mock"
ATTEMPT_CHECK = "check"  # check questions at the end of a chat session

# Study modes (PLAN.md, Languages), in the order a question moves through them as the
# learner answers it correctly: own language, side by side, German with help, German only.
MODE_OWN = "own"
MODE_SIDE = "side"
MODE_HELP = "help"
MODE_DE = "de"
STUDY_MODES = (MODE_OWN, MODE_SIDE, MODE_HELP, MODE_DE)

MOCK_IN_PROGRESS = "in_progress"
MOCK_FINISHED = "finished"  # handed in by the learner
MOCK_EXPIRED = "expired"  # the deadline passed first; scored on the answers saved in time
MOCK_STATUSES = (MOCK_IN_PROGRESS, MOCK_FINISHED, MOCK_EXPIRED)


class Topic(Base):
    """One entry of a canton's topic file (content/topics/<canton>.yaml). Federal topics
    appear in every canton's file, so the key is (canton, code)."""

    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("canton", "code", name="uq_topic_canton_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    canton: Mapped[str] = mapped_column(String(2), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    scope: Mapped[str] = mapped_column(String(10))  # federal | canton | commune
    name_de: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))
    target_questions: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)  # order in the file
    content_hash: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)

    def display(self, locale: str) -> str:
        return self.name_de if locale == "de" else self.name_en


class Question(Base):
    """A question as imported from content/questions/<scope>/<id>.yaml. The file is the
    master copy: admin review changes the status here and records the change in
    `pending_changes` until the pipeline writes it back to the file (task 1.5)."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # stable slug
    version: Mapped[int] = mapped_column(Integer, default=1)
    scope: Mapped[str] = mapped_column(String(40), index=True)  # federal | zh | zh-<commune>
    canton: Mapped[str | None] = mapped_column(String(2), index=True)  # null for federal
    topic_code: Mapped[str] = mapped_column(String(80), index=True)
    question_de: Mapped[str] = mapped_column(Text)
    options_de: Mapped[dict[str, str]] = mapped_column(JSON)  # {"a": ..., "b": ..., ...}
    correct: Mapped[str] = mapped_column(String(1))
    explanation_de: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)  # [{url, checked}]
    glossary: Mapped[list[str]] = mapped_column(JSON, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1 to 3
    translations_missing: Mapped[bool] = mapped_column(Boolean, default=False)
    # The status the app uses, and the status written in the file at the last import.
    status: Mapped[str] = mapped_column(String(16), default=Q_DRAFT, index=True)
    file_status: Mapped[str] = mapped_column(String(16), default=Q_DRAFT)
    content_hash: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    # Admin actions not yet in the file: the pipeline must write them back (task 1.5).
    file_sync_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    review_minutes: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)

    def options_list(self) -> list[dict[str, str]]:
        return [{"key": k, "text": self.options_de.get(k, "")} for k in OPTION_KEYS]


class QuestionTranslation(Base):
    """A translation file (content/translations/<lang>/<id>.yaml). Hidden when it was made
    from an older German version than the one now imported."""

    __tablename__ = "question_translations"
    __table_args__ = (UniqueConstraint("question_id", "lang", name="uq_translation_lang"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(5), index=True)
    source_version: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[dict[str, str]] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=T_DRAFT)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[date | None] = mapped_column(Date)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class GlossaryTerm(Base):
    """A key German term with its translation and a short note (content/glossary/)."""

    __tablename__ = "glossary_terms"
    __table_args__ = (UniqueConstraint("term", "lang", name="uq_glossary_term_lang"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    term: Mapped[str] = mapped_column(String(120), index=True)
    lang: Mapped[str] = mapped_column(String(5))
    translation: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)


class QuestionReport(Base):
    """A learner's flag on a question or, with `lang`, on one of its translations."""

    __tablename__ = "question_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    lang: Mapped[str | None] = mapped_column(String(5))
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Attempt(Base):
    """A learner's answer to a question: in Practise, in a mock test, or as a check at the end
    of a chat session. `study_mode` is the mode the question was shown in."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    topic_code: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(12), default=ATTEMPT_PRACTICE)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0 to 1
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    study_mode: Mapped[str | None] = mapped_column(String(8))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    mock_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, index=True)


class QuestionProgress(Base):
    """Progress per learner and question (PLAN.md, Languages). `mode` is the study mode the
    question is shown in next; a correct answer moves it one mode forward and the learner can
    step back at any time. `understood`: answered correctly in the learner's language (own
    language or side by side). `known`: answered correctly in German only twice, on different
    days (Zurich calendar days). `box` and `due_at` schedule the next review (Leitner boxes,
    app.study.progress)."""

    __tablename__ = "question_progress"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_question_progress"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(8), default=MODE_OWN)
    mode_reached: Mapped[str] = mapped_column(String(8), default=MODE_OWN)
    correct_own: Mapped[int] = mapped_column(Integer, default=0)
    correct_side: Mapped[int] = mapped_column(Integer, default=0)
    correct_help: Mapped[int] = mapped_column(Integer, default=0)
    correct_de: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    last_correct_de_date: Mapped[date | None] = mapped_column(Date)
    understood: Mapped[bool] = mapped_column(Boolean, default=False)
    known: Mapped[bool] = mapped_column(Boolean, default=False)
    box: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_answered_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    seen_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # last shown in Learn
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, onupdate=utcnow)


class MockRun(Base):
    """A mock test: German only, the canton's number of questions and time limit, a deadline
    set by the server at the start. Replaces the diagnostic runs (D-010). `answers` maps
    question id to the option key given; `free` marks the one mock test of the free tier."""

    __tablename__ = "mock_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    canton: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(16), default=MOCK_IN_PROGRESS)
    question_ids: Mapped[list[str]] = mapped_column(JSON)
    answers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    minutes: Mapped[int] = mapped_column(Integer)
    pass_mark: Mapped[int | None] = mapped_column(Integer)
    free: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow)
    deadline_at: Mapped[datetime] = mapped_column(TZDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    score: Mapped[int | None] = mapped_column(Integer)
