"""add business_id to event_videos

Revision ID: a6f8333d54e6
Revises: a2b3c4d5e6f7
Create Date: 2026-05-27 20:49:46.784874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6f8333d54e6'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("event_videos", sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_event_videos_business_id", "event_videos", ["business_id"])
    op.create_foreign_key("fk_event_videos_business", "event_videos", "businesses", ["business_id"], ["id"], ondelete="CASCADE")

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_event_videos_business", "event_videos", type_="foreignkey")
    op.drop_index("ix_event_videos_business_id", table_name="event_videos")
    op.drop_column("event_videos", "business_id")
