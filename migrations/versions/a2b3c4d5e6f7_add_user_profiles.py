"""add user_profiles table for user search and display names

Revision ID: a2b3c4d5e6f7
Revises: f6e5d4c3b2a1
Create Date: 2026-05-27 14:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f6e5d4c3b2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_profiles_display_name", "user_profiles", ["display_name"])
    op.create_index("ix_user_profiles_is_public_display_name", "user_profiles", ["is_public", "display_name"])

def downgrade() -> None:
    op.drop_index("ix_user_profiles_is_public_display_name", table_name="user_profiles")
    op.drop_index("ix_user_profiles_display_name", table_name="user_profiles")
    op.drop_table("user_profiles")
