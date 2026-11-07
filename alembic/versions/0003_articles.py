"""Article pipeline (D-073): the `articles` table, one row per article or canton guide of
content/articles/plan.yaml, with its English draft, translations, review history, Chris's
suggestions, the sources read, cost and publication state.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("canton", sa.String(2)),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("english", sa.JSON()),
        sa.Column("translations", sa.JSON(), nullable=False),
        sa.Column("reviews", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=False),
        sa.Column("sources_read", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("review_nonce", sa.String(32), nullable=False),
        sa.Column("cost_chf", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("production_started_at", sa.DateTime(timezone=True)),
        sa.Column("proposal_sent_at", sa.DateTime(timezone=True)),
        sa.Column("proposal_revision", sa.Integer()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("build_requested_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_published_at", sa.DateTime(timezone=True)),
        sa.Column("published_revision", sa.Integer()),
        sa.Column("live_urls", sa.JSON(), nullable=False),
        sa.Column("live_files", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_articles_key", "articles", ["key"], unique=True)
    op.create_index("ix_articles_status", "articles", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_articles_status", table_name="articles")
    op.drop_index("ix_articles_key", table_name="articles")
    op.drop_table("articles")
