"""Add visibility and sponsored_rank to community_events

Revision ID: 0a1b2c3d4e5f
Revises: b167e599ed0f
Create Date: 2026-05-27 12:45:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "b167e599ed0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if visibility column exists; add only if missing
    has_visibility = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_name='community_events' AND column_name='visibility'")
    ).scalar()
    if not has_visibility:
        op.add_column(
            "community_events",
            sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
        )
        op.create_index("ix_community_events_visibility", "community_events", ["visibility"])

    # Check if sponsored_rank column exists; add only if missing
    has_sponsored = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_name='community_events' AND column_name='sponsored_rank'")
    ).scalar()
    if not has_sponsored:
        op.add_column(
            "community_events",
            sa.Column("sponsored_rank", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_community_events_sponsored_rank", "community_events", ["sponsored_rank"])


def downgrade() -> None:
    conn = op.get_bind()
    has_sponsored = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_name='community_events' AND column_name='sponsored_rank'")
    ).scalar()
    if has_sponsored:
        op.drop_index("ix_community_events_sponsored_rank", table_name="community_events")
        op.drop_column("community_events", "sponsored_rank")
    has_visibility = conn.execute(
        text("SELECT 1 FROM information_schema.columns WHERE table_name='community_events' AND column_name='visibility'")
    ).scalar()
    if has_visibility:
        op.drop_index("ix_community_events_visibility", table_name="community_events")
        op.drop_column("community_events", "visibility")
