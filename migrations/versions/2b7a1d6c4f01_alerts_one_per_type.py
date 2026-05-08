"""alerts one per type

Revision ID: 2b7a1d6c4f01
Revises: 5c4e2a9b9d10
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2b7a1d6c4f01"
down_revision: Union[str, Sequence[str], None] = "5c4e2a9b9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clean up any historical duplicates (keep newest trigger_at, then highest id).
    op.execute(
        """
        DELETE FROM alerts
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY event_id, alert_type
                        ORDER BY trigger_at DESC, id DESC
                    ) AS rn
                FROM alerts
            ) ranked
            WHERE ranked.rn > 1
        )
        """
    )

    op.create_unique_constraint(
        "uq_alerts_event_id_alert_type",
        "alerts",
        ["event_id", "alert_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_alerts_event_id_alert_type", "alerts", type_="unique")

