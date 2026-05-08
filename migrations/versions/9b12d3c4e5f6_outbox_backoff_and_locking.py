"""outbox backoff and locking

Revision ID: 9b12d3c4e5f6
Revises: 6a6d0ce9a0b0
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b12d3c4e5f6"
down_revision: Union[str, Sequence[str], None] = "6a6d0ce9a0b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("outbox_messages", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_messages", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_messages", sa.Column("locked_by", sa.String(length=128), nullable=True))

    op.create_index("ix_outbox_messages_next_attempt_at", "outbox_messages", ["next_attempt_at"])
    op.create_index("ix_outbox_messages_locked_at", "outbox_messages", ["locked_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_messages_locked_at", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_next_attempt_at", table_name="outbox_messages")
    op.drop_column("outbox_messages", "locked_by")
    op.drop_column("outbox_messages", "locked_at")
    op.drop_column("outbox_messages", "next_attempt_at")

