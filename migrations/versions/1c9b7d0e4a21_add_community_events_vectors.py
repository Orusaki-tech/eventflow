"""add community events vectors

Revision ID: 1c9b7d0e4a21
Revises: 7d1c9b2a3f11
Create Date: 2026-04-27

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1c9b7d0e4a21"
down_revision: Union[str, Sequence[str], None] = "7d1c9b2a3f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector is required for embeddings, but we want local dev to work even when the
    # extension isn't installed (e.g. non-Docker Postgres). In that case, we skip this
    # migration entirely so core app flows can still run.
    conn = op.get_bind()
    available = conn.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
    ).scalar()
    if not available:
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE community_events (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL,
            source VARCHAR(64) NOT NULL,
            title VARCHAR(512) NOT NULL,
            start_time TIMESTAMPTZ NOT NULL,
            venue VARCHAR(512) NOT NULL,
            description TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_community_events_user_id ON community_events (user_id)")
    op.execute("CREATE INDEX ix_community_events_start_time ON community_events (start_time)")

    op.execute(
        """
        CREATE TABLE community_event_embeddings (
            community_event_id UUID PRIMARY KEY REFERENCES community_events(id) ON DELETE CASCADE,
            embedding vector(64) NOT NULL,
            embedding_model VARCHAR(64) NOT NULL,
            embedded_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_community_event_embeddings_hnsw ON community_event_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_community_event_embeddings_hnsw")
    op.execute("DROP TABLE IF EXISTS community_event_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_community_events_start_time")
    op.execute("DROP INDEX IF EXISTS ix_community_events_user_id")
    op.execute("DROP TABLE IF EXISTS community_events")

