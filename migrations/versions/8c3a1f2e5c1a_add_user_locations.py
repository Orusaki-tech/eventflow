"""add user locations

Revision ID: 8c3a1f2e5c1a
Revises: 412ff3b1928f
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8c3a1f2e5c1a"
down_revision: Union[str, Sequence[str], None] = "412ff3b1928f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_locations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=1024), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "label", name="pk_user_locations"),
    )


def downgrade() -> None:
    op.drop_table("user_locations")

