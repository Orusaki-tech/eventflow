"""add venues and event visibility

Revision ID: 3f4c2a1b9d20
Revises: 1c9b7d0e4a21
Create Date: 2026-05-06 20:34:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3f4c2a1b9d20"
down_revision: Union[str, Sequence[str], None] = "1c9b7d0e4a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("address", sa.String(length=1024), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("place_id", sa.String(length=256), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("place_id", name="uq_venues_place_id"),
    )
    op.create_index("ix_venues_name", "venues", ["name"])
    op.create_index("ix_venues_created_by_user_id", "venues", ["created_by_user_id"])
    op.create_index("ix_venues_updated_by_user_id", "venues", ["updated_by_user_id"])
    op.create_index("ix_venues_created_at", "venues", ["created_at"])
    op.create_index("ix_venues_updated_at", "venues", ["updated_at"])

    op.add_column("scheduled_events", sa.Column("venue_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("scheduled_events", sa.Column("raw_venue_text", sa.Text(), nullable=True))
    op.add_column(
        "scheduled_events",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="private"),
    )
    op.create_index("ix_scheduled_events_venue_id", "scheduled_events", ["venue_id"])
    op.create_index("ix_scheduled_events_visibility", "scheduled_events", ["visibility"])
    op.create_foreign_key(
        "fk_scheduled_events_venue_id_venues",
        "scheduled_events",
        "venues",
        ["venue_id"],
        ["id"],
    )

    # Backfill raw_venue_text for existing rows to preserve original input.
    op.execute("UPDATE scheduled_events SET raw_venue_text = venue WHERE raw_venue_text IS NULL")
    # Drop server default; application controls defaults going forward.
    op.alter_column("scheduled_events", "visibility", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_scheduled_events_venue_id_venues", "scheduled_events", type_="foreignkey")
    op.drop_index("ix_scheduled_events_visibility", table_name="scheduled_events")
    op.drop_index("ix_scheduled_events_venue_id", table_name="scheduled_events")
    op.drop_column("scheduled_events", "visibility")
    op.drop_column("scheduled_events", "raw_venue_text")
    op.drop_column("scheduled_events", "venue_id")

    op.drop_index("ix_venues_updated_at", table_name="venues")
    op.drop_index("ix_venues_created_at", table_name="venues")
    op.drop_index("ix_venues_updated_by_user_id", table_name="venues")
    op.drop_index("ix_venues_created_by_user_id", table_name="venues")
    op.drop_index("ix_venues_name", table_name="venues")
    op.drop_table("venues")

