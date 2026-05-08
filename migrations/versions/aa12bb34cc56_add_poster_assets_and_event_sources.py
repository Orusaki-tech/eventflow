"""add poster assets and event sources

Revision ID: aa12bb34cc56
Revises: 4a7b1c2d9f30
Create Date: 2026-05-06 21:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "aa12bb34cc56"
down_revision: Union[str, Sequence[str], None] = "4a7b1c2d9f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "poster_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dhash64", sa.String(length=32), nullable=False),
        sa.Column("poster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_poster_assets_dhash64", "poster_assets", ["dhash64"], unique=True)
    op.create_index("ix_poster_assets_poster_id", "poster_assets", ["poster_id"], unique=True)
    op.create_index("ix_poster_assets_created_at", "poster_assets", ["created_at"])

    op.create_table(
        "poster_asset_parses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("poster_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parsed_json", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["poster_asset_id"],
            ["poster_assets.id"],
            name="fk_poster_asset_parses_poster_asset_id_poster_assets",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_poster_asset_parses_poster_asset_id", "poster_asset_parses", ["poster_asset_id"], unique=True)
    op.create_index("ix_poster_asset_parses_created_at", "poster_asset_parses", ["created_at"])

    op.create_table(
        "event_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_url_raw", sa.Text(), nullable=True),
        sa.Column("source_url_normalized", sa.Text(), nullable=True),
        sa.Column("poster_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["event_drafts.id"],
            name="fk_event_sources_draft_id_event_drafts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["scheduled_events.id"],
            name="fk_event_sources_event_id_scheduled_events",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["poster_asset_id"],
            ["poster_assets.id"],
            name="fk_event_sources_poster_asset_id_poster_assets",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", "draft_id", name="uq_event_sources_user_draft"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_event_sources_user_event"),
    )
    op.create_index("ix_event_sources_user_id", "event_sources", ["user_id"])
    op.create_index("ix_event_sources_draft_id", "event_sources", ["draft_id"])
    op.create_index("ix_event_sources_event_id", "event_sources", ["event_id"])
    op.create_index("ix_event_sources_source_url_normalized", "event_sources", ["source_url_normalized"])
    op.create_index("ix_event_sources_poster_asset_id", "event_sources", ["poster_asset_id"])
    op.create_index("ix_event_sources_created_at", "event_sources", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_event_sources_created_at", table_name="event_sources")
    op.drop_index("ix_event_sources_poster_asset_id", table_name="event_sources")
    op.drop_index("ix_event_sources_source_url_normalized", table_name="event_sources")
    op.drop_index("ix_event_sources_event_id", table_name="event_sources")
    op.drop_index("ix_event_sources_draft_id", table_name="event_sources")
    op.drop_index("ix_event_sources_user_id", table_name="event_sources")
    op.drop_table("event_sources")

    op.drop_index("ix_poster_asset_parses_created_at", table_name="poster_asset_parses")
    op.drop_index("ix_poster_asset_parses_poster_asset_id", table_name="poster_asset_parses")
    op.drop_table("poster_asset_parses")

    op.drop_index("ix_poster_assets_created_at", table_name="poster_assets")
    op.drop_index("ix_poster_assets_poster_id", table_name="poster_assets")
    op.drop_index("ix_poster_assets_dhash64", table_name="poster_assets")
    op.drop_table("poster_assets")

