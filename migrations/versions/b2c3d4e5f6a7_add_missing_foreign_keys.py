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
    # On standard Postgres environments, auth_users might not exist (managed by Supabase auth in prod)
    # Create a stub auth_users table if it doesn't exist so foreign keys don't break.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM pg_class 
                WHERE relname = 'auth_users' 
                AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            ) THEN
                CREATE TABLE auth_users (
                    id UUID PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            END IF;
        END $$;
        """
    )

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
