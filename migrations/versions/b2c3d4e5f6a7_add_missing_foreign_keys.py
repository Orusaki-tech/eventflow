"""Add missing foreign key constraints to follows and other tables

Revision ID: b2c3d4e5f6a7
Revises: f1e2d3c4b5a6
Create Date: 2026-05-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add foreign key constraints to follows table (both sides)
    op.create_foreign_key(
        "fk_follows_follower",
        "follows",
        "auth_users",
        ["follower_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_follows_following",
        "follows",
        "auth_users",
        ["following_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    
    # Add foreign key to group_rsvps.user_id
    op.create_foreign_key(
        "fk_group_rsvps_user",
        "group_rsvps",
        "auth_users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_group_rsvps_user", "group_rsvps", type_="foreignkey")
    op.drop_constraint("fk_follows_following", "follows", type_="foreignkey")
    op.drop_constraint("fk_follows_follower", "follows", type_="foreignkey")
