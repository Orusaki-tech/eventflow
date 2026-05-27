from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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

