"""add poster_processing_logs for admin notifications

Revision ID: f6e5d4c3b2a1
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-27 13:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6e5d4c3b2a1"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "poster_processing_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("poster_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_title", sa.String(length=512), nullable=True),
        sa.Column("extracted_start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_venue", sa.String(length=512), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("extracted_price", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["poster_asset_id"],
            ["poster_assets.id"],
            name="fk_poster_processing_logs_poster_asset_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_poster_processing_logs_created_at", "poster_processing_logs", ["created_at"])
    op.create_index("ix_poster_processing_logs_status", "poster_processing_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_poster_processing_logs_status", table_name="poster_processing_logs")
    op.drop_index("ix_poster_processing_logs_created_at", table_name="poster_processing_logs")
    op.drop_table("poster_processing_logs")
