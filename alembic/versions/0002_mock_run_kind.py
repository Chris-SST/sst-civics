"""Readiness check: mock_runs gets a `kind` column (`mock` for the mock test, `readiness` for
the untimed 20-question readiness check). Existing rows are mock tests.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mock_runs") as batch:
        batch.add_column(
            sa.Column("kind", sa.String(12), nullable=False, server_default="mock"),
        )


def downgrade() -> None:
    with op.batch_alter_table("mock_runs") as batch:
        batch.drop_column("kind")
