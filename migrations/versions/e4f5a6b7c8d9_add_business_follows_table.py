"""Add business_follows table so users can follow businesses.

Revision ID: e4f5a6b7c8d9
Revises: c3d5e7f9a1b2
Create Date: 2026-05-24

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "c3d5e7f9a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_follows",
        sa.Column("follower_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("follower_user_id", "business_id", name="pk_business_follows"),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_business_follows_business", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_business_follows_follower", "business_follows", ["follower_user_id"])
    op.create_index("ix_business_follows_business", "business_follows", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_business_follows_business", table_name="business_follows")
    op.drop_index("ix_business_follows_follower", table_name="business_follows")
    op.drop_table("business_follows")
