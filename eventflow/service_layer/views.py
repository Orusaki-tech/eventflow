from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List
from uuid import UUID

from sqlalchemy import text

from eventflow.adapters.repository import AbstractDraftRepository, AbstractEventRepository


def get_upcoming_events(
    *,
    user_id: UUID,
    session: Any | None = None,
    events_repo: AbstractEventRepository | None = None,
    days_ahead: int = 30,
    limit: int = 50,
) -> List[dict]:
    priority_days = 30
    if session is None:
        if events_repo is None:
            return []
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(days=int(days_ahead))
        events = [
            e
            for e in events_repo.list_upcoming(user_id=user_id, now=now, limit=limit)
            if e.start_time <= horizon and getattr(e, "cancelled_at", None) is None
        ]
        priority_cutoff = now + timedelta(days=priority_days)
        events.sort(key=lambda e: (0 if e.start_time <= priority_cutoff else 1, e.start_time))
        return [
            {
                "id": e.id,
                "user_id": e.user_id,
                "title": e.title,
                "start_time": e.start_time,
                "venue": e.venue,
                "price": getattr(e, "price", None),
                "alert_time": None,
            }
            for e in events
        ]

    results = session.execute(
        text(
            """
            WITH me_groups AS (
              SELECT gm.group_id
              FROM group_memberships gm
              WHERE gm.user_id = :user_id
            ),
            visible_events AS (
              SELECT e.*
              FROM scheduled_events e
              WHERE e.user_id = :user_id
                AND e.cancelled_at IS NULL

              UNION

              SELECT e.*
              FROM scheduled_events e
              JOIN event_shares es ON es.event_id = e.id
              JOIN me_groups mg ON mg.group_id = es.group_id
              WHERE e.cancelled_at IS NULL

              UNION

              SELECT e.*
              FROM scheduled_events e
              WHERE e.visibility = 'public'
                AND e.cancelled_at IS NULL
            )
            SELECT e.id, e.user_id, e.title, e.start_time, e.venue, e.price,
                   a.trigger_at as alert_time,
                    CASE
                      WHEN e.user_id = :user_id THEN COALESCE(e.description_public, e.description_close_friends)
                      WHEN e.visibility = 'public' THEN e.description_public
                      ELSE e.description_public
                    END AS description
            FROM visible_events e
            LEFT JOIN alerts a ON a.event_id = e.id
                              AND a.alert_type = 'TRAFFIC_ALERT'
            WHERE e.start_time > CURRENT_TIMESTAMP
              AND e.start_time <= CURRENT_TIMESTAMP + (:days_ahead || ' days')::interval
            ORDER BY
              CASE
                WHEN e.start_time <= CURRENT_TIMESTAMP + (:priority_days || ' days')::interval THEN 0
                ELSE 1
              END ASC,
              e.start_time ASC
            LIMIT :limit
            """
        ),
        {
            "user_id": str(user_id),
            "limit": int(limit),
            "days_ahead": int(days_ahead),
            "priority_days": int(priority_days),
        },
    )
    return [dict(r._mapping) for r in results]


