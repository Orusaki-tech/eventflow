"""Add business profile fields (description, logo_url, website, contact_email)

Revision ID: b1c2d3e4f5a6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-25

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("website", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("contact_email", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("businesses", "contact_email")
    op.drop_column("businesses", "website")
    op.drop_column("businesses", "logo_url")
    op.drop_column("businesses", "description")
