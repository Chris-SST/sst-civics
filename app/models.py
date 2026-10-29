"""Database models. Portable column types so tests can run on SQLite and
production on PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, Uuid
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