def list_today_events(
    *,
    user_id: UUID,
    session: Any,
    tz_offset_minutes: int,
    limit: int = 200,
) -> List[dict]:
    """
    Today feed includes:
    - my events (any visibility)
    - events shared to groups I'm a member of
    - public events by others

    Day boundaries are computed using a client-provided timezone offset.
    """
    # Postgres: treat start_time as timestamptz and compare against a derived local-day window.
    # We compute "now at user local tz" by shifting UTC by offset minutes.
    results = session.execute(
        text(
            """
            WITH me_groups AS (
              SELECT gm.group_id
              FROM group_memberships gm
              WHERE gm.user_id = :user_id
            ),
            visible_events AS (
              SELECT e.*
              FROM scheduled_events e
              WHERE e.user_id = :user_id
                AND e.cancelled_at IS NULL

              UNION

              SELECT e.*
              FROM scheduled_events e
              JOIN event_shares es ON es.event_id = e.id
              JOIN me_groups mg ON mg.group_id = es.group_id
              WHERE e.cancelled_at IS NULL

              UNION

              SELECT e.*
              FROM scheduled_events e
              WHERE e.visibility = 'public'
                AND e.cancelled_at IS NULL
            ),
            bounds AS (
              SELECT
                date_trunc('day', (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval) AS local_day_start,
                date_trunc('day', (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval) + interval '1 day' AS local_day_end
            )
            SELECT
              e.id,
              e.user_id,
              e.title,
              e.start_time,
              e.venue,
              e.price,
              e.venue_id,
              e.visibility,
              CASE
                WHEN e.user_id = :user_id THEN COALESCE(e.description_public, e.description_close_friends)
                WHEN e.visibility = 'public' THEN e.description_public
                ELSE e.description_public
              END AS description
            FROM visible_events e, bounds b
            WHERE (e.start_time AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval >= b.local_day_start
              AND (e.start_time AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval < b.local_day_end
            ORDER BY e.start_time ASC
            LIMIT :limit
            """
        ),
        {
            "user_id": str(user_id),
            "offset_mins": int(tz_offset_minutes),
            "limit": int(limit),
        },
    )
    return [dict(r._mapping) for r in results]


