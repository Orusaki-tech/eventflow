"""add apscheduler jobs

Revision ID: 5c4e2a9b9d10
Revises: 1f2d7c8c0c71
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c4e2a9b9d10"
down_revision: Union[str, Sequence[str], None] = "1f2d7c8c0c71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "apscheduler_jobs",
        sa.Column("id", sa.String(length=191), primary_key=True),
        sa.Column("next_run_time", sa.Float(), nullable=True, index=True),
        sa.Column("job_state", sa.LargeBinary(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("apscheduler_jobs")

