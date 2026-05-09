"""Admin console operator allowlist (Postgres-backed).

Revision ID: c3d5e7f9a1b2
Revises: a9b8c7d6e5f4
Create Date: 2026-05-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d5e7f9a1b2"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_console_allowlist",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_admin_console_allowlist"),
    )


def downgrade() -> None:
    op.drop_table("admin_console_allowlist")
