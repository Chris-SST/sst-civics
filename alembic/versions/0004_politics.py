"""Politics in your canton (D-074): `politics_items` (what discovery found) and
`current_affairs_questions` (the expiring practice questions made from published round-ups
and vote explainers, kept apart from the question bank). The pages themselves are rows of
`articles`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07
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
        "politics_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("source_id", sa.String(60), nullable=False),
        sa.Column("source_type", sa.String(12), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("url", sa.String(600), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("item_date", sa.Date()),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("canton", "url", name="uq_politics_item_url"),
    )
    op.create_index("ix_politics_items_canton", "politics_items", ["canton"])
    op.create_index("ix_politics_items_item_date", "politics_items", ["item_date"])
    op.create_table(
        "current_affairs_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("set_name", sa.String(30), nullable=False),
        sa.Column("canton", sa.String(2), nullable=False),
        sa.Column("page_key", sa.String(80), nullable=False),
        sa.Column("page_kind", sa.String(10), nullable=False),
        sa.Column("page_revision", sa.Integer(), nullable=False),
        sa.Column("page_paths", sa.JSON(), nullable=False),
        sa.Column("refers_to", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_de", sa.Text(), nullable=False),
        sa.Column("options_de", sa.JSON(), nullable=False),
        sa.Column("correct", sa.String(1), nullable=False),
        sa.Column("explanation_de", sa.Text(), nullable=False),
        sa.Column("translations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("check", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_current_affairs_questions_canton", "current_affairs_questions", ["canton"])
    op.create_index(
        "ix_current_affairs_questions_page_key", "current_affairs_questions", ["page_key"]
    )
    op.create_index(
        "ix_current_affairs_questions_expires_at", "current_affairs_questions", ["expires_at"]
    )
    op.create_index("ix_current_affairs_questions_status", "current_affairs_questions", ["status"])


def downgrade() -> None:
    op.drop_table("current_affairs_questions")
    op.drop_table("politics_items")
