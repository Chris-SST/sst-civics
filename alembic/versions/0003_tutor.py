"""Phase 1: conversations, messages, AI call log, safety flags, cost alerts.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("tutor_notice_seen_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("topic_name", sa.String(120), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_upto_seq", sa.Integer(), nullable=False),
        sa.Column("next_seq", sa.Integer(), nullable=False),
        sa.Column("off_topic_streak", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_student_id", "conversations", ["student_id"])

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
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("gate_label", sa.String(20), nullable=True),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_student_id", "messages", ["student_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
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
    op.create_index("ix_llm_calls_student_id", "llm_calls", ["student_id"])
    op.create_index("ix_llm_calls_conversation_id", "llm_calls", ["conversation_id"])
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])

    op.create_table(
        "safety_flags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_safety_flags_student_id", "safety_flags", ["student_id"])
    op.create_index("ix_safety_flags_conversation_id", "safety_flags", ["conversation_id"])
    op.create_index("ix_safety_flags_created_at", "safety_flags", ["created_at"])

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


def downgrade() -> None:
    op.drop_table("cost_alerts")
    op.drop_index("ix_safety_flags_created_at", table_name="safety_flags")
    op.drop_index("ix_safety_flags_conversation_id", table_name="safety_flags")
    op.drop_index("ix_safety_flags_student_id", table_name="safety_flags")
    op.drop_table("safety_flags")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_index("ix_llm_calls_conversation_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_student_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_student_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_student_id", table_name="conversations")
    op.drop_table("conversations")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("tutor_notice_seen_at")
