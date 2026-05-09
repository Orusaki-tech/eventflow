#!/usr/bin/env python3
"""Populate Postgres with rich dummy data across mobile, web-business, and web-admin.

Creates:

- **Mobile / core:** venues, scheduled events (today + upcoming, visibility mix), calendar_external_id sample,
  ``device_calendar_links``, ``user_locations`` (home/work), dummy Expo push token, alerts, groups (invite token +
  pinned event), shares, RSVPs
- **Drafts:** pending + confirmed rows with ``poster_assets``, ``poster_asset_parses``, and ``event_sources`` links
  (surfaces thumbnail/share plumbing + admin Posters directory)
- **Business portal:** two businesses (one **verified**), listings with posters, WhatsApp fields, share aliases,
  ``listing_analytics_events``, approved promo videos plus one **pending** video row for moderation workflows
- **Discovery / feed:** community listings (HTTPS posters), embeddings when pgvector table exists, synthetic second
  organizer + ``follows`` for ``GET /api/v1/feed/home``
- **Link moderation samples:** ``shared_link_listings`` rows (approved + rejected URLs)

Requires ``DB_URL`` (or ``DB_*`` in ``.env``) and Alembic migrations applied.

Usage::

    cd /path/to/eventflow
    export DB_URL=postgresql+psycopg://...
    python3 scripts/seed_dummy_full.py --user-id YOUR-SUPABASE-AUTH-UUID

Replace a previous run for the same ``--user-id`` (same deterministic UUIDs)::

    python3 scripts/seed_dummy_full.py --user-id YOUR-UUID --replace

Exit codes: 0 success, 1 configuration / missing tables / errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from eventflow.adapters.embeddings_client import DeterministicEmbeddingsClient
from eventflow.adapters.share_parse_cache import normalize_shared_url
from eventflow.config import get_settings

SEED_NS = UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")
SOURCE_TAG = "dummy_seed_full"

# Stable HTTPS demo assets (small / CDN-friendly)
POSTER = lambda seed: f"https://picsum.photos/seed/{seed}/800/450"
VIDEO_SHORT = "https://download.samplelib.com/mp4/sample-5s.mp4"
VIDEO_CLIP = "https://download.samplelib.com/mp4/sample-10s.mp4"

DUMMY_SHARE_APPROVED = "https://example.com/eventflow/dummy-share-approved"
DUMMY_SHARE_REJECTED = "https://example.com/eventflow/dummy-share-rejected"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _uuid_in_sql(ids: list[UUID]) -> str:
    return ", ".join(f"'{u}'::uuid" for u in ids)


def _did(primary: UUID, key: str) -> UUID:
    return uuid5(SEED_NS, f"{primary}:{key}")


def _table_exists(conn: Connection, name: str) -> bool:
    return (
        conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :name LIMIT 1
                """
            ),
            {"name": name},
        ).scalar()
        is not None
    )


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _sqlalchemy_db_url(url: str) -> str:
    """Use psycopg v3: bare ``postgresql://`` defaults to psycopg2 in SQLAlchemy, which may not be installed."""
    if "+psycopg" in url or "+asyncpg" in url or "+pg8000" in url:
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def _clear_seed(conn: Connection, primary: UUID, secondary: UUID) -> None:
    sched_ids = [
        _did(primary, "sched-today-a"),
        _did(primary, "sched-today-b"),
        _did(primary, "sched-up-1"),
        _did(primary, "sched-up-2"),
        _did(primary, "sched-up-3"),
        _did(primary, "sched-shared"),
    ]
    gid = _did(primary, "group-demo")
    draft_ids = [_did(primary, "draft-pending-a"), _did(primary, "draft-pending-b"), _did(primary, "draft-confirmed")]
    biz_ids = [_did(primary, "biz-luna"), _did(primary, "biz-east")]
    venue_ids = [_did(primary, "venue-hall"), _did(primary, "venue-roof")]
    ce_ids = [
        _did(primary, "ce-own-1"),
        _did(primary, "ce-own-2"),
        _did(primary, "ce-own-3"),
        _did(primary, "ce-org-a"),
        _did(primary, "ce-org-b"),
        _did(primary, "ce-org-c"),
    ]
    poster_ids = [_did(primary, "poster-asset-a"), _did(primary, "poster-asset-b"), _did(primary, "poster-asset-c")]
    poster_sql = _uuid_in_sql(poster_ids)
    push_id = _did(primary, "push-token-1")

    sid_sql = _uuid_in_sql(sched_ids)
    conn.execute(
        text(f"DELETE FROM device_calendar_links WHERE user_id = :u AND event_id IN ({sid_sql})"),
        {"u": str(primary)},
    )
    conn.execute(text(f"DELETE FROM listing_analytics_events WHERE community_event_id IN ({_uuid_in_sql(ce_ids)})"))
    conn.execute(
        text(
            "DELETE FROM shared_link_listings WHERE normalized_url LIKE 'https://example.com/eventflow/dummy-%'"
        )
    )
    conn.execute(
        text("DELETE FROM user_locations WHERE user_id = :u AND label IN ('home', 'work')"),
        {"u": str(primary)},
    )
    conn.execute(text("DELETE FROM device_push_tokens WHERE id = :id"), {"id": str(push_id)})

    conn.execute(text(f"DELETE FROM alerts WHERE event_id IN ({sid_sql})"))
    conn.execute(text(f"DELETE FROM event_shares WHERE event_id IN ({sid_sql})"))
    conn.execute(text(f"DELETE FROM group_rsvps WHERE event_id IN ({sid_sql})"))
    conn.execute(text(f"DELETE FROM scheduled_events WHERE id IN ({sid_sql})"))

    conn.execute(text("DELETE FROM group_memberships WHERE group_id = :gid"), {"gid": str(gid)})
    conn.execute(text("DELETE FROM groups WHERE id = :gid"), {"gid": str(gid)})

    conn.execute(text(f"DELETE FROM event_drafts WHERE id IN ({_uuid_in_sql(draft_ids)})"))

    conn.execute(text(f"DELETE FROM poster_assets WHERE id IN ({poster_sql})"))

    ce_sql = _uuid_in_sql(ce_ids)
    biz_sql = _uuid_in_sql(biz_ids)
    conn.execute(
        text(
            f"""
            DELETE FROM business_listing_attachments
            WHERE community_event_id IN ({ce_sql}) OR business_id IN ({biz_sql})
            """
        )
    )
    conn.execute(text(f"DELETE FROM community_event_share_aliases WHERE community_event_id IN ({ce_sql})"))
    conn.execute(text(f"DELETE FROM event_videos WHERE community_event_id IN ({ce_sql})"))
    conn.execute(text(f"DELETE FROM community_events WHERE id IN ({ce_sql})"))
    conn.execute(text("DELETE FROM follows WHERE follower_user_id = :a AND following_user_id = :b"), {"a": primary, "b": secondary})
    conn.execute(text(f"DELETE FROM businesses WHERE id IN ({biz_sql})"))
    conn.execute(text(f"DELETE FROM venues WHERE id IN ({_uuid_in_sql(venue_ids)})"))
    conn.execute(text("DELETE FROM user_preferences WHERE user_id = :u"), {"u": str(primary)})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="Supabase auth user UUID (owns dashboard businesses/listings and personal calendar rows).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove rows previously inserted for this user-id (deterministic IDs + listing source tag overlap).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate DB connectivity and tables only.")
    args = parser.parse_args()

    try:
        primary = UUID(args.user_id)
    except ValueError:
        print("ERROR: --user-id must be a valid UUID.", file=sys.stderr)
        return 1

    secondary = _did(primary, "secondary-organizer")

    settings = get_settings()
    db_url = settings.effective_db_url
    if not db_url:
        print("ERROR: DB_URL (or DB_HOST/DB_NAME/...) must be set.", file=sys.stderr)
        return 1

    engine = create_engine(_sqlalchemy_db_url(db_url), future=True)
    now_sql = text("SELECT NOW() AT TIME ZONE 'utc' AS ts")

    with engine.connect() as conn:
        if not _table_exists(conn, "scheduled_events"):
            print("ERROR: Core tables missing. Run: alembic upgrade head", file=sys.stderr)
            return 1
        if not _table_exists(conn, "community_events"):
            print(
                "ERROR: community_events missing (pgvector migration skipped?). "
                "Use Postgres with pgvector or Supabase, then alembic upgrade head.",
                file=sys.stderr,
            )
            return 1

    if args.dry_run:
        print(f"primary user: {primary}")
        print(f"synthetic secondary organizer (follow target): {secondary}")
        print("DRY RUN ok — omit --dry-run to insert.")
        return 0

    embedder = DeterministicEmbeddingsClient(dim=64)
    base_now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        if args.replace:
            _clear_seed(conn, primary, secondary)

        ts_row = conn.execute(now_sql).one()[0]
        base_now = ts_row if isinstance(ts_row, datetime) else base_now

        venue_a = _did(primary, "venue-hall")
        venue_b = _did(primary, "venue-roof")
        now_ins = base_now
        conn.execute(
            text(
                """
                INSERT INTO venues (id, name, address, lat, lng, place_id, created_by_user_id, updated_by_user_id, created_at, updated_at)
                VALUES
                  (:va, 'Dummy Concert Hall', '1 Demo Ave', -1.2921, 36.8219, NULL, :u, :u, :now, :now),
                  (:vb, 'Dummy Rooftop', '99 Skyline Rd', -1.2864, 36.8172, NULL, :u, :u, :now, :now)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"va": str(venue_a), "vb": str(venue_b), "u": str(primary), "now": now_ins},
        )

        conn.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, monthly_budget_minor_units, updated_at)
                VALUES (:u, 25000, :now)
                ON CONFLICT (user_id) DO UPDATE SET monthly_budget_minor_units = EXCLUDED.monthly_budget_minor_units, updated_at = EXCLUDED.updated_at
                """
            ),
            {"u": str(primary), "now": now_ins},
        )

        # Scheduled events: two today-ish, shared one, several upcoming
        def ins_sched(
            key: str,
            title: str,
            start: datetime,
            venue: str,
            *,
            visibility: str,
            vid: UUID | None,
            price: str | None,
            desc_pub: str | None,
            desc_cf: str | None,
        ) -> UUID:
            eid = _did(primary, key)
            conn.execute(
                text(
                    """
                    INSERT INTO scheduled_events (
                      id, user_id, title, start_time, venue, venue_id, raw_venue_text,
                      visibility, price, description_public, description_close_friends, cancelled_at
                    )
                    VALUES (
                      :id, :uid, :title, :st, :venue, :vid, :rv,
                      :vis, :price, :dp, :dcf, NULL
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      title = EXCLUDED.title,
                      start_time = EXCLUDED.start_time,
                      venue = EXCLUDED.venue,
                      venue_id = EXCLUDED.venue_id,
                      raw_venue_text = EXCLUDED.raw_venue_text,
                      visibility = EXCLUDED.visibility,
                      price = EXCLUDED.price,
                      description_public = EXCLUDED.description_public,
                      description_close_friends = EXCLUDED.description_close_friends
                    """
                ),
                {
                    "id": str(eid),
                    "uid": str(primary),
                    "title": title,
                    "st": start,
                    "venue": venue,
                    "vid": str(vid) if vid else None,
                    "rv": venue,
                    "vis": visibility,
                    "price": price,
                    "dp": desc_pub,
                    "dcf": desc_cf,
                },
            )
            return eid

        e_today_a = ins_sched(
            "sched-today-a",
            "Dummy — Coffee & jazz (today)",
            base_now + timedelta(hours=3),
            "Dummy Concert Hall — Main Room",
            visibility="private",
            vid=venue_a,
            price="KES 500",
            desc_pub=None,
            desc_cf="Bring friends; dummy seeded event.",
        )
        conn.execute(
            text(
                """
                UPDATE scheduled_events SET calendar_external_id = :ext WHERE id = :id
                """
            ),
            {"ext": "dummy-google-cal-event-001", "id": str(e_today_a)},
        )
        ins_sched(
            "sched-today-b",
            "Dummy — Open mic night (today)",
            base_now + timedelta(hours=9),
            "Dummy Rooftop",
            visibility="public",
            vid=venue_b,
            price="Free",
            desc_pub="Public listing from dummy seed.",
            desc_cf=None,
        )
        ins_sched(
            "sched-up-1",
            "Dummy — Vinyl fair",
            base_now + timedelta(days=4),
            "Dummy Concert Hall",
            visibility="private",
            vid=venue_a,
            price="KES 200",
            desc_pub=None,
            desc_cf=None,
        )
        ins_sched(
            "sched-up-2",
            "Dummy — Sunset DJ set",
            base_now + timedelta(days=11),
            "Dummy Rooftop",
            visibility="public",
            vid=venue_b,
            price="KES 1,500",
            desc_pub="Dummy poster-style description for the open web.",
            desc_cf=None,
        )
        ins_sched(
            "sched-up-3",
            "Dummy — Workshop: lighting design",
            base_now + timedelta(days=22),
            "Dummy Concert Hall — Studio B",
            visibility="private",
            vid=venue_a,
            price=None,
            desc_pub=None,
            desc_cf="Close friends notes from seed.",
        )
        e_shared = ins_sched(
            "sched-shared",
            "Dummy — Group picnic planning",
            base_now + timedelta(days=6),
            "Dummy Rooftop Garden",
            visibility="private",
            vid=venue_b,
            price=None,
            desc_pub=None,
            desc_cf=None,
        )

        gid = _did(primary, "group-demo")
        conn.execute(
            text(
                """
                INSERT INTO groups (id, name, owner_user_id, created_at, group_type, invite_token, pinned_event_id)
                VALUES (:id, 'Dummy Friends Circle', :owner, :now, 'friend', NULL, NULL)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """
            ),
            {"id": str(gid), "owner": str(primary), "now": now_ins},
        )
        conn.execute(
            text(
                """
                INSERT INTO group_memberships (group_id, user_id, role, created_at)
                VALUES (:g, :u, 'owner', :now)
                ON CONFLICT (group_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """
            ),
            {"g": str(gid), "u": str(primary), "now": now_ins},
        )
        conn.execute(
            text(
                """
                INSERT INTO event_shares (event_id, group_id, shared_by_user_id, created_at)
                VALUES (:e, :g, :u, :now)
                ON CONFLICT (event_id, group_id) DO NOTHING
                """
            ),
            {"e": str(e_shared), "g": str(gid), "u": str(primary), "now": now_ins},
        )
        inv_tok = f"dmyinv{primary.hex[:40]}"[:64]
        conn.execute(
            text(
                """
                UPDATE groups SET invite_token = :tok, pinned_event_id = :pe WHERE id = :gid
                """
            ),
            {"tok": inv_tok, "pe": str(e_shared), "gid": str(gid)},
        )
        conn.execute(
            text(
                """
                INSERT INTO group_rsvps (group_id, user_id, event_id, status, updated_at)
                VALUES (:g, :u, :e, 'going', :now)
                ON CONFLICT ON CONSTRAINT pk_group_rsvps DO UPDATE SET
                  status = EXCLUDED.status,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {"g": str(gid), "u": str(primary), "e": str(e_shared), "now": now_ins},
        )

        conn.execute(
            text(
                """
                INSERT INTO alerts (id, event_id, alert_type, trigger_at, message)
                VALUES (:aid, :e, 'TRAFFIC_ALERT', :trig, 'Dummy traffic reminder — leave a bit early.')
                ON CONFLICT (event_id, alert_type) DO UPDATE SET
                  trigger_at = EXCLUDED.trigger_at,
                  message = EXCLUDED.message
                """
            ),
            {"aid": str(_did(primary, "alert-traffic")), "e": str(e_today_a), "trig": base_now + timedelta(hours=2)},
        )

        drafts = [
            ("draft-pending-a", "Dummy draft — awaiting confirm", base_now + timedelta(days=2), "Somewhere TBD", None, 0.72),
            ("draft-pending-b", "Dummy draft — venue TBD", None, "Unknown venue", None, 0.41),
            ("draft-confirmed", "Dummy confirmed draft → event later", base_now + timedelta(days=18), "Dummy Concert Hall", base_now - timedelta(days=1), 0.91),
        ]
        for key, title, st, ven, confirmed, conf in drafts:
            conn.execute(
                text(
                    """
                    INSERT INTO event_drafts (id, user_id, title, start_time, venue, confidence_score, confirmed_at, price)
                    VALUES (:id, :u, :title, :st, :venue, :cs, :cf, :price)
                    ON CONFLICT (id) DO UPDATE SET
                      title = EXCLUDED.title,
                      start_time = EXCLUDED.start_time,
                      venue = EXCLUDED.venue,
                      confidence_score = EXCLUDED.confidence_score,
                      confirmed_at = EXCLUDED.confirmed_at,
                      price = EXCLUDED.price
                    """
                ),
                {
                    "id": str(_did(primary, key)),
                    "u": str(primary),
                    "title": title,
                    "st": st,
                    "venue": ven,
                    "cs": conf,
                    "cf": confirmed,
                    "price": "Early bird" if confirmed else None,
                },
            )

        pa_a = _did(primary, "poster-asset-a")
        pa_b = _did(primary, "poster-asset-b")
        pa_c = _did(primary, "poster-asset-c")
        store_a = _did(primary, "poster-store-a")
        store_b = _did(primary, "poster-store-b")
        store_c = _did(primary, "poster-store-c")

        if _table_exists(conn, "poster_assets"):
            poster_rows = [
                (pa_a, store_a, "seed-a"),
                (pa_b, store_b, "seed-b"),
                (pa_c, store_c, "seed-c"),
            ]
            for pa_id, st_id, tag in poster_rows:
                sha = _sha256_hex(f"{primary}:{tag}")
                dh = sha[:32]
                conn.execute(
                    text(
                        """
                        INSERT INTO poster_assets (id, dhash64, content_sha256, poster_id, content_type, created_at)
                        VALUES (:id, :dh, :sha, :pid, 'image/jpeg', :now)
                        ON CONFLICT (id) DO UPDATE SET
                          dhash64 = EXCLUDED.dhash64,
                          content_sha256 = EXCLUDED.content_sha256,
                          poster_id = EXCLUDED.poster_id,
                          content_type = EXCLUDED.content_type
                        """
                    ),
                    {"id": str(pa_id), "dh": dh, "sha": sha, "pid": str(st_id), "now": now_ins},
                )

            if _table_exists(conn, "poster_asset_parses"):
                conn.execute(
                    text(
                        """
                        INSERT INTO poster_asset_parses (id, poster_asset_id, parsed_json, model_version, created_at)
                        VALUES (:id, :pa, CAST(:pj AS jsonb), :mv, :now)
                        ON CONFLICT (poster_asset_id) DO UPDATE SET
                          parsed_json = EXCLUDED.parsed_json,
                          model_version = EXCLUDED.model_version
                        """
                    ),
                    {
                        "id": str(_did(primary, "poster-parse-a")),
                        "pa": str(pa_a),
                        "pj": json.dumps(
                            {
                                "title": "Dummy parsed poster title",
                                "venue": "Poster venue",
                                "confidence_score": 0.88,
                            }
                        ),
                        "mv": "dummy_seed_v1",
                        "now": now_ins,
                    },
                )

            draft_pa = _did(primary, "draft-pending-a")
            draft_pb = _did(primary, "draft-pending-b")
            ig_a = "https://instagram.com/reel/dummyseed-draft-a"
            ig_b = "https://instagram.com/reel/dummyseed-draft-b"
            ig_ev = "https://instagram.com/reel/dummyseed-sched-today"
            conn.execute(
                text(
                    """
                    INSERT INTO event_sources (
                      id, user_id, draft_id, event_id, source_url_raw, source_url_normalized,
                      poster_asset_id, created_at
                    )
                    VALUES (
                      gen_random_uuid(), :uid, :did, NULL, :raw, :norm, :pa, :now
                    )
                    ON CONFLICT ON CONSTRAINT uq_event_sources_user_draft DO UPDATE SET
                      poster_asset_id = EXCLUDED.poster_asset_id,
                      source_url_raw = EXCLUDED.source_url_raw,
                      source_url_normalized = EXCLUDED.source_url_normalized
                    """
                ),
                {
                    "uid": str(primary),
                    "did": str(draft_pa),
                    "raw": ig_a,
                    "norm": normalize_shared_url(ig_a),
                    "pa": str(pa_a),
                    "now": now_ins,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO event_sources (
                      id, user_id, draft_id, event_id, source_url_raw, source_url_normalized,
                      poster_asset_id, created_at
                    )
                    VALUES (
                      gen_random_uuid(), :uid, :did, NULL, :raw, :norm, :pa, :now
                    )
                    ON CONFLICT ON CONSTRAINT uq_event_sources_user_draft DO UPDATE SET
                      poster_asset_id = EXCLUDED.poster_asset_id,
                      source_url_raw = EXCLUDED.source_url_raw,
                      source_url_normalized = EXCLUDED.source_url_normalized
                    """
                ),
                {
                    "uid": str(primary),
                    "did": str(draft_pb),
                    "raw": ig_b,
                    "norm": normalize_shared_url(ig_b),
                    "pa": str(pa_c),
                    "now": now_ins,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO event_sources (
                      id, user_id, draft_id, event_id, source_url_raw, source_url_normalized,
                      poster_asset_id, created_at
                    )
                    VALUES (
                      gen_random_uuid(), :uid, NULL, :eid, :raw, :norm, :pa, :now
                    )
                    ON CONFLICT ON CONSTRAINT uq_event_sources_user_event DO UPDATE SET
                      poster_asset_id = EXCLUDED.poster_asset_id,
                      source_url_raw = EXCLUDED.source_url_raw,
                      source_url_normalized = EXCLUDED.source_url_normalized
                    """
                ),
                {
                    "uid": str(primary),
                    "eid": str(e_today_a),
                    "raw": ig_ev,
                    "norm": normalize_shared_url(ig_ev),
                    "pa": str(pa_b),
                    "now": now_ins,
                },
            )

        biz_luna = _did(primary, "biz-luna")
        biz_east = _did(primary, "biz-east")
        conn.execute(
            text(
                """
                INSERT INTO businesses (id, name, whatsapp_e164, owner_user_id, verified, created_at)
                VALUES
                  (:b1, 'Dummy Luna Promotions', '+254700000001', :owner, true, :now),
                  (:b2, 'Dummy Eastside Collective', '+254700000002', :owner, false, :now)
                ON CONFLICT (id) DO UPDATE SET
                  name = EXCLUDED.name,
                  whatsapp_e164 = EXCLUDED.whatsapp_e164,
                  verified = EXCLUDED.verified
                """
            ),
            {"b1": str(biz_luna), "b2": str(biz_east), "owner": str(primary), "now": now_ins},
        )

        listing_keys = ["ce-own-1", "ce-own-2", "ce-own-3", "ce-org-a", "ce-org-b", "ce-org-c"]
        pre_ce = [_did(primary, k) for k in listing_keys]
        ce_in = _uuid_in_sql(pre_ce)
        conn.execute(text(f"DELETE FROM event_videos WHERE community_event_id IN ({ce_in})"))
        conn.execute(text(f"DELETE FROM business_listing_attachments WHERE community_event_id IN ({ce_in})"))

        listings = [
            {
                "key": "ce-own-1",
                "owner": primary,
                "title": "Dummy listing — Neon nights (yours)",
                "hours": 96,
                "venue": "Dummy Rooftop",
                "desc": "Your dashboard listing with poster + promo video.",
                "poster": POSTER("efdummy1"),
                "sponsored": 3,
                "biz": biz_luna,
                "video": VIDEO_SHORT,
            },
            {
                "key": "ce-own-2",
                "owner": primary,
                "title": "Dummy listing — Morning market (yours)",
                "hours": 120,
                "venue": "Dummy Concert Hall Plaza",
                "desc": "Poster only; good for carousel poster slide.",
                "poster": POSTER("efdummy2"),
                "sponsored": 1,
                "biz": biz_east,
                "video": None,
            },
            {
                "key": "ce-own-3",
                "owner": primary,
                "title": "Dummy listing — Film shorts night (yours)",
                "hours": 200,
                "venue": "Dummy Studio Annex",
                "desc": "Video-forward listing.",
                "poster": POSTER("efdummy3"),
                "sponsored": 0,
                "biz": None,
                "video": VIDEO_CLIP,
            },
            {
                "key": "ce-org-a",
                "owner": secondary,
                "title": "Dummy — Other organizer · street food crawl",
                "hours": 80,
                "venue": "Dummy Night Market",
                "desc": "Appears in discovery; followed feed when you follow synthetic organizer.",
                "poster": POSTER("efdummy4"),
                "sponsored": 2,
                "biz": None,
                "video": VIDEO_SHORT,
            },
            {
                "key": "ce-org-b",
                "owner": secondary,
                "title": "Dummy — Other organizer · indie makers fair",
                "hours": 140,
                "venue": "Dummy Warehouse District",
                "desc": "Second organizer listing.",
                "poster": POSTER("efdummy5"),
                "sponsored": 0,
                "biz": None,
                "video": None,
            },
            {
                "key": "ce-org-c",
                "owner": secondary,
                "title": "Dummy — Other organizer · rooftop cinema",
                "hours": 180,
                "venue": "Dummy Skyline Terrace",
                "desc": "Third organizer listing with video.",
                "poster": POSTER("efdummy6"),
                "sponsored": 4,
                "biz": None,
                "video": VIDEO_CLIP,
            },
        ]

        ce_uuid_by_key: dict[str, UUID] = {}
        for row in listings:
            cid = _did(primary, row["key"])
            ce_uuid_by_key[row["key"]] = cid
            st = base_now + timedelta(hours=row["hours"])
            conn.execute(
                text(
                    """
                    INSERT INTO community_events (
                      id, user_id, source, title, start_time, venue, description, created_at,
                      sponsored_rank, verified_badge, poster_image_uri
                    )
                    VALUES (
                      :id, :uid, :src, :title, :st, :venue, :desc, :now,
                      :sr, false, :poster
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      title = EXCLUDED.title,
                      start_time = EXCLUDED.start_time,
                      venue = EXCLUDED.venue,
                      description = EXCLUDED.description,
                      sponsored_rank = EXCLUDED.sponsored_rank,
                      poster_image_uri = EXCLUDED.poster_image_uri,
                      user_id = EXCLUDED.user_id,
                      source = EXCLUDED.source
                    """
                ),
                {
                    "id": str(cid),
                    "uid": str(row["owner"]),
                    "src": SOURCE_TAG,
                    "title": row["title"],
                    "st": st,
                    "venue": row["venue"],
                    "desc": row["desc"],
                    "now": now_ins,
                    "sr": row["sponsored"],
                    "poster": row["poster"],
                },
            )
            if row["biz"]:
                conn.execute(
                    text(
                        """
                        INSERT INTO business_listing_attachments (community_event_id, business_id, created_at)
                        VALUES (:ce, :biz, :now)
                        ON CONFLICT (community_event_id) DO UPDATE SET business_id = EXCLUDED.business_id
                        """
                    ),
                    {"ce": str(cid), "biz": str(row["biz"]), "now": now_ins},
                )
            if row["video"]:
                conn.execute(
                    text(
                        """
                        INSERT INTO event_videos (id, community_event_id, storage_uri, moderation_status, created_at)
                        VALUES (gen_random_uuid(), :ce, :uri, 'approved', :now)
                        """
                    ),
                    {"ce": str(cid), "uri": row["video"], "now": now_ins},
                )

        ce_own_2 = ce_uuid_by_key["ce-own-2"]
        conn.execute(
            text(
                """
                INSERT INTO event_videos (id, community_event_id, storage_uri, moderation_status, created_at)
                VALUES (:vid, :ce, :uri, 'pending', :now)
                ON CONFLICT (id) DO UPDATE SET
                  storage_uri = EXCLUDED.storage_uri,
                  moderation_status = EXCLUDED.moderation_status
                """
            ),
            {
                "vid": str(_did(primary, "evt-video-pending")),
                "ce": str(ce_own_2),
                "uri": VIDEO_SHORT,
                "now": now_ins,
            },
        )

        conn.execute(
            text(
                """
                INSERT INTO follows (follower_user_id, following_user_id, created_at)
                VALUES (:a, :b, :now)
                ON CONFLICT (follower_user_id, following_user_id) DO NOTHING
                """
            ),
            {"a": str(primary), "b": str(secondary), "now": now_ins},
        )

        ce_own_1 = ce_uuid_by_key["ce-own-1"]
        alias_norm = normalize_shared_url("https://example.com/eventflow/dummy-listing-share-alias")
        conn.execute(
            text(
                """
                INSERT INTO community_event_share_aliases (normalized_url, community_event_id, created_at, updated_at)
                VALUES (:u, :ce, :now, :now2)
                ON CONFLICT (normalized_url) DO UPDATE SET community_event_id = EXCLUDED.community_event_id, updated_at = EXCLUDED.updated_at
                """
            ),
            {"u": alias_norm, "ce": str(ce_own_1), "now": now_ins, "now2": now_ins},
        )

        conn.execute(
            text(
                """
                INSERT INTO shared_link_listings (normalized_url, status, cached_payload, created_at, updated_at)
                VALUES (:u1, 'approved', CAST(:p1 AS jsonb), :now, :now),
                       (:u2, 'rejected', CAST(:p2 AS jsonb), :now, :now)
                ON CONFLICT (normalized_url) DO UPDATE SET
                  status = EXCLUDED.status,
                  cached_payload = EXCLUDED.cached_payload,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "u1": normalize_shared_url(DUMMY_SHARE_APPROVED),
                "u2": normalize_shared_url(DUMMY_SHARE_REJECTED),
                "p1": json.dumps(
                    {"title": "Approved dummy listing link", "venue": "Cached plaza", "confidence_score": 0.93}
                ),
                "p2": json.dumps(
                    {"title": "Rejected dummy listing link", "venue": "Spam venue", "confidence_score": 0.11}
                ),
                "now": now_ins,
            },
        )

        conn.execute(
            text(
                """
                INSERT INTO user_locations (user_id, label, address, lat, lng)
                VALUES (:u, 'home', 'Dummy Seed Home St, Nairobi', -1.28, 36.82),
                       (:u, 'work', 'Dummy Seed Office Rd, Nairobi', -1.29, 36.81)
                ON CONFLICT (user_id, label) DO UPDATE SET
                  address = EXCLUDED.address,
                  lat = EXCLUDED.lat,
                  lng = EXCLUDED.lng
                """
            ),
            {"u": str(primary)},
        )

        conn.execute(
            text(
                """
                INSERT INTO device_push_tokens (
                  id, user_id, expo_push_token, platform, device_id, created_at, last_seen_at, disabled_at
                )
                VALUES (:id, :u, :tok, 'ios', 'dummy-device-seed', :now, :now, NULL)
                ON CONFLICT ON CONSTRAINT uq_device_push_tokens_user_token DO UPDATE SET
                  platform = EXCLUDED.platform,
                  device_id = EXCLUDED.device_id,
                  last_seen_at = EXCLUDED.last_seen_at,
                  disabled_at = NULL
                """
            ),
            {
                "id": str(_did(primary, "push-token-1")),
                "u": str(primary),
                "tok": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
                "now": now_ins,
            },
        )

        conn.execute(
            text(
                """
                INSERT INTO device_calendar_links (user_id, event_id, external_event_id, calendar_id, updated_at)
                VALUES (:u, :e, 'dummy-ios-cal-ev-001', 'dummy-cal-local', :now)
                ON CONFLICT (user_id, event_id) DO UPDATE SET
                  external_event_id = EXCLUDED.external_event_id,
                  calendar_id = EXCLUDED.calendar_id,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {"u": str(primary), "e": str(e_today_a), "now": now_ins},
        )

        conn.execute(
            text(
                """
                INSERT INTO listing_analytics_events (
                  id, community_event_id, business_id, user_id, metric_type, meta, created_at
                )
                VALUES
                  (:id1, :ce1, :biz1, :u, 'listing_impression', CAST(:m1 AS jsonb), :now),
                  (:id2, :ce2, :biz2, :u, 'whatsapp_tap', CAST(:m2 AS jsonb), :now)
                ON CONFLICT (id) DO UPDATE SET
                  community_event_id = EXCLUDED.community_event_id,
                  business_id = EXCLUDED.business_id,
                  user_id = EXCLUDED.user_id,
                  metric_type = EXCLUDED.metric_type,
                  meta = EXCLUDED.meta,
                  created_at = EXCLUDED.created_at
                """
            ),
            {
                "id1": str(_did(primary, "analytics-impression")),
                "id2": str(_did(primary, "analytics-wa")),
                "ce1": str(ce_own_1),
                "ce2": str(ce_own_1),
                "biz1": str(biz_luna),
                "biz2": str(biz_luna),
                "u": str(primary),
                "m1": json.dumps({"source": "dummy_seed"}),
                "m2": json.dumps({"source": "dummy_seed"}),
                "now": now_ins,
            },
        )

        if _table_exists(conn, "community_event_embeddings"):
            for row in listings:
                cid = ce_uuid_by_key[row["key"]]
                blob = " ".join([row["title"], row["venue"], row["desc"]]).strip()
                vec = embedder.embed_text(text=blob)
                conn.execute(
                    text(
                        """
                        INSERT INTO community_event_embeddings (community_event_id, embedding, embedding_model, embedded_at)
                        VALUES (:id, (:emb)::vector, :model, :now)
                        ON CONFLICT (community_event_id) DO UPDATE SET
                          embedding = (:emb)::vector,
                          embedding_model = EXCLUDED.embedding_model,
                          embedded_at = EXCLUDED.embedded_at
                        """
                    ),
                    {
                        "id": str(cid),
                        "emb": _vector_literal(vec),
                        "model": "deterministic-64",
                        "now": now_ins,
                    },
                )

        print(f"Seeded dummy data for user {primary}")
        print(f"Synthetic organizer UUID (follow target): {secondary}")
        print(
            "Coverage: mobile calendar/share surfaces, business portal listings + analytics, "
            "admin summary/posters/businesses/listings (incl. verified flag + poster_assets)."
        )
        print(
            "Pending promo video row: PATCH /api/v1/admin/event-videos/<video_id>/moderation "
            f"(id={_did(primary, 'evt-video-pending')}) with header X-Admin-Token."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
