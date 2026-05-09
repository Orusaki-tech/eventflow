"""v2 product gaps: device calendar, link moderation, business, social, videos

Revision ID: f1e2d3c4b5a6
Revises: d4e5f6a7b8c9
Create Date: 2026-05-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_calendar_links",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_event_id", sa.String(length=512), nullable=False),
        sa.Column("calendar_id", sa.String(length=512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "event_id", name="pk_device_calendar_links"),
        sa.ForeignKeyConstraint(
            ["event_id"], ["scheduled_events.id"], name="fk_device_calendar_links_event", ondelete="CASCADE"
        ),
    )

    op.create_table(
        "shared_link_listings",
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="approved"),
        sa.Column("cached_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("normalized_url", name="pk_shared_link_listings"),
    )

    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("whatsapp_e164", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_businesses"),
    )

    op.create_table(
        "business_listing_attachments",
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("community_event_id", name="pk_business_listing_attachments"),
        sa.ForeignKeyConstraint(
            ["community_event_id"],
            ["community_events.id"],
            name="fk_bl_attach_community_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_bl_attach_business", ondelete="CASCADE"
        ),
    )

    op.create_table(
        "listing_analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("metric_type", sa.String(length=64), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_listing_analytics_events"),
        sa.ForeignKeyConstraint(
            ["community_event_id"],
            ["community_events.id"],
            name="fk_listing_analytics_community_event",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], name="fk_listing_analytics_business", ondelete="SET NULL"
        ),
    )

    op.create_table(
        "follows",
        sa.Column("follower_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("following_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("follower_user_id", "following_user_id", name="pk_follows"),
        sa.CheckConstraint("follower_user_id <> following_user_id", name="ck_follows_not_self"),
    )
    op.create_index("ix_follows_follower", "follows", ["follower_user_id"])
    op.create_index("ix_follows_following", "follows", ["following_user_id"])

    op.create_table(
        "group_rsvps",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("group_id", "user_id", "event_id", name="pk_group_rsvps"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_rsvps_group", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["scheduled_events.id"], name="fk_group_rsvps_event", ondelete="CASCADE"),
    )

    op.create_table(
        "event_videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("community_event_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("moderation_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_event_videos"),
        sa.ForeignKeyConstraint(
            ["community_event_id"],
            ["community_events.id"],
            name="fk_event_videos_community_event",
            ondelete="CASCADE",
        ),
    )

    op.add_column("groups", sa.Column("group_type", sa.String(length=32), nullable=False, server_default="friend"))
    op.add_column("groups", sa.Column("invite_token", sa.String(length=64), nullable=True))
    op.add_column("groups", sa.Column("pinned_event_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_groups_pinned_event",
        "groups",
        "scheduled_events",
        ["pinned_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_groups_invite_token", "groups", ["invite_token"], unique=True)

    op.add_column("community_events", sa.Column("sponsored_rank", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "community_events",
        sa.Column("verified_badge", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("community_events", "verified_badge")
    op.drop_column("community_events", "sponsored_rank")

    op.drop_index("ix_groups_invite_token", table_name="groups")
    op.drop_constraint("fk_groups_pinned_event", "groups", type_="foreignkey")
    op.drop_column("groups", "pinned_event_id")
    op.drop_column("groups", "invite_token")
    op.drop_column("groups", "group_type")

    op.drop_table("event_videos")
    op.drop_table("group_rsvps")
    op.drop_index("ix_follows_following", table_name="follows")
    op.drop_index("ix_follows_follower", table_name="follows")
    op.drop_table("follows")
    op.drop_table("listing_analytics_events")
    op.drop_table("business_listing_attachments")
    op.drop_table("businesses")
    op.drop_table("shared_link_listings")
    op.drop_table("device_calendar_links")
