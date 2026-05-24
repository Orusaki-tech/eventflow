"""Add source_url_raw to shared_link_listings, updated_at to event_sources

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f5
Create Date: 2026-05-25

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shared_link_listings",
        sa.Column("source_url_raw", sa.Text(), nullable=True),
    )
    op.add_column(
        "event_sources",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE event_sources SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("event_sources", "updated_at", nullable=False)


def downgrade() -> None:
    op.drop_column("event_sources", "updated_at")
    op.drop_column("shared_link_listings", "source_url_raw")
