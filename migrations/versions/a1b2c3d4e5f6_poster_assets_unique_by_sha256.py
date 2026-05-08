"""poster dedupe by exact image bytes (sha256), not dhash

Revision ID: a1b2c3d4e5f6
Revises: 5c187b836b40
Create Date: 2026-05-06

Poster parse cache reused rows keyed only by dhash64, which is perceptual and can
treat different screenshots (e.g. same layout but different printed date/time) as one
asset. Reuse parses only when the uploaded bytes match exactly (SHA-256).

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5c187b836b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_poster_assets_dhash64", table_name="poster_assets")
    op.create_index("ix_poster_assets_dhash64", "poster_assets", ["dhash64"], unique=False)
    op.add_column("poster_assets", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_poster_assets_content_sha256",
        "poster_assets",
        ["content_sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_poster_assets_content_sha256", table_name="poster_assets")
    op.drop_column("poster_assets", "content_sha256")
    op.drop_index("ix_poster_assets_dhash64", table_name="poster_assets")
    op.create_index("ix_poster_assets_dhash64", "poster_assets", ["dhash64"], unique=True)