def list_drafts(
    *,
    user_id: UUID,
    session: Any | None = None,
    drafts_repo: AbstractDraftRepository | None = None,
    status: str | None,
    limit: int = 50,
) -> List[dict]:
    if session is None:
        if drafts_repo is None:
            return []
        drafts = drafts_repo.list_for_user(user_id=user_id, limit=limit)
        if status == "pending":
            drafts = [d for d in drafts if d.confirmed_at is None]
        elif status == "confirmed":
            drafts = [d for d in drafts if d.confirmed_at is not None]
        return [
            {
                "draft_id": d.id,
                "title": d.title,
                "start_time": d.start_time,
                "venue": d.venue,
                "confidence_score": d.confidence_score,
                "confirmed_at": d.confirmed_at,
                "price": getattr(d, "price", None),
            }
            for d in drafts[: int(limit)]
        ]

    if status is not None and status not in {"pending", "confirmed"}:
        raise ValueError(f"Invalid status: {status!r}")
    where_confirmed = ""
    if status == "pending":
        where_confirmed = "AND d.confirmed_at IS NULL"
    elif status == "confirmed":
        where_confirmed = "AND d.confirmed_at IS NOT NULL"
    else:
        where_confirmed = ""

    results = session.execute(
        text(
            f"""
            SELECT d.id as draft_id,
                   d.title,
                   d.start_time,
                   d.venue,
                   d.confidence_score,
                   d.confirmed_at,
                   d.price
            FROM event_drafts d
            WHERE d.user_id = :user_id
            {where_confirmed}
            ORDER BY d.start_time DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"user_id": str(user_id), "limit": int(limit)},
    )
    return [dict(r._mapping) for r in results]


def list_community_events(*, session: Any, user_id: UUID | None = None, limit: int = 50) -> List[dict]:
    results = session.execute(
        text(
            """
            SELECT e.id as community_event_id,
                   e.source,
                   e.title,
                   e.start_time,
                   e.venue,
                   e.description,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE TRUE
            ORDER BY e.start_time DESC
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    )
    return [dict(r._mapping) for r in results]


def list_my_community_events(*, session: Any, user_id: UUID, limit: int = 50) -> List[dict]:
    results = session.execute(
        text(
            """
            SELECT e.id as community_event_id,
                   e.source,
                   e.title,
                   e.start_time,
                   e.venue,
                   e.description,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE e.user_id = :uid
            ORDER BY e.start_time DESC
            LIMIT :limit
            """
        ),
        {"uid": str(user_id), "limit": int(limit)},
    )
    return [dict(r._mapping) for r in results]


def get_my_community_event_detail(*, session: Any, user_id: UUID, community_event_id: UUID) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT e.id as community_event_id,
                   e.source,
                   e.title,
                   e.start_time,
                   e.venue,
                   e.description,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE e.id = :id AND e.user_id = :uid
            LIMIT 1
            """
        ),
        {"id": str(community_event_id), "uid": str(user_id)},
    ).first()
    if row is None:
        return None
    out = dict(row._mapping)
    alias_rows = session.execute(
        text(
            """
            SELECT normalized_url FROM community_event_share_aliases
            WHERE community_event_id = :ce
            ORDER BY created_at ASC
            """
        ),
        {"ce": str(community_event_id)},
    ).fetchall()
    out["normalized_share_aliases"] = [str(ar[0]) for ar in alias_rows]
    return out


def search_community_events(*, session: Any, query_vector: str, limit: int = 20) -> List[dict]:
    results = session.execute(
        text(
            """
            SELECT e.id as community_event_id,
                   e.source,
                   e.title,
                   e.start_time,
                   e.venue,
                   e.description,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri,
                   (emb.embedding <-> (:qvec)::vector) AS distance
            FROM community_event_embeddings emb
            JOIN community_events e ON e.id = emb.community_event_id
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            ORDER BY emb.embedding <-> (:qvec)::vector ASC
            LIMIT :limit
            """
        ),
        {"qvec": query_vector, "limit": int(limit)},
    )
    return [dict(r._mapping) for r in results]


def list_feed_home(*, user_id: UUID, session: Any | None, limit: int = 50, offset: int = 0) -> List[dict]:
    """Compose discovery feed: followed organisers plus trending/sponsored community listings."""
    if session is None:
        return []
    # Each sub-query fetches limit+offset rows to account for dedup across categories.
    fetch = int(limit) + int(offset)
    merged: dict[str, dict] = {}
    followed = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.user_id,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            INNER JOIN follows f ON f.following_user_id = e.user_id AND f.follower_user_id = :uid
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE e.start_time > NOW()
            ORDER BY e.start_time ASC
            LIMIT :lim
            """
        ),
        {"uid": str(user_id), "lim": fetch},
    )
    for r in followed:
        merged[str(r.id)] = dict(r._mapping)

    business_followed = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.user_id,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            INNER JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            INNER JOIN business_follows bf ON bf.business_id = bl.business_id AND bf.follower_user_id = :uid
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE e.start_time > NOW()
            ORDER BY e.start_time ASC
            LIMIT :lim
            """
        ),
        {"uid": str(user_id), "lim": fetch},
    )
    for r in business_followed:
        k = str(r.id)
        if k not in merged:
            merged[k] = dict(r._mapping)

    trending = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.user_id,
                   e.poster_image_uri,
                   bl.business_id,
                   b.whatsapp_e164,
                   v.hero_video_uri
            FROM community_events e
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE e.start_time > NOW()
            ORDER BY e.start_time ASC
            LIMIT :lim
            """
        ),
        {"lim": fetch},
    )
    for r in trending:
        k = str(r.id)
        if k not in merged:
            merged[k] = dict(r._mapping)

    items = list(merged.values())
    items.sort(key=lambda row: row.get("start_time"))
    return items[int(offset) : int(offset) + int(limit)]


