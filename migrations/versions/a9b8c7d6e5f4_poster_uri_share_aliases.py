"""Poster image URI on community_events + canonical share URL aliases.

Revision ID: a9b8c7d6e5f4
Revises: f1e2d3c4b5a6
Create Date: 2026-05-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("community_events", sa.Column("poster_image_uri", sa.Text(), nullable=True))
    op.create_table(
        "community_event_share_aliases",
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("normalized_url", name="pk_community_event_share_aliases"),
        sa.ForeignKeyConstraint(
            ["community_event_id"],
            ["community_events.id"],
            name="fk_ce_share_alias_event",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_community_event_share_aliases_event_id",
        "community_event_share_aliases",
        ["community_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_community_event_share_aliases_event_id", table_name="community_event_share_aliases")
    op.drop_table("community_event_share_aliases")
    op.drop_column("community_events", "poster_image_uri")
