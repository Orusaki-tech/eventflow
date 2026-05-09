#!/usr/bin/env python3
"""Insert demo rows into ``community_events`` for Discover / listing carousel smoke tests.

Requires:

- ``DB_URL`` (or ``DB_*`` parts) pointing at Postgres where migrations have been applied.
- Table ``community_events`` must exist (see Alembic; early migrations skip creating this table if the ``vector`` extension is unavailable).

Usage::

    cd /path/to/eventflow
    export DB_URL=postgresql+psycopg://...
    python3 scripts/seed_discovery_demo.py

Use a real Supabase auth user id as organizer so “Follow organizer” matches an account::

    python3 scripts/seed_discovery_demo.py --organizer-user-id \"YOUR-SUPABASE-USER-UUID\"

Options::

    --dry-run   Print planned inserts without writing.

Exit codes: 0 on success, 1 on configuration / DB errors.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from eventflow.config import get_settings


def _table_exists(conn: Connection, name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :name
            LIMIT 1
            """
        ),
        {"name": name},
    ).scalar()
    return row is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--organizer-user-id",
        type=str,
        default=None,
        help="UUID of an existing user (e.g. Supabase auth user id). "
        "If omitted, a random UUID is used — Discover works but follow tests won't match a login.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not commit inserts.")
    args = parser.parse_args()

    settings = get_settings()
    db_url = settings.effective_db_url
    if not db_url:
        print("ERROR: DB_URL (or DB_HOST/DB_NAME/...) must be set.", file=sys.stderr)
        return 1

    try:
        organizer = UUID(args.organizer_user_id) if args.organizer_user_id else uuid4()
    except ValueError:
        print("ERROR: --organizer-user-id must be a valid UUID.", file=sys.stderr)
        return 1

    engine = create_engine(db_url, future=True)
    now_sql = text("SELECT NOW() AT TIME ZONE 'utc' AS ts")

    if args.dry_run:
        with engine.connect() as conn:
            if not _table_exists(conn, "community_events"):
                print(
                    "ERROR: Table community_events does not exist. "
                    "Apply migrations (alembic upgrade head). "
                    "If you use Postgres without pgvector, the migration that creates "
                    "community_events may have been skipped — install pgvector or use Supabase.",
                    file=sys.stderr,
                )
                return 1
            base_ts = conn.execute(now_sql).one()[0]
        print(f"Organizer user_id: {organizer}")
        if not args.organizer_user_id:
            print("(Random organizer UUID — pass --organizer-user-id for realistic follow tests.)")
        rows_desc = [
            ("Demo listing — rooftop sunset", 72),
            ("Demo listing — acoustic night", 168),
        ]
        for title, dh in rows_desc:
            print(f"DRY RUN would insert: title={title!r}, start≈{base_ts + timedelta(hours=dh)}")
        return 0

    with engine.begin() as conn:
        if not _table_exists(conn, "community_events"):
            print(
                "ERROR: Table community_events does not exist. "
                "Apply migrations (alembic upgrade head). "
                "If you use Postgres without pgvector, the migration that creates "
                "community_events may have been skipped — install pgvector or use Supabase.",
                file=sys.stderr,
            )
            return 1

        base_ts = conn.execute(now_sql).one()[0]

        rows = [
            {
                "title": "Demo listing — rooftop sunset",
                "venue": "100 Demo Street, Example City",
                "delta_hours": 72,
                "sponsored_rank": 2,
                "description": "Seeded by scripts/seed_discovery_demo.py",
            },
            {
                "title": "Demo listing — acoustic night",
                "venue": "2 Venue Rd, Example City",
                "delta_hours": 168,
                "sponsored_rank": 1,
                "description": "Second demo row for merge/dedupe tests.",
            },
        ]

        insert_sql = text(
            """
            INSERT INTO community_events (
                id, user_id, source, title, start_time, venue, description,
                created_at, sponsored_rank, verified_badge
            )
            VALUES (
                gen_random_uuid(), :user_id, 'demo_seed', :title,
                :start_time, :venue, :description,
                NOW() AT TIME ZONE 'utc', :sponsored_rank, false
            )
            """
        )

        print(f"Organizer user_id: {organizer}")
        if not args.organizer_user_id:
            print("(Random organizer UUID — pass --organizer-user-id for realistic follow tests.)")

        for r in rows:
            start_time = base_ts + timedelta(hours=r["delta_hours"])
            params = {
                "user_id": str(organizer),
                "title": r["title"],
                "start_time": start_time,
                "venue": r["venue"],
                "description": r["description"],
                "sponsored_rank": r["sponsored_rank"],
            }
            conn.execute(insert_sql, params)

        print(f"Inserted {len(rows)} community_events row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
