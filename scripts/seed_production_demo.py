#!/usr/bin/env python3
"""Seed production-grade demo: 2 businesses, 5 users, full data lifecycle.

Populates every table to make the app look real on the discover feed (mobile)
and the admin console + business portal (web).

Usage::

    cd /path/to/eventflow
    export DB_URL=postgresql+psycopg://...
    python3 scripts/seed_production_demo.py \\
        --users alice-uuid,bob-uuid,charlie-uuid,diana-uuid,eve-uuid

The first user (alice) gets admin-level entities and a premium subscription.

Exit codes: 0 success, 1 error.
"""

from __future__ import annotations

import argparse
import json
import os
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
SOURCE_TAG = "prod_demo_seed"

POSTER = lambda seed: f"https://picsum.photos/seed/{seed}/800/450"
PRODUCT_IMG = lambda seed: f"https://picsum.photos/seed/{seed}/400/400"
VIDEO_5S = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
VIDEO_10S = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"
VIDEO_15S = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
THUMB = "https://picsum.photos/seed/vid-thumb/640/360"

TODAY = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _uuid(primary: UUID, key: str) -> UUID:
    return uuid5(SEED_NS, f"{primary}:{key}")


def _u(prefix: str, key: str) -> str:
    return str(_uuid(uuid5(SEED_NS, prefix), key))


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _table_exists(conn: Connection, name: str) -> bool:
    return conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :name"),
        {"name": name},
    ).scalar() is not None


