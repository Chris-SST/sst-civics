"""Initial schema: families, users, sessions, tokens, plans, Stripe events, payments, audit.

Revision ID: 0001
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "families",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("terms_version", sa.String(40)),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("guardian_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("stripe_customer_id", sa.String(64)),
        sa.Column("stripe_subscription_id", sa.String(64)),
        sa.Column("plan_key", sa.String(40)),
        sa.Column("subscription_status", sa.String(32)),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("trial_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("past_due_since", sa.DateTime(timezone=True)),
        sa.Column("payment_warning", sa.Boolean(), nullable=False),
        sa.Column("free_access_until", sa.DateTime(timezone=True)),
        sa.Column("free_access_reason", sa.String(200)),
        sa.Column("tutor_credits", sa.Integer(), nullable=False),
        sa.Column("exam_sprint_purchased_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_families_stripe_customer_id", "families", ["stripe_customer_id"], unique=True
    )
    op.create_index(
        "ix_families_stripe_subscription_id", "families", ["stripe_subscription_id"], unique=True
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id")),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("username", sa.String(40)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("year_of_birth", sa.Integer()),
        sa.Column("curriculum", sa.String(40)),
        sa.Column("courses", sa.JSON()),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("tagged_courses", sa.JSON()),
        sa.Column("available", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_users_family_id", "users", ["family_id"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfa_pending", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "one_time_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_one_time_tokens_user_id", "one_time_tokens", ["user_id"])

    op.create_table(
        "plans",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("monthly_message_limit", sa.Integer()),
        sa.Column("daily_message_limit", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_stripe_events_type", "stripe_events", ["type"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("family_id", sa.Uuid(), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(64), nullable=False, unique=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payments_family_id", "payments", ["family_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("meta", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])


def downgrade() -> None:
    for name in (
        "audit_log",
        "payments",
        "stripe_events",
        "plans",
        "one_time_tokens",
        "sessions",
        "users",
        "families",
    ):
        op.drop_table(name)
