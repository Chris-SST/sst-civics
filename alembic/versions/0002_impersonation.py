"""Admin "view as": impersonator on sessions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("impersonator_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_sessions_impersonator_user_id_users",
            "users",
            ["impersonator_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_sessions_impersonator_user_id", ["impersonator_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_impersonator_user_id")
        batch.drop_constraint("fk_sessions_impersonator_user_id_users", type_="foreignkey")
        batch.drop_column("impersonator_user_id")