def list_unified_feed(
    *,
    session: Any,
    user_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    """Blend feed_videos, community_events, and affiliate products into a single interleaved feed."""
    fetch = int(limit) + int(offset)

    # 1. Business promo videos (feed_videos)
    videos = session.execute(
        text(
            """
            SELECT
                fv.id AS item_id,
                'video' AS kind,
                fv.title,
                fv.video_uri,
                fv.thumbnail_uri,
                fv.duration_seconds,
                fv.views,
                fv.whatsapp_taps,
                fv.video_type,
                fv.community_event_id,
                ce.title AS event_title,
                b.id AS business_id,
                b.name AS business_name,
                b.logo_url AS business_logo,
                b.whatsapp_e164
            FROM feed_videos fv
            LEFT JOIN businesses b ON b.id = fv.business_id
            LEFT JOIN community_events ce ON ce.id = fv.community_event_id
            WHERE fv.moderation_status = 'approved'
            ORDER BY fv.created_at DESC
            LIMIT :lim
            """
        ),
        {"lim": fetch},
    ).fetchall()

    # 2. Community events with attending friends count
    uid_filter = ""
    uid_params: dict[str, object] = {}
    if user_id:
        uid_filter = """
            LEFT JOIN (
                SELECT gr.event_id, ARRAY_AGG(DISTINCT gr.user_id) AS attending_user_ids, COUNT(DISTINCT gr.user_id) AS attending_count
                FROM group_rsvps gr
                JOIN group_memberships gm ON gm.group_id = gr.group_id
                WHERE gm.user_id = :uid AND gr.status = 'going'
                GROUP BY gr.event_id
            ) att ON att.event_id = e.id
        """
        uid_params["uid"] = str(user_id)
    uid_params["lim"] = fetch

    events = session.execute(
        text(
            f"""
            SELECT
                e.id AS item_id,
                'event' AS kind,
                e.title,
                e.start_time,
                e.venue,
                e.description,
                e.poster_image_uri,
                e.user_id AS organizer_user_id,
                bl.business_id,
                b.whatsapp_e164,
                v.hero_video_uri,
                COALESCE(att.attending_count, 0) AS attending_friends_count,
                COALESCE(att.attending_user_ids, ARRAY[]::uuid[]) AS attending_friend_ids,
                (
                    SELECT MIN(tt.price_minor_units)
                    FROM ticket_types tt
                    WHERE tt.community_event_id = e.id AND tt.is_active = true
                ) AS price_minor_units
            FROM community_events e
            LEFT JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            {uid_filter}
            ORDER BY e.start_time DESC
            LIMIT :lim
            """
        ),
        uid_params,
    ).fetchall()

    # 3. Affiliate products linked to events
    affiliates = session.execute(
        text(
            """
            SELECT
                pel.id AS item_id,
                'affiliate' AS kind,
                p.title,
                p.description,
                p.price_minor_units,
                p.image_uri,
                pel.seller_business_id,
                b.name AS seller_name,
                b.whatsapp_e164,
                pel.community_event_id,
                ce.title AS event_title,
                pel.commission_seller_percent
            FROM product_event_links pel
            JOIN products p ON p.id = pel.product_id
            LEFT JOIN businesses b ON b.id = pel.seller_business_id
            LEFT JOIN community_events ce ON ce.id = pel.community_event_id
            WHERE pel.status = 'approved'
            ORDER BY pel.id DESC
            LIMIT :lim
            """
        ),
        {"lim": fetch},
    ).fetchall()

    # 4. Interleave: pattern [video, video, event, video, video, affiliate]
    # Ratio: 66% video, 16% event, 16% affiliate
    pattern = ["V", "V", "E", "V", "V", "A"]
    result: list[dict] = []
    vi = ei = ai = 0
    max_items = int(limit) + int(offset)
    slot = 0
    while len(result) < max_items:
        kind = pattern[slot % len(pattern)]
        slot += 1
        if kind == "V" and vi < len(videos):
            result.append(dict(videos[vi]._mapping))
            vi += 1
        elif kind == "E" and ei < len(events):
            ev = dict(events[ei]._mapping)
            if ev.get("attending_friend_ids") and isinstance(ev["attending_friend_ids"], list):
                ev["attending_friend_ids"] = [str(uid) for uid in ev["attending_friend_ids"]]
            result.append(ev)
            ei += 1
        elif kind == "A" and ai < len(affiliates):
            result.append(dict(affiliates[ai]._mapping))
            ai += 1
        else:
            # Fallback: add whatever is available
            added = False
            if vi < len(videos):
                result.append(dict(videos[vi]._mapping))
                vi += 1
                added = True
            elif ei < len(events):
                ev = dict(events[ei]._mapping)
                if ev.get("attending_friend_ids") and isinstance(ev["attending_friend_ids"], list):
                    ev["attending_friend_ids"] = [str(uid) for uid in ev["attending_friend_ids"]]
                result.append(ev)
                ei += 1
                added = True
            elif ai < len(affiliates):
                result.append(dict(affiliates[ai]._mapping))
                ai += 1
                added = True
            if not added:
                break

    return result[int(offset) : int(offset) + int(limit)]

