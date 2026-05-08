"""merge poster assets and event descriptions branches

Revision ID: 5c187b836b40
Revises: aa12bb34cc56, 9b8c7d6e5f40
Create Date: 2026-05-06 23:19:33.176717

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '5c187b836b40'
down_revision: Union[str, Sequence[str], None] = ('aa12bb34cc56', '9b8c7d6e5f40')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
