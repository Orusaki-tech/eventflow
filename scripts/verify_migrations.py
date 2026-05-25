#!/usr/bin/env python3
"""Verify Alembic migrations against the configured Postgres (e.g. Supabase).

Usage:
  python scripts/verify_migrations.py
  ENV_FILE=deploy/gcp/.env.production python scripts/verify_migrations.py
  docker compose exec -T api python scripts/verify_migrations.py

Exits 0 when alembic_version matches repo head and core tables exist.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "b167e599ed0f"
KEY_TABLES = (
    "event_drafts",
    "scheduled_events",
    "alerts",
    "community_events",
    "venues",
    "outbox_messages",
    "device_push_tokens",
    "business_follows",
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key:
            os.environ[key] = val


def _mask_url(url: str) -> str:
    return re.sub(r"//[^@]+@", "//***@", url)


def _direct_url_fallback(url: str) -> str | None:
    """Session pooler URLs often fail for Alembic; try direct db.<ref>.supabase.co."""
    m = re.search(
        r"postgresql\+psycopg://([^:]+):([^@]+)@[^/]+/(\w+)(\?.*)?$",
        url,
    )
    if not m:
        return None
    user, password, dbname, query = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    ref_match = re.match(r"postgres\.([a-z0-9]+)", user)
    if not ref_match:
        ref_match = re.match(r"postgres", user) and re.search(
            r"enlxdeiitvezfrubhhfv", url
        )
        ref = "enlxdeiitvezfrubhhfv" if ref_match else None
    else:
        ref = ref_match.group(1)
    if not ref:
        return None
    q = query if query else "?sslmode=require"
    if "sslmode" not in q:
        q = f"{q}&sslmode=require" if "?" in q else "?sslmode=require"
    direct_user = "postgres" if "." in user else user
    return (
        f"postgresql+psycopg://{direct_user}:{password}"
        f"@db.{ref}.supabase.co:5432/{dbname}{q}"
    )


def _repo_head() -> str:
    try:
        out = subprocess.check_output(
            ["alembic", "heads"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        )
        for line in out.splitlines():
            if "(head)" in line:
                return line.split()[0].strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return EXPECTED_HEAD


def main() -> int:
    env_file = os.environ.get("ENV_FILE")
    if env_file:
        _load_env_file(Path(env_file))
    else:
        _load_env_file(REPO_ROOT / ".env")

    sys.path.insert(0, str(REPO_ROOT))
    from eventflow.config import Settings

    settings = Settings()
    url = settings.effective_db_url
    if not url:
        print("ERROR: No DB_URL / DB_* configured. Set ENV_FILE or .env.", file=sys.stderr)
        return 2

    head = _repo_head()
    print("=== Migration verification ===\n")
    print(f"Connection target: {_mask_url(url)}")
    print(f"Repo alembic head: {head}\n")

    from sqlalchemy import create_engine, text

    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif not url.startswith("postgresql+psycopg"):
        url = url.replace("postgresql+psycopg2", "postgresql+psycopg", 1)

    engines_to_try: list[tuple[str, str]] = [("configured", url)]
    direct = _direct_url_fallback(url)
    if direct and direct != url:
        engines_to_try.append(("direct (db.<ref>.supabase.co)", direct))

    last_err: Exception | None = None
    for label, try_url in engines_to_try:
        print(f"--- Trying {label} ---")
        engine = create_engine(try_url)
        try:
            with engine.connect() as conn:
                _run_checks(conn, head)
            print("\n✓ All checks passed.\n")
            return 0
        except Exception as exc:
            last_err = exc
            print(f"  Connection failed: {exc}\n")
        finally:
            engine.dispose()

    print("ERROR: Could not connect to the database.", file=sys.stderr)
    if last_err:
        print(f"  Last error: {last_err}", file=sys.stderr)
    print(
        "\nNext steps:\n"
        "  1. Supabase Dashboard → SQL Editor → run:\n"
        "       SELECT * FROM alembic_version;\n"
        "  2. On the VM: docker compose exec -T api python scripts/verify_migrations.py\n"
        "  3. Use direct host db.<project-ref>.supabase.co:5432 (not transaction pooler)\n",
        file=sys.stderr,
    )
    return 1


def _run_checks(conn, head: str) -> None:
    from sqlalchemy import text
    print("\n=== alembic_version ===")
    rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    if not rows:
        print("  (empty — no migrations recorded)")
        raise RuntimeError("alembic_version is empty")
    versions = [r[0] for r in rows]
    for v in versions:
        mark = "OK" if v == head else "MISMATCH"
        print(f"  version_num = {v}  [{mark}]")
    if head not in versions:
        print(f"\n  STATUS: BEHIND — run `alembic upgrade head`")
        raise RuntimeError(f"expected head {head}, got {versions}")

    print("\n=== key EventFlow tables ===")
    names = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            )
        ).fetchall()
    }
    missing = []
    for t in KEY_TABLES:
        ok = t in names
        print(f"  {t}: {'YES' if ok else 'MISSING'}")
        if not ok:
            missing.append(t)
    print(f"\n  total public tables: {len(names)}")
    if missing:
        raise RuntimeError(f"missing tables: {', '.join(missing)}")

    print("\n=== pgvector extension ===")
    ext = conn.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    print(f"  vector: {'YES' if ext else 'NO'}")


if __name__ == "__main__":
    raise SystemExit(main())
