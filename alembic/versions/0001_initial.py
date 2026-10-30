"""Initial schema for the citizenship-test trainer.

Learners and admins, entitlements per canton, sessions, tokens, plans, Stripe events,
payments, audit log, tutor conversations, AI call log, cost alerts and the question bank.
Replaces the source app's migrations 0001 to 0004 (D-005). Until gate A this migration may be
rewritten in place.

Revision ID: 0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("amount_chf", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "scope", "period", name="uq_cost_alert"),
    )
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
    op.create_index("ix_stripe_events_type", "stripe_events", ["type"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("study_language", sa.String(5), nullable=False),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("terms_version", sa.String(40)),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("stripe_customer_id", sa.String(64)),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=True)
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
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("topic_name", sa.String(120), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("summary_upto_seq", sa.Integer(), nullable=False),
        sa.Column("next_seq", sa.Integer(), nullable=False),
        sa.Column("off_topic_streak", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], unique=False)
    op.create_table(
        "diagnostic_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_diagnostic_runs_user_id", "diagnostic_runs", ["user_id"], unique=False)
    op.create_table(
        "entitlements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entitlements_canton", "entitlements", ["canton"], unique=False)
    op.create_index(
        "ix_entitlements_stripe_checkout_session_id",
        "entitlements",
        ["stripe_checkout_session_id"],
        unique=False,
    )
    op.create_index("ix_entitlements_user_id", "entitlements", ["user_id"], unique=False)
    op.create_table(
        "generation_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_batch_id", sa.String(80)),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("module_key", sa.String(40), nullable=False),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("topic_codes", sa.JSON(), nullable=False),
        sa.Column("difficulties", sa.JSON(), nullable=False),
        sa.Column("per_request", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("questions_created", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_generation_batches_module_key", "generation_batches", ["module_key"], unique=False
    )
    op.create_index(
        "ix_generation_batches_provider_batch_id",
        "generation_batches",
        ["provider_batch_id"],
        unique=False,
    )
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("conversation_id", sa.Uuid()),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("cost_chf", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_calls_conversation_id", "llm_calls", ["conversation_id"], unique=False)
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"], unique=False)
    op.create_index("ix_llm_calls_user_id", "llm_calls", ["user_id"], unique=False)
    op.create_table(
        "one_time_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_one_time_tokens_user_id", "one_time_tokens", ["user_id"], unique=False)
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("stripe_invoice_id", sa.String(64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stripe_invoice_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
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
        sa.Column("impersonator_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_index(
        "ix_sessions_impersonator_user_id", "sessions", ["impersonator_user_id"], unique=False
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_table(
        "topic_mastery",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "course_key", "topic_code", name="uq_mastery"),
    )
    op.create_index("ix_topic_mastery_user_id", "topic_mastery", ["user_id"], unique=False)
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("gate_label", sa.String(20)),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)
    op.create_index("ix_messages_user_id", "messages", ["user_id"], unique=False)
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("module_key", sa.String(40), nullable=False),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("qtype", sa.String(12), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON()),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("worked_solution", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("spot_check", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("check_results", sa.JSON()),
        sa.Column("solve_answer", sa.Text()),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("generation_batches.id", ondelete="SET NULL")
        ),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("review_minutes", sa.Integer(), nullable=False),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_module_key", "questions", ["module_key"], unique=False)
    op.create_index("ix_questions_status", "questions", ["status"], unique=False)
    op.create_index("ix_questions_topic_code", "questions", ["topic_code"], unique=False)
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("conversation_id", sa.Uuid()),
        sa.Column("diagnostic_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_conversation_id", "attempts", ["conversation_id"], unique=False)
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"], unique=False)
    op.create_index("ix_attempts_diagnostic_id", "attempts", ["diagnostic_id"], unique=False)
    op.create_index("ix_attempts_question_id", "attempts", ["question_id"], unique=False)
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"], unique=False)
    op.create_table(
        "question_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("comment", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_question_reports_question_id", "question_reports", ["question_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_question_reports_question_id", table_name="question_reports")
    op.drop_table("question_reports")
    op.drop_index("ix_attempts_conversation_id", table_name="attempts")
    op.drop_index("ix_attempts_created_at", table_name="attempts")
    op.drop_index("ix_attempts_diagnostic_id", table_name="attempts")
    op.drop_index("ix_attempts_question_id", table_name="attempts")
    op.drop_index("ix_attempts_user_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_questions_module_key", table_name="questions")
    op.drop_index("ix_questions_status", table_name="questions")
    op.drop_index("ix_questions_topic_code", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_topic_mastery_user_id", table_name="topic_mastery")
    op.drop_table("topic_mastery")
    op.drop_index("ix_sessions_impersonator_user_id", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_one_time_tokens_user_id", table_name="one_time_tokens")
    op.drop_table("one_time_tokens")
    op.drop_index("ix_llm_calls_conversation_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_user_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("ix_generation_batches_module_key", table_name="generation_batches")
    op.drop_index("ix_generation_batches_provider_batch_id", table_name="generation_batches")
    op.drop_table("generation_batches")
    op.drop_index("ix_entitlements_canton", table_name="entitlements")
    op.drop_index("ix_entitlements_stripe_checkout_session_id", table_name="entitlements")
    op.drop_index("ix_entitlements_user_id", table_name="entitlements")
    op.drop_table("entitlements")
    op.drop_index("ix_diagnostic_runs_user_id", table_name="diagnostic_runs")
    op.drop_table("diagnostic_runs")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_stripe_events_type", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_table("plans")
    op.drop_table("cost_alerts")
