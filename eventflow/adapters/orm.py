from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    Boolean,
    LargeBinary,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Float as SA_Float
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import UserDefinedType
from sqlalchemy.orm import registry, relationship

from eventflow.adapters.repository import OutboxMessage
from eventflow.domain.model import Alert, AlertType, EventDraft, ScheduledEvent, UserLocation
from eventflow.adapters.repository import DevicePushToken
from eventflow.adapters.repository import CommunityEvent, CommunityEventEmbedding
from eventflow.adapters.repository import EventShare, Group, GroupMembership, Venue


mapper_registry = registry()
metadata_obj: MetaData = mapper_registry.metadata


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"


event_drafts = Table(
    "event_drafts",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("title", String(512), nullable=False),
    Column("start_time", DateTime(timezone=True), nullable=True, index=True),
    Column("venue", String(512), nullable=False),
    Column("confidence_score", Float, nullable=False),
    Column("price", String(256), nullable=True),
    Column("confirmed_at", DateTime(timezone=True), nullable=True),
)


scheduled_events = Table(
    "scheduled_events",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("title", String(512), nullable=False),
    Column("start_time", DateTime(timezone=True), nullable=False, index=True),
    Column("venue", String(512), nullable=False),
    Column("venue_id", PG_UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True, index=True),
    Column("raw_venue_text", Text, nullable=True),
    Column("visibility", String(16), nullable=False, default="private", index=True),
    Column("description_public", Text, nullable=True),
    Column("description_close_friends", Text, nullable=True),
    Column("price", String(256), nullable=True),
    Column("cancelled_at", DateTime(timezone=True), nullable=True),
    Column("calendar_external_id", String(256), nullable=True),
)


venues = Table(
    "venues",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("name", String(512), nullable=False, index=True),
    Column("address", String(1024), nullable=True),
    Column("lat", SA_Float, nullable=False),
    Column("lng", SA_Float, nullable=False),
    Column("place_id", String(256), nullable=True, unique=True),
    Column("created_by_user_id", PG_UUID(as_uuid=True), nullable=True, index=True),
    Column("updated_by_user_id", PG_UUID(as_uuid=True), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False, index=True),
)


alerts = Table(
    "alerts",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("event_id", PG_UUID(as_uuid=True), ForeignKey("scheduled_events.id"), nullable=False, index=True),
    Column("alert_type", String(32), nullable=False, index=True),
    Column("trigger_at", DateTime(timezone=True), nullable=False, index=True),
    Column("message", Text, nullable=False),
    UniqueConstraint("event_id", "alert_type", name="uq_alerts_event_id_alert_type"),
)


user_locations = Table(
    "user_locations",
    metadata_obj,
    Column("user_id", PG_UUID(as_uuid=True), nullable=False),
    Column("label", String(32), nullable=False),
    Column("address", String(1024), nullable=False),
    Column("lat", SA_Float, nullable=True),
    Column("lng", SA_Float, nullable=True),
    PrimaryKeyConstraint("user_id", "label", name="pk_user_locations"),
)

