"""merge venues and outbox heads

Revision ID: 0d8c1a2b3e44
Revises: 3f4c2a1b9d20, 9b12d3c4e5f6
Create Date: 2026-05-06 20:34:30.000000

"""

from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0d8c1a2b3e44"
down_revision: Union[str, Sequence[str], None] = ("3f4c2a1b9d20", "9b12d3c4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision: no-op.
    return


def downgrade() -> None:
    # Merge revision: no-op.
    return

