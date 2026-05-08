"""initial schema

Revision ID: 412ff3b1928f
Revises: 
Create Date: 2026-04-27 19:10:40.284939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '412ff3b1928f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "event_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("venue", sa.String(length=512), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Indexes are already created via `index=True` on the columns above.

    op.create_table(
        "scheduled_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.String(length=512), nullable=False),
    )
    op.create_index("ix_scheduled_events_user_id", "scheduled_events", ["user_id"])
    op.create_index("ix_scheduled_events_start_time", "scheduled_events", ["start_time"])

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
    )
    op.create_index("ix_alerts_event_id", "alerts", ["event_id"])
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_trigger_at", "alerts", ["trigger_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_alerts_trigger_at", table_name="alerts")
    op.drop_index("ix_alerts_alert_type", table_name="alerts")
    op.drop_index("ix_alerts_event_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_scheduled_events_start_time", table_name="scheduled_events")
    op.drop_index("ix_scheduled_events_user_id", table_name="scheduled_events")
    op.drop_table("scheduled_events")

    op.drop_index("ix_event_drafts_start_time", table_name="event_drafts")
    op.drop_index("ix_event_drafts_user_id", table_name="event_drafts")
    op.drop_table("event_drafts")