user_calendar_tokens = Table(
    "user_calendar_tokens",
    metadata_obj,
    Column("user_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("access_token", LargeBinary, nullable=False),
    Column("refresh_token", LargeBinary, nullable=True),
    Column("token_uri", Text, nullable=False),
    Column("scopes", Text, nullable=False),
    Column("expiry", DateTime(timezone=True), nullable=True),
)

oauth_states = Table(
    "oauth_states",
    metadata_obj,
    Column("user_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("state", String(256), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

outbox_messages = Table(
    "outbox_messages",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("topic", String(128), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False, index=True),
    Column("published_at", DateTime(timezone=True), nullable=True, index=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error", Text, nullable=True),
    Column("next_attempt_at", DateTime(timezone=True), nullable=True, index=True),
    Column("locked_at", DateTime(timezone=True), nullable=True, index=True),
    Column("locked_by", String(128), nullable=True),
)

device_push_tokens = Table(
    "device_push_tokens",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("expo_push_token", Text, nullable=False),
    Column("platform", String(32), nullable=True),
    Column("device_id", String(128), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("disabled_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("user_id", "expo_push_token", name="uq_device_push_tokens_user_token"),
)

community_events = Table(
    "community_events",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("source", String(64), nullable=False),
    Column("title", String(512), nullable=False),
    Column("start_time", DateTime(timezone=True), nullable=False, index=True),
    Column("venue", String(512), nullable=False),
    Column("description", Text, nullable=True),
    Column("poster_image_uri", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sponsored_rank", Integer, nullable=False, default=0),
    Column("verified_badge", Boolean, nullable=False, default=False),
)

community_event_embeddings = Table(
    "community_event_embeddings",
    metadata_obj,
    Column(
        "community_event_id",
        PG_UUID(as_uuid=True),
        ForeignKey("community_events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("embedding", Vector(64), nullable=False),
    Column("embedding_model", String(64), nullable=False),
    Column("embedded_at", DateTime(timezone=True), nullable=False),
)

groups = Table(
    "groups",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("name", String(256), nullable=False),
    Column("owner_user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("group_type", String(32), nullable=False, default="friend"),
    Column("invite_token", String(64), nullable=True),
    Column("pinned_event_id", PG_UUID(as_uuid=True), nullable=True),
)

group_memberships = Table(
    "group_memberships",
    metadata_obj,
    Column("group_id", PG_UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False),
    Column("role", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    PrimaryKeyConstraint("group_id", "user_id", name="pk_group_memberships"),
)
Index("ix_group_memberships_user_id", group_memberships.c.user_id)

event_shares = Table(
    "event_shares",
    metadata_obj,
    Column("event_id", PG_UUID(as_uuid=True), ForeignKey("scheduled_events.id", ondelete="CASCADE"), nullable=False),
    Column("group_id", PG_UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
    Column("shared_by_user_id", PG_UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    PrimaryKeyConstraint("event_id", "group_id", name="pk_event_shares"),
)
Index("ix_event_shares_group_id", event_shares.c.group_id)


poster_assets = Table(
    "poster_assets",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    # Visual fingerprint for diagnostics only; not used for parse reuse (too coarse).
    Column("dhash64", String(32), nullable=False, index=True),
    # Exact-byte identity for Parse reuse + avoiding mistaken merges across visually similar posters.
    Column("content_sha256", String(64), nullable=True, unique=True, index=True),
    # Pointer to durable storage (PosterStore UUID)
    Column("poster_id", PG_UUID(as_uuid=True), nullable=False, unique=True, index=True),
    Column("content_type", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)


poster_asset_parses = Table(
    "poster_asset_parses",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column(
        "poster_asset_id",
        PG_UUID(as_uuid=True),
        ForeignKey("poster_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    Column("parsed_json", JSON, nullable=False),
    Column("model_version", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
)


business_follows = Table(
    "business_follows",
    metadata_obj,
    Column("follower_user_id", PG_UUID(as_uuid=True), nullable=False),
    Column("business_id", PG_UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("follower_user_id", "business_id", name="pk_business_follows"),
    ForeignKeyConstraint(["follower_user_id"], ["auth_users.id"], name="fk_business_follows_follower", ondelete="CASCADE"),
    ForeignKeyConstraint(["business_id"], ["businesses.id"], name="fk_business_follows_business", ondelete="CASCADE"),
)
Index("ix_business_follows_follower", business_follows.c.follower_user_id)
Index("ix_business_follows_business", business_follows.c.business_id)


event_sources = Table(
    "event_sources",
    metadata_obj,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("draft_id", PG_UUID(as_uuid=True), ForeignKey("event_drafts.id", ondelete="CASCADE"), nullable=True, index=True),
    Column("event_id", PG_UUID(as_uuid=True), ForeignKey("scheduled_events.id", ondelete="CASCADE"), nullable=True, index=True),
    Column("source_url_raw", Text, nullable=True),
    Column("source_url_normalized", Text, nullable=True, index=True),
    Column("poster_asset_id", PG_UUID(as_uuid=True), ForeignKey("poster_assets.id", ondelete="SET NULL"), nullable=True, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    UniqueConstraint("user_id", "draft_id", name="uq_event_sources_user_draft"),
    UniqueConstraint("user_id", "event_id", name="uq_event_sources_user_event"),
)


def start_mappers() -> None:
    # Idempotent: FastAPI dependencies can call this multiple times.
    # SQLAlchemy will raise if a class is mapped twice.
    if mapper_registry.mappers:
        return
    # Domain model stays persistence-ignorant: mapping is defined here.
    mapper_registry.map_imperatively(EventDraft, event_drafts)

    mapper_registry.map_imperatively(
        ScheduledEvent,
        scheduled_events,
        properties={
            "alerts": relationship(
                Alert,
                backref="event",
                collection_class=list,
                cascade="all, delete-orphan",
                lazy="selectin",
            )
        },
    )

    mapper_registry.map_imperatively(Alert, alerts)
    mapper_registry.map_imperatively(UserLocation, user_locations)
    mapper_registry.map_imperatively(OutboxMessage, outbox_messages)
    mapper_registry.map_imperatively(DevicePushToken, device_push_tokens)
    mapper_registry.map_imperatively(CommunityEvent, community_events)
    mapper_registry.map_imperatively(CommunityEventEmbedding, community_event_embeddings)
    mapper_registry.map_imperatively(Group, groups)
    mapper_registry.map_imperatively(GroupMembership, group_memberships)
    mapper_registry.map_imperatively(EventShare, event_shares)
    mapper_registry.map_imperatively(Venue, venues)

