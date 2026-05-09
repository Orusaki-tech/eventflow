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
                     ELSE e.description_close_friends
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
                ELSE e.description_close_friends
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

    where_confirmed = ""
    if status == "pending":
        where_confirmed = "AND d.confirmed_at IS NULL"
    elif status == "confirmed":
        where_confirmed = "AND d.confirmed_at IS NOT NULL"

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


def list_community_events(*, session: Any, limit: int = 50) -> List[dict]:
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


def list_feed_home(*, user_id: UUID, session: Any | None, limit: int = 50) -> List[dict]:
    """Compose discovery feed: followed organisers plus trending/sponsored community listings."""
    if session is None:
        return []
    merged: dict[str, dict] = {}
    followed = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.user_id, e.sponsored_rank,
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
        {"uid": str(user_id), "lim": int(limit)},
    )
    for r in followed:
        merged[str(r.id)] = dict(r._mapping)

    trending = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.user_id, e.sponsored_rank,
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
            ORDER BY e.sponsored_rank DESC, e.start_time ASC
            LIMIT :lim
            """
        ),
        {"lim": int(limit)},
    )
    for r in trending:
        k = str(r.id)
        if k not in merged:
            merged[k] = dict(r._mapping)

    items = list(merged.values())
    items.sort(key=lambda row: (-int(row.get("sponsored_rank") or 0), row.get("start_time")))
    return items[: int(limit)]

