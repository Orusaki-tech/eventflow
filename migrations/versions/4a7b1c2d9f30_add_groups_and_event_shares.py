"""add groups and event shares

Revision ID: 4a7b1c2d9f30
Revises: 0d8c1a2b3e44
Create Date: 2026-05-06 20:35:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4a7b1c2d9f30"
down_revision: Union[str, Sequence[str], None] = "0d8c1a2b3e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "group_memberships",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.PrimaryKeyConstraint("group_id", "user_id", name="pk_group_memberships"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_memberships_group_id_groups", ondelete="CASCADE"),
    )
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])

    op.create_table(
        "event_shares",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shared_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.PrimaryKeyConstraint("event_id", "group_id", name="pk_event_shares"),
        sa.ForeignKeyConstraint(["event_id"], ["scheduled_events.id"], name="fk_event_shares_event_id_scheduled_events", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_event_shares_group_id_groups", ondelete="CASCADE"),
    )
    op.create_index("ix_event_shares_group_id", "event_shares", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_event_shares_group_id", table_name="event_shares")
    op.drop_table("event_shares")

    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_table("group_memberships")

    op.drop_table("groups")

