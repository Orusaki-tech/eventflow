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
    # Create the apscheduler_jobs table if it doesn't already exist (APScheduler might create it automatically)
    op.create_table(
        "apscheduler_jobs",
        sa.Column("id", sa.VARCHAR(length=191), autoincrement=False, nullable=False),
        sa.Column(
            "next_run_time",
            sa.Float(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("job_state", sa.LargeBinary(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id", name="apscheduler_jobs_pkey"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("apscheduler_jobs")

