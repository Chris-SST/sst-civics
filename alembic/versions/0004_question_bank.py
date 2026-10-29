"""Question bank, attempts, mastery, diagnostics.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_batch_id", sa.String(80), nullable=True),
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
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_generation_batches_provider_batch_id", "generation_batches", ["provider_batch_id"])
    op.create_index("ix_generation_batches_module_key", "generation_batches", ["module_key"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("module_key", sa.String(40), nullable=False),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("qtype", sa.String(12), nullable=False),
        sa.Column("calculator_allowed", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("tolerance", sa.Float(), nullable=True),
        sa.Column("worked_solution", sa.Text(), nullable=False),
        sa.Column("mark_scheme", sa.Text(), nullable=True),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("spot_check", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("check_results", sa.JSON(), nullable=True),
        sa.Column("solve_answer", sa.Text(), nullable=True),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("generation_batches.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("review_minutes", sa.Integer(), nullable=False),
        sa.Column("report_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_module_key", "questions", ["module_key"])
    op.create_index("ix_questions_topic_code", "questions", ["topic_code"])
    op.create_index("ix_questions_status", "questions", ["status"])

    op.create_table(
        "question_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_question_reports_question_id", "question_reports", ["question_id"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("ai_marked", sa.Boolean(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("diagnostic_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_student_id", "attempts", ["student_id"])
    op.create_index("ix_attempts_question_id", "attempts", ["question_id"])
    op.create_index("ix_attempts_conversation_id", "attempts", ["conversation_id"])
    op.create_index("ix_attempts_diagnostic_id", "attempts", ["diagnostic_id"])
    op.create_index("ix_attempts_created_at", "attempts", ["created_at"])

    op.create_table(
        "topic_mastery",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("topic_code", sa.String(20), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "course_key", "topic_code", name="uq_mastery"),
    )
    op.create_index("ix_topic_mastery_student_id", "topic_mastery", ["student_id"])

    op.create_table(
        "diagnostic_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_diagnostic_runs_student_id", "diagnostic_runs", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_diagnostic_runs_student_id", table_name="diagnostic_runs")
    op.drop_table("diagnostic_runs")
    op.drop_index("ix_topic_mastery_student_id", table_name="topic_mastery")
    op.drop_table("topic_mastery")
    for name in (
        "ix_attempts_created_at",
        "ix_attempts_diagnostic_id",
        "ix_attempts_conversation_id",
        "ix_attempts_question_id",
        "ix_attempts_student_id",
    ):
        op.drop_index(name, table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_question_reports_question_id", table_name="question_reports")
    op.drop_table("question_reports")
    op.drop_index("ix_questions_status", table_name="questions")
    op.drop_index("ix_questions_topic_code", table_name="questions")
    op.drop_index("ix_questions_module_key", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_generation_batches_module_key", table_name="generation_batches")
    op.drop_index("ix_generation_batches_provider_batch_id", table_name="generation_batches")
    op.drop_table("generation_batches")
