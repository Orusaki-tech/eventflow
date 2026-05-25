"""merge business profile and foreign keys heads

Revision ID: b167e599ed0f
Revises: b1c2d3e4f5a6, b2c3d4e5f6a7
Create Date: 2026-05-25 13:15:10.425846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b167e599ed0f'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3e4f5a6', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
