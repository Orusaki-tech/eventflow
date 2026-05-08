"""add outbox messages

Revision ID: 6a6d0ce9a0b0
Revises: 2b7a1d6c4f01
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6a6d0ce9a0b0"
down_revision: Union[str, Sequence[str], None] = "2b7a1d6c4f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outbox_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_outbox_messages_topic", "outbox_messages", ["topic"])
    op.create_index("ix_outbox_messages_occurred_at", "outbox_messages", ["occurred_at"])
    op.create_index("ix_outbox_messages_published_at", "outbox_messages", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_messages_published_at", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_occurred_at", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_topic", table_name="outbox_messages")
    op.drop_table("outbox_messages")

