"""add optional human-readable price on drafts and scheduled events

Revision ID: b7e4f1a2c3d8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 22:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4f1a2c3d8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("event_drafts", sa.Column("price", sa.String(length=256), nullable=True))
    op.add_column("scheduled_events", sa.Column("price", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("scheduled_events", "price")
    op.drop_column("event_drafts", "price")
