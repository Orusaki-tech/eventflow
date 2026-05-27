"""Add visibility and sponsored_rank to community_events

Revision ID: 0a1b2c3d4e5f
Revises: b167e599ed0f
Create Date: 2026-05-27 12:45:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "b167e599ed0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "community_events",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
    )
    op.add_column(
        "community_events",
        sa.Column("sponsored_rank", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_community_events_visibility", "community_events", ["visibility"])
    op.create_index("ix_community_events_sponsored_rank", "community_events", ["sponsored_rank"])


def downgrade() -> None:
    op.drop_index("ix_community_events_sponsored_rank", table_name="community_events")
    op.drop_index("ix_community_events_visibility", table_name="community_events")
    op.drop_column("community_events", "sponsored_rank")
    op.drop_column("community_events", "visibility")
