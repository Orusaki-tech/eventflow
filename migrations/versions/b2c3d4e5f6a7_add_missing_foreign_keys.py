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

    # Supabase stores users in auth.users; mirror into public.auth_users for FK targets.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'auth' AND table_name = 'users'
            ) THEN
                INSERT INTO auth_users (id)
                SELECT id FROM auth.users
                ON CONFLICT (id) DO NOTHING;
            END IF;
        END $$;
        """
    )

    # Drop rows that still lack a matching auth_users row (stale test data).
    op.execute(
        """
        DELETE FROM follows f
        WHERE NOT EXISTS (
            SELECT 1 FROM auth_users u WHERE u.id = f.follower_user_id
        )
           OR NOT EXISTS (
            SELECT 1 FROM auth_users u WHERE u.id = f.following_user_id
        );
        """
    )
    op.execute(
        """
        DELETE FROM group_rsvps r
        WHERE NOT EXISTS (
            SELECT 1 FROM auth_users u WHERE u.id = r.user_id
        );
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
