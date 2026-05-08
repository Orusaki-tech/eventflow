"""event_drafts.start_time nullable for unknown AI-parse times

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-05-07 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "event_drafts",
        "start_time",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE event_drafts SET start_time = NOW() AT TIME ZONE 'UTC' WHERE start_time IS NULL"
    )
    op.alter_column(
        "event_drafts",
        "start_time",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