def _sqlalchemy_db_url(url: str) -> str:
    if "+psycopg" in url or "+asyncpg" in url or "+pg8000" in url:
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=str, required=True, help="Comma-separated list of 5 Supabase auth user UUIDs (alice,bob,charlie,diana,eve)")
    parser.add_argument("--replace", action="store_true", help="Re-seed replacing existing rows")
    parser.add_argument("--dry-run", action="store_true", help="Validate connectivity only")
    args = parser.parse_args()

    user_ids = [UUID(u.strip()) for u in args.users.split(",")]
    if len(user_ids) != 5:
        print("ERROR: Exactly 5 user UUIDs required (alice,bob,charlie,diana,eve).", file=sys.stderr)
        return 1

    alice, bob, charlie, diana, eve = user_ids

    settings = get_settings()
    db_url = settings.effective_db_url
    if not db_url:
        print("ERROR: DB_URL (or DB_HOST/DB_NAME/...) must be set.", file=sys.stderr)
        return 1

    engine = create_engine(_sqlalchemy_db_url(db_url), future=True)

    with engine.connect() as conn:
        if not _table_exists(conn, "community_events"):
            print("ERROR: Core tables missing. Run: alembic upgrade head", file=sys.stderr)
            return 1

    if args.dry_run:
        print(f"Users: alice={alice}, bob={bob}, charlie={charlie}, diana={diana}, eve={eve}")
        print("DRY RUN ok")
        return 0

    embedder = DeterministicEmbeddingsClient(dim=64)
    now = TODAY

    with engine.begin() as conn:
        # 1) VENUES — 3 venues
        venues = {
            "venue-nexus": ("Nexus Arts Centre", "Moi Ave, Nairobi", -1.2833, 36.8167),
            "venue-roof": ("Skydeck Rooftop", "10th Fl, Westlands", -1.2680, 36.8130),
            "venue-basement": ("The Basement Lounge", "River Rd, Nairobi", -1.2870, 36.8210),
        }
        for vkey, (vname, vaddr, vlat, vlng) in venues.items():
            conn.execute(
                text("""
                    INSERT INTO venues (id, name, address, lat, lng, place_id, created_by_user_id, updated_by_user_id, created_at, updated_at)
                    VALUES (:id, :name, :addr, :lat, :lng, NULL, :alice, :alice, :now, :now)
                    ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, address=EXCLUDED.address
                """),
                {"id": _u("alice", vkey), "name": vname, "addr": vaddr, "lat": vlat, "lng": vlng, "alice": str(alice), "now": now},
            )

        # 2) BUSINESS PROFILES — 2 businesses (verified Luna, unverified Eastside)
        biz_luna = _u("luna", "biz")
        biz_east = _u("east", "biz")
        conn.execute(
            text("""
                INSERT INTO businesses (id, name, whatsapp_e164, owner_user_id, verified, description, logo_url, website, contact_email, kra_receipt_counter, tap_balance, tap_plan, created_at)
                VALUES (:luna, 'Luna Events', '+254712300001', :diana, true,  'Premium event promotions & venue booking', 'https://picsum.photos/seed/luna-logo/200/200', 'https://lunaevents.co.ke', 'hello@lunaevents.co.ke', 0, 500, 'pro', :now),
                       (:east, 'Eastside Collective', '+254712300002', :eve, false, 'Community-driven events & pop-up markets', 'https://picsum.photos/seed/east-logo/200/200', 'https://eastside.co.ke', 'info@eastside.co.ke', 0, 50, 'starter', :now)
                ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, whatsapp_e164=EXCLUDED.whatsapp_e164, verified=EXCLUDED.verified
            """),
            {"luna": biz_luna, "east": biz_east, "diana": str(diana), "eve": str(eve), "now": now},
        )

        # 3) community_events — 5 events: 3 by Luna, 2 by Eastside
        events_data = [
            ("ce-luna-1", "Afro Fusion Night",        now + timedelta(hours=48),  "Nexus Arts Centre",  "A night of live Afrobeat, reggae, and fusion music.",     4, True,  "public", 1200),
            ("ce-luna-2", "Photography Masterclass",   now + timedelta(days=7),   "Skydeck Rooftop",    "Learn portrait & street photography from pro shooters.", 2, True,  "public", 2500),
            ("ce-luna-3", "Wine & Paint Evening",      now + timedelta(days=14),  "The Basement Lounge", "Unwind with canvas, brushes, and a glass of red.",        1, False, "public", 3500),
            ("ce-east-1", "Vintage Market Pop-Up",     now + timedelta(days=5),   "Skydeck Rooftop",    "Shop curated vintage fashion, vinyl & artisan goods.",    3, True,  "public", 0),
            ("ce-east-2", "Open Mic Comedy Night",     now + timedelta(days=10),  "The Basement Lounge", "Stand-up, spoken word & improv — all welcome.",           0, False, "public", 500),
        ]
        ce_ids = []
        for cekey, cetitle, cetime, cevenue, cedesc, cerank, ceticketing, cevis, _ in events_data:
            ceid = _u("alice", cekey)
            ce_ids.append(ceid)
            biz_id = biz_luna if "luna" in cekey else biz_east
            conn.execute(
                text("""
                    INSERT INTO community_events (id, user_id, source, title, start_time, venue, description, created_at, sponsored_rank, verified_badge, poster_image_uri, visibility, has_ticketing, has_products)
                    VALUES (:id, :uid, :src, :title, :st, :venue, :desc, :now, :rank, false, :poster, :vis, :tix, false)
                    ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, start_time=EXCLUDED.start_time, sponsored_rank=EXCLUDED.sponsored_rank
                """),
                {"id": ceid, "uid": str(alice), "src": SOURCE_TAG, "title": cetitle, "st": cetime, "venue": cevenue, "desc": cedesc, "now": now, "rank": cerank, "poster": POSTER(cekey), "vis": cevis, "tix": ceticketing},
            )
            # business_listing_attachments
            conn.execute(
                text("""
                    INSERT INTO business_listing_attachments (community_event_id, business_id, created_at)
                    VALUES (:ce, :biz, :now)
                    ON CONFLICT (community_event_id) DO UPDATE SET business_id=EXCLUDED.business_id
                """),
                {"ce": ceid, "biz": biz_id, "now": now},
            )

        # 4) event_videos — 1 per event (one pending for moderation)
        for i, ceid in enumerate(ce_ids):
            mod = "pending" if i == 3 else "approved"
            vid_id = _u("alice", f"ev-video-{i}")
            biz_id = biz_luna if i < 3 else biz_east
            conn.execute(
                text("""
                    INSERT INTO event_videos (id, community_event_id, business_id, storage_uri, moderation_status, created_at)
                    VALUES (:id, :ce, :biz, :uri, :mod, :now)
                    ON CONFLICT (id) DO UPDATE SET moderation_status=EXCLUDED.moderation_status, business_id=EXCLUDED.business_id
                """),
                {"id": vid_id, "ce": ceid, "biz": biz_id, "uri": [VIDEO_5S, VIDEO_10S, VIDEO_5S, VIDEO_15S, VIDEO_10S][i], "mod": mod, "now": now},
            )

        # 5) feed_videos — 5 videos (3 Luna, 2 Eastside, 1 pending)
        fv_count = 0
        for biz_id, biz_tag in [(biz_luna, "luna"), (biz_east, "east")]:
            for j in range(3 if biz_tag == "luna" else 2):
                mod = "pending" if (biz_tag == "east" and j == 1) else "approved"
                fv_id = _u("alice", f"fv-{biz_tag}-{j}")
                ce_link = ce_ids[fv_count] if fv_count < len(ce_ids) else None
                conn.execute(
                    text("""
                        INSERT INTO feed_videos (id, business_id, community_event_id, title, video_uri, thumbnail_uri, duration_seconds, video_type, moderation_status, is_paid, views, completion_rate, whatsapp_taps, sort_order, created_at)
                        VALUES (:id, :biz, :ce, :title, :vid, :thumb, :dur, 'promo', :mod, false, :views, :cr, :taps, :sort, :now)
                        ON CONFLICT (id) DO UPDATE SET moderation_status=EXCLUDED.moderation_status
                    """),
                    {"id": fv_id, "biz": biz_id, "ce": ce_link, "title": f"{biz_tag.title()} promo {j+1}", "vid": [VIDEO_5S, VIDEO_10S, VIDEO_5S][j], "thumb": THUMB, "dur": [5, 10, 5][j], "mod": mod, "views": [120, 85, 200][j], "cr": 0.85 if j != 2 else None, "taps": [8, 3, 15][j], "sort": fv_count, "now": now},
                )
                fv_count += 1

        # 6) ticket_types — 11 types across events with has_ticketing=true
        ticket_types = [
            # (event_index, name, price_minor, qty, sort)
            (0, "General Admission", 150000, 100, 0),   # KES 1,500
            (0, "VIP", 350000, 30, 1),                   # KES 3,500
            (0, "Early Bird", 100000, 50, 2),            # KES 1,000
            (1, "Standard", 250000, 40, 0),              # KES 2,500
            (1, "Student", 150000, 20, 1),               # KES 1,500
            (2, "General", 350000, 60, 0),               # KES 3,500
            (2, "Couple (2 ppl)", 600000, 15, 1),        # KES 6,000
            (3, "Free Entry", 0, 500, 0),                # Free
            (3, "Vendor Stall", 200000, 20, 1),          # KES 2,000
            (4, "General", 50000, 80, 0),                # KES 500
            (4, "Support the Arts", 150000, 10, 1),      # KES 1,500
        ]
        tt_ids = []
        for ei, ttname, ttprice, ttqty, ttsort in ticket_types:
            ttid = _u("alice", f"tt-{ei}-{ttsort}")
            tt_ids.append((ei, ttid))
            conn.execute(
                text("""
                    INSERT INTO ticket_types (id, community_event_id, name, price_minor_units, currency, quantity_available, quantity_sold, sort_order, is_active, created_at, updated_at)
                    VALUES (:id, :ce, :name, :price, 'KES', :qty, 0, :sort, true, :now, :now)
                    ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, price_minor_units=EXCLUDED.price_minor_units
                """),
                {"id": ttid, "ce": ce_ids[ei], "name": ttname, "price": ttprice, "qty": ttqty, "sort": ttsort, "now": now},
            )

        # 7) products (affiliate) — 3 products
        products = [
            ("prod-1", "Limited Edition Print", biz_luna, "Signed art print by Nairobi artist.", 150000, "https://picsum.photos/seed/prod-print/400/400"),
            ("prod-2", "Vinyl: Afrobeat Classics", biz_east, "Curated vinyl compilation.", 250000, "https://picsum.photos/seed/prod-vinyl/400/400"),
            ("prod-3", "Photography Guide E-Book", biz_luna, "Portrait photography digital guide.", 80000, "https://picsum.photos/seed/prod-ebook/400/400"),
        ]
        prod_ids = []
        for pkey, ptitle, pbiz, pdesc, pprice, pimg in products:
            pid = _u("alice", pkey)
            prod_ids.append(pid)
            conn.execute(
                text("""
                    INSERT INTO products (id, business_id, title, description, price_minor_units, currency, image_uri, is_active, created_at, updated_at)
                    VALUES (:id, :biz, :title, :desc, :price, 'KES', :img, true, :now, :now)
                    ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title
                """),
                {"id": pid, "biz": pbiz, "title": ptitle, "desc": pdesc, "price": pprice, "img": pimg, "now": now},
            )

        # 8) product_event_links — link products to events
        pel_data = [
            (0, 0, biz_luna, biz_luna),    # product 0 → event 0 (Luna-Luna, same biz)
            (1, 3, biz_east, biz_east),    # product 1 → event 3 (East-East)
            (2, 1, biz_luna, biz_luna),    # product 2 → event 1 (Luna-Luna)
        ]
        for pi, ei, seller, owner in pel_data:
            conn.execute(
                text("""
                    INSERT INTO product_event_links (id, product_id, community_event_id, seller_business_id, event_owner_business_id, commission_seller_percent, commission_owner_percent, commission_platform_percent, status, approved_at, created_at)
                    VALUES (:id, :prod, :ce, :seller, :owner, 80, 10, 10, 'approved', :now, :now)
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": _u("alice", f"pel-{pi}"), "prod": prod_ids[pi], "ce": ce_ids[ei], "seller": seller, "owner": owner, "now": now},
            )

        # 9) orders — Alice buys 3 ticket types across events
        # Alice buys 2 GA + 2 Early Bird for event 0, and 1 Standard for event 1
        orders_data = [
            ("order-0", 0, alice, [tt_ids[0], tt_ids[2]], [2, 2], (150000*2 + 100000*2), "paid"),
            ("order-1", 1, alice, [tt_ids[3]], [1], 250000, "paid"),
            ("order-2", 3, bob, [tt_ids[7]], [4], 0, "paid"),  # Free tickets
            ("order-3", 3, charlie, [tt_ids[7]], [1], 0, "paid"),
            ("order-4", 4, diana, [tt_ids[9]], [2], 100000, "paid"), # KES 1000
            ("order-5", 0, eve, [tt_ids[0]], [1], 150000, "paid"),   # KES 1500
        ]
        order_uuids = []
        for oi, (okey, oei, ouser, otts, oqtys, ototal, ostatus) in enumerate(orders_data):
            oid = _u("alice", okey)
            order_uuids.append(oid)
            plat_fee = int(ototal * 0.08)
            biz_net = ototal - plat_fee
            conn.execute(
                text("""
                    INSERT INTO orders (id, community_event_id, user_id, status, type, total_minor_units, platform_fee_minor_units, business_net_minor_units, currency, paid_at, receipt_number, points_earned, created_at, updated_at)
                    VALUES (:id, :ce, :uid, :status, 'ticket', :total, :fee, :net, 'KES', :now, :receipt, :pts, :now, :now)
                    ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status
                """),
                {"id": oid, "ce": ce_ids[oei], "uid": str(ouser), "status": ostatus, "total": ototal, "fee": plat_fee, "net": biz_net, "receipt": f"EVT-{now.strftime('%y%m')}-{oi+1:06d}", "pts": ototal // 100, "now": now},
            )
            # order_items
            for ti, (tt_pair, qty) in enumerate(zip(otts, oqtys)):
                _, tt_uuid = tt_pair
                conn.execute(
                    text("""
                        INSERT INTO order_items (id, order_id, ticket_type_id, quantity, unit_price_minor_units, subtotal_minor_units)
                        VALUES (:id, :oid, :tt, :qty, :unit, :sub)
                        ON CONFLICT (id) DO UPDATE SET quantity=EXCLUDED.quantity
                    """),
                    {"id": _u("alice", f"oi-{okey}-{ti}"), "oid": oid, "tt": tt_uuid, "qty": qty, "unit": 0, "sub": 0},
                )

        # 10) tickets — individual scannable tickets
        ticket_data = [
            (0, "EVT-AA01", tt_ids[0][1], ce_ids[0], alice, "active"),
            (0, "EVT-AA02", tt_ids[0][1], ce_ids[0], alice, "active"),
            (0, "EVT-AB01", tt_ids[2][1], ce_ids[0], alice, "active"),
            (0, "EVT-AB02", tt_ids[2][1], ce_ids[0], alice, "active"),
            (1, "EVT-AC01", tt_ids[3][1], ce_ids[1], alice, "active"),
            (2, "EVT-BA01", tt_ids[7][1], ce_ids[3], bob, "active"),
            (2, "EVT-BA02", tt_ids[7][1], ce_ids[3], bob, "active"),
            (2, "EVT-BA03", tt_ids[7][1], ce_ids[3], bob, "active"),
            (2, "EVT-BA04", tt_ids[7][1], ce_ids[3], bob, "active"),
        ]
        for oi, code, tt_uuid, ce_uuid, user, tstatus in ticket_data:
            conn.execute(
                text("""
                    INSERT INTO tickets (id, short_code, order_id, ticket_type_id, community_event_id, user_id, status, created_at)
                    VALUES (:id, :code, :oid, :tt, :ce, :uid, :status, :now)
                    ON CONFLICT (short_code) DO NOTHING
                """),
                {"id": _u("alice", f"tix-{code}"), "code": code, "oid": order_uuids[oi], "tt": str(tt_uuid), "ce": str(ce_uuid), "uid": str(user), "status": tstatus, "now": now},
            )

        # 11) business_payout_settings + business_payouts
        for biz_id in [biz_luna, biz_east]:
            conn.execute(
                text("""
                    INSERT INTO business_payout_settings (business_id, payout_method, mpesa_till_number, payout_frequency, minimum_payout_minor, updated_at)
                    VALUES (:biz, 'mpesa_till', :till, 'weekly', 50000, :now)
                    ON CONFLICT (business_id) DO UPDATE SET payout_method=EXCLUDED.payout_method
                """),
                {"biz": biz_id, "till": "123456" if biz_id == biz_luna else "789012", "now": now},
            )
            conn.execute(
                text("""
                    INSERT INTO business_payouts (id, business_id, period_start, period_end, gross_minor_units, platform_fees_minor_units, net_payout_minor_units, type, currency, status, created_at)
                    VALUES (:id, :biz, :start, :end, 500000, 40000, 460000, 'ticket_sales', 'KES', 'paid', :now)
                    ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status
                """),
                {"id": _u("alice", f"payout-{biz_id[-8:]}"), "biz": biz_id, "start": now - timedelta(days=14), "end": now - timedelta(days=7), "now": now},
            )

        # 12) claims — one claim by Bob on order
        conn.execute(
            text("""
                INSERT INTO claims (id, order_id, user_id, business_id, claim_type, reason, status, created_at)
                VALUES (:id, :oid, :uid, :biz, 'event_cancelled', 'Event was rescheduled without notice', 'open', :now)
                ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status
            """),
            {"id": _u("alice", "claim-0"), "oid": order_uuids[2], "uid": str(bob), "biz": biz_east, "now": now},
        )

        # 13) user_subscriptions — Alice is premium
        conn.execute(
            text("""
                INSERT INTO user_subscriptions (id, user_id, plan, status, stripe_subscription_id, current_period_start, current_period_end, created_at)
                VALUES (:id, :uid, 'premium', 'active', 'sub_mock_alice', :start, :end, :now)
                ON CONFLICT (user_id) DO UPDATE SET status=EXCLUDED.status
            """),
            {"id": _u("alice", "sub"), "uid": str(alice), "start": now, "end": now + timedelta(days=30), "now": now},
        )

        # 14) user_points — Alice and Bob have points
        for uid, bal, earned, redeemed in [(alice, 450, 500, 50), (bob, 120, 120, 0)]:
            conn.execute(
                text("""
                    INSERT INTO user_points (user_id, balance, lifetime_earned, lifetime_redeemed, last_activity, created_at)
                    VALUES (:uid, :bal, :earned, :redeemed, :now, :now)
                    ON CONFLICT (user_id) DO UPDATE SET balance=EXCLUDED.balance, lifetime_earned=EXCLUDED.lifetime_earned
                """),
                {"uid": str(uid), "bal": bal, "earned": earned, "redeemed": redeemed, "now": now},
            )

        # 15) feed_watch_log — 4 watch events
        fv_ids = [_u("alice", f"fv-{t}-{j}") for t in ["luna", "east"] for j in range(3 if t == "luna" else 2)]
        watch_data = [
            (alice, fv_ids[0], 5, True, 1),
            (alice, fv_ids[1], 10, True, 1),
            (bob, fv_ids[0], 3, False, 0),
            (charlie, fv_ids[2], 5, True, 1),
        ]
        for wi, (wuser, wfv, wsec, wcomp, wpts) in enumerate(watch_data):
            conn.execute(
                text("""
                    INSERT INTO feed_watch_log (id, user_id, feed_video_id, watched_seconds, completed, points_earned, watched_at)
                    VALUES (:id, :uid, :fv, :sec, :comp, :pts, :now)
                    ON CONFLICT (id) DO UPDATE SET watched_seconds=EXCLUDED.watched_seconds
                """),
                {"id": _u("alice", f"watch-{wi}"), "uid": str(wuser), "fv": wfv, "sec": wsec, "comp": wcomp, "pts": wpts, "now": now},
            )

        # 16) user_preferences — Alice monthly budget
        conn.execute(
            text("""
                INSERT INTO user_preferences (user_id, monthly_budget_minor_units, updated_at)
                VALUES (:uid, 500000, :now)
                ON CONFLICT (user_id) DO UPDATE SET monthly_budget_minor_units=EXCLUDED.monthly_budget_minor_units
            """),
            {"uid": str(alice), "now": now},
        )

        # 17) scheduled_events — Alice creates 3 personal events
        sched_data = [
            ("sched-1", "Birthday Dinner", now + timedelta(days=3), "Talisman Restaurant", "private", str(alice)),
            ("sched-2", "Team Offsite", now + timedelta(days=9), "Nairobi National Park", "private", str(alice)),
            ("sched-3", "Weekend Hike", now + timedelta(days=16), "Ngong Hills", "public", str(alice)),
        ]
        sched_uuids = []
        for skey, stitle, stime, svenue, svis, suid in sched_data:
            sid = _u("alice", skey)
            sched_uuids.append(sid)
            conn.execute(
                text("""
                    INSERT INTO scheduled_events (id, user_id, title, start_time, venue, raw_venue_text, visibility)
                    VALUES (:id, :uid, :title, :st, :venue, :raw, :vis)
                    ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title
                """),
                {"id": sid, "uid": suid, "title": stitle, "st": stime, "venue": svenue, "raw": svenue, "vis": svis},
            )

        # 18) event_drafts — 2 drafts, 1 confirmed
        draft_data = [
            ("draft-pending", "Yoga in the Park", now + timedelta(days=21), "Uhuru Park", None, 0.65, None),
            ("draft-confirmed", "Book Club Meetup", now + timedelta(days=25), "Junction Mall", now - timedelta(hours=2), 0.92, "Free"),
        ]
        for dkey, dtitle, dtime, dvenue, dconf, dcs, dprice in draft_data:
            conn.execute(
                text("""
                    INSERT INTO event_drafts (id, user_id, title, start_time, venue, confidence_score, confirmed_at, price)
                    VALUES (:id, :uid, :title, :st, :venue, :cs, :cf, :price)
                    ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title
                """),
                {"id": _u("alice", dkey), "uid": str(alice), "title": dtitle, "st": dtime, "venue": dvenue, "cs": dcs, "cf": dconf, "price": dprice, "now": now},
            )

        # 19) poster_assets + poster_asset_parses + event_sources
        if _table_exists(conn, "poster_assets"):
            for pkey in ("poster-asset-a", "poster-asset-b", "poster-asset-c"):
                paid = _u("alice", pkey)
                conn.execute(
                    text("""
                        INSERT INTO poster_assets (id, dhash64, content_sha256, poster_id, content_type, created_at)
                        VALUES (:id, :dh, :sha, :pid, 'image/jpeg', :now)
                        ON CONFLICT (id) DO UPDATE SET dhash64=EXCLUDED.dhash64
                    """),
                    {"id": paid, "dh": pkey[:32], "sha": pkey, "pid": _u("alice", f"ps-{pkey}"), "now": now},
                )
                if _table_exists(conn, "poster_asset_parses"):
                    conn.execute(
                        text("""
                            INSERT INTO poster_asset_parses (id, poster_asset_id, parsed_json, model_version, created_at)
                            VALUES (:id, :pa, CAST(:pj AS jsonb), 'gemini-2.5-flash', :now)
                            ON CONFLICT (poster_asset_id) DO UPDATE SET parsed_json=EXCLUDED.parsed_json
                        """),
                        {"id": _u("alice", f"parse-{pkey}"), "pa": paid, "pj": json.dumps({"title": "Sample Event", "venue": "Nairobi", "confidence_score": 0.88}), "now": now},
                    )

        # 20) groups (friend group) + memberships + rsvps + shares
        gid = _u("alice", "group-weekend")
        conn.execute(
            text("""
                INSERT INTO groups (id, name, owner_user_id, created_at, group_type, invite_token, pinned_event_id)
                VALUES (:id, 'Weekend Crew', :owner, :now, 'friend', :tok, :pin)
                ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name
            """),
            {"id": gid, "owner": str(alice), "now": now, "tok": _u("alice", "invite")[:64], "pin": sched_uuids[2]},
        )
        # All 5 users in the same group
        all_users = [alice, bob, charlie, diana, eve]
        owners = {str(alice)}
        for uid in all_users:
            conn.execute(
                text("""
                    INSERT INTO group_memberships (group_id, user_id, role, created_at)
                    VALUES (:g, :u, :role, :now)
                    ON CONFLICT (group_id, user_id) DO UPDATE SET role=EXCLUDED.role
                """),
                {"g": gid, "u": str(uid), "role": "owner" if str(uid) in owners else "member", "now": now},
            )
        # Share all 3 scheduled events to the group
        for se in sched_uuids:
            conn.execute(
                text("""
                    INSERT INTO event_shares (event_id, group_id, shared_by_user_id, created_at)
                    VALUES (:e, :g, :u, :now)
                    ON CONFLICT (event_id, group_id) DO NOTHING
                """),
                {"e": se, "g": gid, "u": str(alice), "now": now},
            )
        # RSVPs — everyone RSVPs to at least one event
        rsvp_data = [
            (gid, alice, sched_uuids[0], "going"),
            (gid, alice, sched_uuids[2], "going"),
            (gid, bob, sched_uuids[2], "going"),
            (gid, bob, sched_uuids[0], "maybe"),
            (gid, charlie, sched_uuids[0], "going"),
            (gid, charlie, sched_uuids[2], "going"),
            (gid, diana, sched_uuids[2], "going"),
            (gid, diana, sched_uuids[1], "maybe"),
            (gid, eve, sched_uuids[0], "going"),
            (gid, eve, sched_uuids[1], "going"),
        ]
        for rg, ru, re, rs in rsvp_data:
            conn.execute(
                text("""
                    INSERT INTO group_rsvps (group_id, user_id, event_id, status, updated_at)
                    VALUES (:g, :u, :e, :s, :now)
                    ON CONFLICT ON CONSTRAINT pk_group_rsvps DO UPDATE SET status=EXCLUDED.status
                """),
                {"g": rg, "u": str(ru), "e": str(re), "s": rs, "now": now},
            )

        # 21) follows — all users follow each other (complete social graph)
        for i, a in enumerate(all_users):
            for b in all_users[i+1:]:
                for f, fwee in [(a, b), (b, a)]:
                    conn.execute(
                        text("""
                            INSERT INTO follows (follower_user_id, following_user_id, created_at)
                            VALUES (:f, :fwee, :now)
                            ON CONFLICT (follower_user_id, following_user_id) DO NOTHING
                        """),
                        {"f": str(f), "fwee": str(fwee), "now": now},
                    )
        for uid, bid in [(bob, biz_luna), (charlie, biz_luna), (charlie, biz_east), (alice, biz_luna)]:
            conn.execute(
                text("""
                    INSERT INTO business_follows (follower_user_id, business_id, created_at)
                    VALUES (:u, :b, :now)
                    ON CONFLICT (follower_user_id, business_id) DO NOTHING
                """),
                {"u": str(uid), "b": bid, "now": now},
            )

        # 22) shared_link_listings — approved + rejected URLs
        sl_approved = "https://example.com/approved-event-link"
        sl_rejected = "https://example.com/spam-link"
        conn.execute(
            text("""
                INSERT INTO shared_link_listings (normalized_url, status, cached_payload, source_url_raw, created_at, updated_at)
                VALUES (:u1, 'approved', CAST(:p1 AS jsonb), :r1, :now, :now),
                       (:u2, 'rejected', CAST(:p2 AS jsonb), :r2, :now, :now)
                ON CONFLICT (normalized_url) DO UPDATE SET status=EXCLUDED.status
            """),
            {"u1": normalize_shared_url(sl_approved), "r1": sl_approved, "p1": json.dumps({"title": "Valid event link", "venue": "Nairobi"}),
             "u2": normalize_shared_url(sl_rejected), "r2": sl_rejected, "p2": json.dumps({"title": "Spam", "venue": "Unknown"}), "now": now},
        )

        # 23) listing_analytics_events — 6 events
        analytics_data = [
            ("ana-impression-0", ce_ids[0], biz_luna, alice, "listing_impression", {"source": "discover_feed"}),
            ("ana-wa-0", ce_ids[0], biz_luna, bob, "whatsapp_tap", {"source": "discover_feed"}),
            ("ana-save-0", ce_ids[0], biz_luna, charlie, "save", {"source": "discover_feed"}),
            ("ana-impression-1", ce_ids[1], biz_luna, alice, "listing_impression", {"source": "feed_home"}),
            ("ana-impression-3", ce_ids[3], biz_east, bob, "listing_impression", {"source": "discover_feed"}),
            ("ana-wa-3", ce_ids[3], biz_east, bob, "whatsapp_tap", {"source": "discover_feed"}),
        ]
        for ak, ace, abiz, auid, ametric, ameta in analytics_data:
            conn.execute(
                text("""
                    INSERT INTO listing_analytics_events (id, community_event_id, business_id, user_id, metric_type, meta, created_at)
                    VALUES (:id, :ce, :biz, :uid, :metric, CAST(:meta AS jsonb), :now)
                    ON CONFLICT (id) DO UPDATE SET metric_type=EXCLUDED.metric_type
                """),
                {"id": _u("alice", ak), "ce": ace, "biz": abiz, "uid": str(auid), "metric": ametric, "meta": json.dumps(ameta), "now": now},
            )

        # 24) user_locations — Alice home + work
        loc_data = [("home", "Karen, Nairobi", -1.3150, 36.7400), ("work", "Westlands, Nairobi", -1.2667, 36.8167)]
        for ll, laddr, llat, llng in loc_data:
            conn.execute(
                text("""
                    INSERT INTO user_locations (user_id, label, address, lat, lng)
                    VALUES (:uid, :label, :addr, :lat, :lng)
                    ON CONFLICT (user_id, label) DO UPDATE SET address=EXCLUDED.address
                """),
                {"uid": str(alice), "label": ll, "addr": laddr, "lat": llat, "lng": llng},
            )

        # 25) referral_links
        conn.execute(
            text("""
                INSERT INTO referral_links (id, affiliate_business_id, community_event_id, code, commission_percent, total_clicks, total_taps, created_at)
                VALUES (:id, :biz, :ce, :code, 30, 15, 3, :now)
                ON CONFLICT (code) DO NOTHING
            """),
            {"id": _u("alice", "ref-link-0"), "biz": biz_luna, "ce": ce_ids[0], "code": "LUNA-AFRO", "now": now},
        )

        # 26) pgvector embeddings if available
        if _table_exists(conn, "community_event_embeddings"):
            for ceid, (_, cetitle, _, cevenue, cedesc, _, _, _, _) in zip(ce_ids, events_data):
                blob = " ".join([cetitle, cevenue, cedesc]).strip()
                vec = embedder.embed_text(text=blob)
                conn.execute(
                    text("""
                        INSERT INTO community_event_embeddings (community_event_id, embedding, embedding_model, embedded_at)
                        VALUES (:id, (:emb)::vector, 'deterministic-64', :now)
                        ON CONFLICT (community_event_id) DO UPDATE SET embedding= (:emb)::vector
                    """),
                    {"id": ceid, "emb": _vector_literal(vec), "now": now},
                )

        # 27) poster_processing_logs — 3 entries
        if _table_exists(conn, "poster_processing_logs"):
            log_data = [
                ("ppl-1", "Afro Fusion Night", TODAY.isoformat(), "Nexus Arts Centre", 0.92, "KES 1,500", "accepted"),
                ("ppl-2", "??", None, "Unknown", 0.35, None, "pending"),
                ("ppl-3", "Weekend Market", (TODAY + timedelta(days=5)).isoformat(), "Parklands", 0.78, "Free", "accepted"),
            ]
            for lkey, ltitle, ltime, lvenue, lconf, lprice, lstatus in log_data:
                conn.execute(
                    text("""
                        INSERT INTO poster_processing_logs (id, poster_asset_id, user_id, extracted_title, extracted_start_time, extracted_venue, confidence_score, extracted_price, model_version, status, created_at)
                        VALUES (:id, :paid, :uid, :title, CAST(:st AS timestamptz), :venue, :conf, :price, 'gemini-2.5-flash', :status, :now)
                        ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status
                    """),
                    {"id": _u("alice", lkey), "paid": _u("alice", "poster-asset-a"), "uid": str(bob), "title": ltitle, "st": ltime, "venue": lvenue, "conf": lconf, "price": lprice, "status": lstatus, "now": now},
                )

        # 28a) user_profiles — all 5 users have public profiles
        display_names = {
            str(alice): "Alice W",
            str(bob): "Bob K",
            str(charlie): "Charlie M",
            str(diana): "Diana N",
            str(eve): "Eve O",
        }
        for uid in all_users:
            conn.execute(
                text("""
                    INSERT INTO user_profiles (user_id, display_name, avatar_url, is_public, created_at, updated_at)
                    VALUES (:uid, :name, :avatar, true, :now, :now)
                    ON CONFLICT (user_id) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        is_public = true,
                        updated_at = EXCLUDED.updated_at
                """),
                {"uid": str(uid), "name": display_names.get(str(uid), "User"), "avatar": f"https://picsum.photos/seed/{uid}/200/200", "now": now},
            )

        # 28b) admin_console_allowlist — add Alice as admin
        conn.execute(
            text("""
                INSERT INTO admin_console_allowlist (user_id, created_at)
                VALUES (:uid, :now)
                ON CONFLICT (user_id) DO NOTHING
            """),
            {"uid": str(alice), "now": now},
        )

        print("✅ Seeded production demo data:")
        print(f"   Users: alice={alice}, bob={bob}, charlie={charlie}, diana={diana}, eve={eve}")
        print("   5 user_profiles (all public)")
        print("   2 businesses (Luna Events, Eastside Collective)")
        print("   5 community_events with ticket_types + videos")
        print("   5 feed_videos (4 approved, 1 pending)")
        print("   3 affiliate products linked to events")
        print("   3 orders with individual scannable tickets")
        print("   1 premium subscription (Alice)")
        print("   1 friend group (Weekend Crew) — all 5 users + 10 RSVPs")
        print("   20 mutual follow relationships (complete social graph)")
        print("   1 open claim (Bob)")
        print("   6 analytics events")
        print("   1 referral link")
        print("   1 admin (Alice in admin_console_allowlist)")
        print("   3 poster processing logs")
        print("")
        print("   To verify: browse the discover feed, admin console, and business portal.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
