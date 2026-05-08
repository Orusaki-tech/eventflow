"""add event descriptions (public + close friends)

Revision ID: 9b8c7d6e5f40
Revises: 4a7b1c2d9f30
Create Date: 2026-05-06 21:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b8c7d6e5f40"
down_revision: Union[str, Sequence[str], None] = "4a7b1c2d9f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scheduled_events", sa.Column("description_public", sa.Text(), nullable=True))
    op.add_column("scheduled_events", sa.Column("description_close_friends", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scheduled_events", "description_close_friends")
    op.drop_column("scheduled_events", "description_public")

