from __future__ import annotations

import uuid as _uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from eventflow.adapters.embeddings_client import DeterministicEmbeddingsClient
from eventflow.adapters.share_parse_cache import normalize_shared_url
from eventflow.domain import commands
from eventflow.entrypoints.api.schemas import (
    BusinessProfileListingRow,
    BusinessProfileResponse,
    CommunityEventMineDetailResponse,
    CommunityEventMineListRowResponse,
    CommunityEventResponse,
    CommunityEventUpsertRequest,
    SharedLinkListingStatusResponse,
)
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, get_uow
from eventflow.service_layer import messagebus, views


router = APIRouter(tags=["Discovery"])


@router.get(
    "/discovery/shared-link-listing",
    status_code=status.HTTP_200_OK,
    response_model=SharedLinkListingStatusResponse,
)
async def shared_link_listing_status(url: str = Query(min_length=8), session=Depends(get_session)):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    norm = normalize_shared_url(url)
    row = session.execute(
        text("SELECT status FROM shared_link_listings WHERE normalized_url = :u LIMIT 1"),
        {"u": norm},
    ).first()
    return SharedLinkListingStatusResponse(normalized_url=norm, status=None if row is None else str(row[0]))


def _vector_literal(vec: list[float]) -> str:
    # pgvector accepts '[1,2,3]' syntax.
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


