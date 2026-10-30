"""Initial schema for the citizenship-test trainer.

Learners and admins, entitlements per canton, sessions, tokens, Stripe events, one-off
Civics Pass payments, audit log, chat conversations, AI call log, cost alerts, and the question
bank filled from content/ (topics, questions, translations, glossary, reports), attempts,
progress per question and study mode, and mock-test runs.
Replaces the source app's migrations 0001 to 0004 (D-005). Rewritten in place for the question
model in Phase 1 task 1.1 and for the study modes, progress and mock test in tasks 1.7 to 1.9,
before any production data existed (D-044); staging's database is recreated.

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
        # Encrypted at rest (app.crypto.EncryptedString), D-011.
        sa.Column("totp_secret", sa.String(255)),
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
        sa.Column(
            "entitlement_id", sa.Uuid(), sa.ForeignKey("entitlements.id", ondelete="SET NULL")
        ),
        sa.Column("product", sa.String(40), nullable=False),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255)),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_refunded_cents", sa.Integer(), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True)),
        sa.Column("email_hash", sa.String(64)),
        sa.UniqueConstraint("stripe_checkout_session_id"),
    )
    op.create_index("ix_payments_entitlement_id", "payments", ["entitlement_id"], unique=False)
    op.create_index(
        "ix_payments_stripe_payment_intent_id",
        "payments",
        ["stripe_payment_intent_id"],
        unique=False,
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
        sa.Column("email_link_at", sa.DateTime(timezone=True)),
        sa.Column("impersonator_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    op.create_index(
        "ix_sessions_impersonator_user_id", "sessions", ["impersonator_user_id"], unique=False
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("topic_code", sa.String(80), nullable=False),
        sa.Column("topic_name", sa.String(200), nullable=False),
        sa.Column("question_id", sa.String(80)),
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
    op.create_index("ix_conversations_question_id", "conversations", ["question_id"], unique=False)
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
        "mock_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("pass_mark", sa.Integer()),
        sa.Column("free", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("score", sa.Integer()),
    )
    op.create_index("ix_mock_runs_user_id", "mock_runs", ["user_id"], unique=False)
    # Question bank, filled from content/ by scripts/import_content.py (D-041).
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("name_de", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("target_questions", sa.Integer(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canton", "code", name="uq_topic_canton_code"),
    )
    op.create_index("ix_topics_canton", "topics", ["canton"], unique=False)
    op.create_index("ix_topics_code", "topics", ["code"], unique=False)
    op.create_table(
        "questions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("canton", sa.String(2)),
        sa.Column("topic_code", sa.String(80), nullable=False),
        sa.Column("question_de", sa.Text(), nullable=False),
        sa.Column("options_de", sa.JSON(), nullable=False),
        sa.Column("correct", sa.String(1), nullable=False),
        sa.Column("explanation_de", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("glossary", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("translations_missing", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("file_status", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_sync_pending", sa.Boolean(), nullable=False),
        sa.Column("pending_changes", sa.JSON()),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("review_minutes", sa.Integer(), nullable=False),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_canton", "questions", ["canton"], unique=False)
    op.create_index("ix_questions_scope", "questions", ["scope"], unique=False)
    op.create_index("ix_questions_status", "questions", ["status"], unique=False)
    op.create_index("ix_questions_topic_code", "questions", ["topic_code"], unique=False)
    op.create_table(
        "question_translations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(80),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewed_by", sa.String(120)),
        sa.Column("reviewed_at", sa.Date()),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("question_id", "lang", name="uq_translation_lang"),
    )
    op.create_index(
        "ix_question_translations_lang", "question_translations", ["lang"], unique=False
    )
    op.create_index(
        "ix_question_translations_question_id",
        "question_translations",
        ["question_id"],
        unique=False,
    )
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("term", sa.String(120), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("translation", sa.String(200), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("source", sa.String(300)),
        sa.Column("keep_german", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reviewed_by", sa.String(120)),
        sa.Column("reviewed_at", sa.Date()),
        sa.Column("file_sync_pending", sa.Boolean(), nullable=False),
        sa.Column("pending_changes", sa.JSON()),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("term", "lang", name="uq_glossary_term_lang"),
    )
    op.create_index("ix_glossary_terms_term", "glossary_terms", ["term"], unique=False)
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "question_id",
            sa.String(80),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic_code", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("study_mode", sa.String(8)),
        sa.Column("conversation_id", sa.Uuid()),
        sa.Column("mock_run_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_conversation_id", "attempts", ["conversation_id"], unique=False)
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"], unique=False)
    op.create_index("ix_attempts_mock_run_id", "attempts", ["mock_run_id"], unique=False)
    op.create_index("ix_attempts_question_id", "attempts", ["question_id"], unique=False)
    op.create_index("ix_attempts_user_id", "attempts", ["user_id"], unique=False)
    op.create_table(
        "question_progress",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "question_id",
            sa.String(80),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("mode_reached", sa.String(8), nullable=False),
        sa.Column("correct_own", sa.Integer(), nullable=False),
        sa.Column("correct_side", sa.Integer(), nullable=False),
        sa.Column("correct_help", sa.Integer(), nullable=False),
        sa.Column("correct_de", sa.Integer(), nullable=False),
        sa.Column("wrong", sa.Integer(), nullable=False),
        sa.Column("last_correct_de_date", sa.Date()),
        sa.Column("understood", sa.Boolean(), nullable=False),
        sa.Column("known", sa.Boolean(), nullable=False),
        sa.Column("box", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("last_answered_at", sa.DateTime(timezone=True)),
        sa.Column("seen_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "question_id", name="uq_question_progress"),
    )
    op.create_index(
        "ix_question_progress_question_id", "question_progress", ["question_id"], unique=False
    )
    op.create_index("ix_question_progress_user_id", "question_progress", ["user_id"], unique=False)
    op.create_table(
        "question_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_id",
            sa.String(80),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("lang", sa.String(5)),
        sa.Column("comment", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_question_reports_question_id", "question_reports", ["question_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_question_reports_question_id", table_name="question_reports")
    op.drop_table("question_reports")
    op.drop_index("ix_attempts_conversation_id", table_name="attempts")
    op.drop_index("ix_attempts_created_at", table_name="attempts")
    op.drop_index("ix_attempts_mock_run_id", table_name="attempts")
    op.drop_index("ix_attempts_question_id", table_name="attempts")
    op.drop_index("ix_attempts_user_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_question_progress_question_id", table_name="question_progress")
    op.drop_index("ix_question_progress_user_id", table_name="question_progress")
    op.drop_table("question_progress")
    op.drop_index("ix_glossary_terms_term", table_name="glossary_terms")
    op.drop_table("glossary_terms")
    op.drop_index("ix_question_translations_lang", table_name="question_translations")
    op.drop_index("ix_question_translations_question_id", table_name="question_translations")
    op.drop_table("question_translations")
    op.drop_index("ix_questions_canton", table_name="questions")
    op.drop_index("ix_questions_scope", table_name="questions")
    op.drop_index("ix_questions_status", table_name="questions")
    op.drop_index("ix_questions_topic_code", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_topics_canton", table_name="topics")
    op.drop_index("ix_topics_code", table_name="topics")
    op.drop_table("topics")
    op.drop_index("ix_mock_runs_user_id", table_name="mock_runs")
    op.drop_table("mock_runs")
    op.drop_index("ix_conversations_question_id", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_sessions_impersonator_user_id", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_stripe_payment_intent_id", table_name="payments")
    op.drop_index("ix_payments_entitlement_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_one_time_tokens_user_id", table_name="one_time_tokens")
    op.drop_table("one_time_tokens")
    op.drop_index("ix_llm_calls_conversation_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_user_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("ix_entitlements_canton", table_name="entitlements")
    op.drop_index("ix_entitlements_stripe_checkout_session_id", table_name="entitlements")
    op.drop_index("ix_entitlements_user_id", table_name="entitlements")
    op.drop_table("entitlements")
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_stripe_events_type", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_table("cost_alerts")