@router.get("/discovery/feed", status_code=status.HTTP_200_OK)
async def discovery_feed(
    limit: int = Query(default=50, ge=1, le=200),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    return views.list_community_events(session=session, user_id=user_id, limit=limit)


@router.get("/discover/unified-feed", status_code=status.HTTP_200_OK)
async def unified_feed(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    return views.list_unified_feed(
        session=session,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/discovery/search", status_code=status.HTTP_200_OK)
async def discovery_search(
    q: str = Query(min_length=1, max_length=2000),
    limit: int = Query(default=20, ge=1, le=50),
    session=Depends(get_session),
):
    if session is None:
        return []
    embedder = DeterministicEmbeddingsClient(dim=64)
    qvec = _vector_literal(embedder.embed_text(text=q))
    return views.search_community_events(session=session, query_vector=qvec, limit=limit)


@router.get(
    "/discovery/community-events/mine",
    status_code=status.HTTP_200_OK,
    response_model=list[CommunityEventMineListRowResponse],
)
async def discovery_my_community_events(
    limit: int = Query(default=50, ge=1, le=200),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    rows = views.list_my_community_events(session=session, user_id=user_id, limit=limit)
    return [CommunityEventMineListRowResponse.model_validate(r) for r in rows]


@router.get(
    "/discovery/community-events/{community_event_id}",
    status_code=status.HTTP_200_OK,
    response_model=CommunityEventMineDetailResponse,
)
async def discovery_my_community_event_detail(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    row = views.get_my_community_event_detail(
        session=session, user_id=user_id, community_event_id=community_event_id
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return CommunityEventMineDetailResponse.model_validate(row)


@router.post("/discovery/community-events", status_code=status.HTTP_201_CREATED, response_model=CommunityEventResponse)
async def upsert_community_event(
    body: CommunityEventUpsertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    result = messagebus.handle(
        commands.UpsertCommunityEvent(
            user_id=user_id,
            source=body.source,
            title=body.title,
            start_time=body.start_time,
            venue=body.venue,
            description=body.description,
            poster_image_uri=(body.poster_image_uri.strip() if body.poster_image_uri else None),
        ),
        uow,
    )
    return result


@router.get("/discovery/business/{business_id}", response_model=BusinessProfileResponse)
async def discovery_business_profile(
    business_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    biz = session.execute(
        text(
            "SELECT id, name, description, logo_url, website, contact_email, whatsapp_e164, verified "
            "FROM businesses WHERE id = :id LIMIT 1"
        ),
        {"id": str(business_id)},
    ).first()
    if biz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    follower_count_row = session.execute(
        text("SELECT COUNT(*) FROM business_follows WHERE business_id = :id"),
        {"id": str(business_id)},
    ).scalar()

    listings = session.execute(
        text(
            """
            SELECT e.id, e.title, e.start_time, e.venue, e.poster_image_uri,
                   v.hero_video_uri, b.whatsapp_e164
            FROM community_events e
            INNER JOIN business_listing_attachments bl ON bl.community_event_id = e.id
            LEFT JOIN businesses b ON b.id = bl.business_id
            LEFT JOIN LATERAL (
              SELECT ev.storage_uri AS hero_video_uri
              FROM event_videos ev
              WHERE ev.community_event_id = e.id AND ev.moderation_status = 'approved'
              ORDER BY ev.created_at ASC
              LIMIT 1
            ) v ON TRUE
            WHERE bl.business_id = :id AND e.start_time > NOW()
            ORDER BY e.start_time ASC
            LIMIT :lim
            """
        ),
        {"id": str(business_id), "lim": limit},
    ).fetchall()

    listing_rows = [
        BusinessProfileListingRow(
            community_event_id=r[0],
            title=r[1],
            start_time=r[2],
            venue=r[3],
            poster_image_uri=r[4],
            hero_video_uri=r[5],
            whatsapp_e164=r[6],
        )
        for r in listings
    ]

    return BusinessProfileResponse(
        business_id=biz[0],
        name=biz[1],
        description=biz[2],
        logo_url=biz[3],
        website=biz[4],
        contact_email=biz[5],
        whatsapp_e164=biz[6],
        verified=biz[7],
        follower_count=follower_count_row or 0,
        listing_count=len(listing_rows),
        listings=listing_rows,
    )


@router.get("/discovery/community-events/saved", status_code=status.HTTP_200_OK)
async def list_saved_community_events(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text("""
            SELECT ce.id, ce.title, ce.start_time, ce.venue, ce.description, ce.poster_image_uri,
                   ce.business_id, ce.whatsapp_e164, ce.hero_video_uri, ce.user_id as organizer_user_id
            FROM community_events ce
            INNER JOIN listing_analytics_events lae ON lae.community_event_id = ce.id
            WHERE lae.user_id = :uid AND lae.metric_type = 'save'
            ORDER BY ce.start_time ASC
        """),
        {"uid": str(user_id)},
    ).fetchall()
    return [
        {
            "item_id": str(r[0]),
            "kind": "event",
            "title": r[1],
            "start_time": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            "venue": r[3],
            "description": r[4],
            "poster_image_uri": r[5],
            "business_id": str(r[6]) if r[6] else None,
            "whatsapp_e164": r[7],
            "hero_video_uri": r[8],
            "organizer_user_id": str(r[9]),
            "attending_friends_count": 0,
            "attending_friend_ids": [],
            "price_minor_units": None,
        }
        for r in rows
    ]


@router.get("/discovery/community-events/{community_event_id}", status_code=status.HTTP_200_OK)
async def get_community_event_detail(
    community_event_id: UUID,
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    ce = session.execute(
        text("""
            SELECT ce.id, ce.title, ce.start_time, ce.venue, ce.description,
                   ce.poster_image_uri, ce.hero_video_uri, ce.whatsapp_e164, ce.user_id, ce.business_id,
                   MIN(tt.price_minor_units) AS min_price
            FROM community_events ce
            LEFT JOIN ticket_types tt ON tt.community_event_id = ce.id
            WHERE ce.id = :id
            GROUP BY ce.id
            LIMIT 1
        """),
        {"id": str(community_event_id)},
    ).first()
    if ce is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return {
        "item_id": str(ce[0]),
        "kind": "event",
        "title": ce[1],
        "start_time": ce[2].isoformat() if hasattr(ce[2], "isoformat") else str(ce[2]),
        "venue": ce[3],
        "description": ce[4],
        "poster_image_uri": ce[5],
        "hero_video_uri": ce[6],
        "whatsapp_e164": ce[7],
        "organizer_user_id": str(ce[8]),
        "business_id": str(ce[9]) if ce[9] else None,
        "attending_friends_count": 0,
        "attending_friend_ids": [],
        "price_minor_units": ce[10] if ce[10] is not None else None,
    }


@router.post("/discovery/community-events/{community_event_id}/save-to-calendar", status_code=status.HTTP_201_CREATED)
async def save_community_event_to_calendar(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    ce = session.execute(
        text("SELECT id, title, start_time, venue, description FROM community_events WHERE id = :id LIMIT 1"),
        {"id": str(community_event_id)},
    ).first()
    if ce is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event_id = _uuid.uuid4()
    session.execute(
        text("""
            INSERT INTO scheduled_events (id, user_id, title, start_time, venue, raw_venue_text, description_public, visibility)
            VALUES (:id, :uid, :title, :st, :venue, :venue, :desc, 'private')
        """),
        {"id": str(event_id), "uid": str(user_id), "title": ce.title, "st": ce.start_time, "venue": ce.venue, "desc": ce.description or ""},
    )
    session.execute(
        text("INSERT INTO listing_analytics_events (id, community_event_id, user_id, metric_type, meta, created_at) VALUES (gen_random_uuid(), :ce, :uid, 'save', '{}'::jsonb, NOW()) ON CONFLICT DO NOTHING"),
        {"ce": str(community_event_id), "uid": str(user_id)},
    )
    session.commit()
    return {"scheduled_event_id": str(event_id), "ok": True}


@router.get("/discovery/community-events/{community_event_id}/ics", response_class=PlainTextResponse)
async def community_event_ics(
    community_event_id: UUID,
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    ce = session.execute(
        text("SELECT id, title, start_time, venue, description FROM community_events WHERE id = :id LIMIT 1"),
        {"id": str(community_event_id)},
    ).first()
    if ce is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    from eventflow.adapters.calendar_client import build_ics_for_community_event
    ics = build_ics_for_community_event(event_id=str(ce.id), title=ce.title, start_time=ce.start_time, venue=ce.venue)
    return PlainTextResponse(content=ics, media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=\"event-{ce.id}.ics\""})


@router.post("/discovery/community-events/{community_event_id}/rsvp", status_code=status.HTTP_200_OK)
async def rsvp_community_event(
    community_event_id: UUID,
    body: dict,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    status_val = body.get("status", "going")
    if status_val not in ("going", "maybe", "not_going"):
        raise HTTPException(status_code=400, detail="Invalid RSVP status")
    existing = session.execute(
        text("SELECT id FROM listing_analytics_events WHERE community_event_id = :ce AND user_id = :uid AND metric_type = 'rsvp' LIMIT 1"),
        {"ce": str(community_event_id), "uid": str(user_id)},
    ).first()
    meta = {"rsvp_status": status_val}
    if existing:
        session.execute(
            text("UPDATE listing_analytics_events SET meta = :meta WHERE id = :id"),
            {"meta": meta, "id": existing[0]},
        )
    else:
        session.execute(
            text("INSERT INTO listing_analytics_events (id, community_event_id, user_id, metric_type, meta, created_at) VALUES (gen_random_uuid(), :ce, :uid, 'rsvp', :meta, NOW())"),
            {"ce": str(community_event_id), "uid": str(user_id), "meta": meta},
        )
    session.commit()
    return {"status": status_val, "ok": True}


@router.get("/discovery/community-events/{community_event_id}/rsvp", status_code=status.HTTP_200_OK)
async def get_rsvp_status(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return {"status": None}
    row = session.execute(
        text("SELECT meta FROM listing_analytics_events WHERE community_event_id = :ce AND user_id = :uid AND metric_type = 'rsvp' LIMIT 1"),
        {"ce": str(community_event_id), "uid": str(user_id)},
    ).first()
    status_val = (row["meta"] or {}).get("rsvp_status") if row else None
    return {"status": status_val}

