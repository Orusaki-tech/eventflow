"""Additional product surfaces from EventFlow v2.0 gap plan (feed, business shell, analytics, billing stub)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Json
from sqlalchemy import text
from starlette.responses import Response

from eventflow.adapters.share_parse_cache import normalize_shared_url
from eventflow.entrypoints.api.business_verified_updates import set_business_verified
from eventflow.entrypoints.api.routes.share import upsert_shared_link_listing_approved
from eventflow.entrypoints.api.schemas import (
    AdminBusinessVerifiedPatchRequest,
    BillingCheckoutStubResponse,
    BusinessCreateRequest,
    BusinessPatchRequest,
    BusinessResponse,
    CarouselSlide,
    EventVideoModerationPatchRequest,
    FollowingRow,
    ListingAnalyticsRequest,
    ListingBusinessAttachRequest,
    ListingCarouselResponse,
    ListingShareAliasPutRequest,
)
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, require_admin_api_token
from eventflow.service_layer import views

router = APIRouter(tags=["Product"])


def _assert_community_listing_owner(session, community_event_id: UUID, user_id: UUID) -> None:
    row = session.execute(
        text("SELECT user_id FROM community_events WHERE id = :id LIMIT 1"),
        {"id": str(community_event_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail="Not your listing")


def _assert_business_owner(session, business_id: UUID, user_id: UUID) -> None:
    row = session.execute(
        text("SELECT owner_user_id FROM businesses WHERE id = :id LIMIT 1"),
        {"id": str(business_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Business not found")
    if row[0] != user_id:
        raise HTTPException(status_code=403, detail="Not your business")


@router.get("/feed/home", status_code=status.HTTP_200_OK)
async def feed_home(
    limit: int = Query(default=50, ge=1, le=200),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    return views.list_feed_home(user_id=user_id, session=session, limit=limit)


@router.get("/businesses", status_code=status.HTTP_200_OK, response_model=list[BusinessResponse])
async def list_my_businesses(user_id=Depends(get_current_user_id), session=Depends(get_session)):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    rows = session.execute(
        text(
            """
            SELECT id, name, whatsapp_e164, verified
            FROM businesses
            WHERE owner_user_id = :uid
            ORDER BY created_at DESC
            """
        ),
        {"uid": user_id},
    )
    return [
        BusinessResponse(business_id=r[0], name=r[1], whatsapp_e164=r[2], verified=bool(r[3]))
        for r in rows
    ]


@router.post("/businesses", status_code=status.HTTP_201_CREATED, response_model=BusinessResponse)
async def create_business(
    body: BusinessCreateRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    bid = uuid4()
    now = datetime.now(timezone.utc)
    w = body.whatsapp_e164.strip() if body.whatsapp_e164 else None
    session.execute(
        text(
            """
            INSERT INTO businesses (id, name, whatsapp_e164, owner_user_id, verified, created_at)
            VALUES (:id, :name, :wa, :owner, false, :now)
            """
        ),
        {"id": bid, "name": body.name.strip(), "wa": w, "owner": user_id, "now": now},
    )
    session.commit()
    return BusinessResponse(business_id=bid, name=body.name.strip(), whatsapp_e164=w, verified=False)


@router.patch("/businesses/{business_id}", status_code=status.HTTP_200_OK, response_model=BusinessResponse)
async def patch_business(
    business_id: UUID,
    body: BusinessPatchRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_business_owner(session, business_id, user_id)
    sets: list[str] = []
    params: dict = {"id": str(business_id)}
    if body.name is not None:
        sets.append("name = :name")
        params["name"] = body.name.strip()
    if body.whatsapp_e164 is not None:
        wa = body.whatsapp_e164.strip()
        sets.append("whatsapp_e164 = :wa")
        params["wa"] = wa if wa else None
    if not sets:
        row = session.execute(
            text("SELECT id, name, whatsapp_e164, verified FROM businesses WHERE id = :id LIMIT 1"),
            {"id": str(business_id)},
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Business not found")
        return BusinessResponse(business_id=row[0], name=row[1], whatsapp_e164=row[2], verified=bool(row[3]))
    session.execute(text(f"UPDATE businesses SET {', '.join(sets)} WHERE id = :id"), params)
    session.commit()
    row = session.execute(
        text("SELECT id, name, whatsapp_e164, verified FROM businesses WHERE id = :id LIMIT 1"),
        {"id": str(business_id)},
    ).first()
    assert row is not None
    return BusinessResponse(business_id=row[0], name=row[1], whatsapp_e164=row[2], verified=bool(row[3]))


@router.patch(
    "/admin/businesses/{business_id}/verified",
    status_code=status.HTTP_200_OK,
    response_model=BusinessResponse,
)
async def admin_patch_business_verified(
    business_id: UUID,
    body: AdminBusinessVerifiedPatchRequest,
    session=Depends(get_session),
    _: None = Depends(require_admin_api_token),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return set_business_verified(session, business_id=business_id, verified=body.verified)


@router.get("/businesses/{business_id}", status_code=status.HTTP_200_OK, response_model=BusinessResponse)
async def get_business(business_id: UUID, session=Depends(get_session)):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text(
            """
            SELECT id, name, whatsapp_e164, verified
            FROM businesses WHERE id = :id LIMIT 1
            """
        ),
        {"id": str(business_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(
        business_id=row[0],
        name=row[1],
        whatsapp_e164=row[2],
        verified=bool(row[3]),
    )


@router.put(
    "/listings/{community_event_id}/business",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_listing_business_attachment(
    community_event_id: UUID,
    body: ListingBusinessAttachRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_community_listing_owner(session, community_event_id, user_id)
    _assert_business_owner(session, body.business_id, user_id)
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO business_listing_attachments (community_event_id, business_id, created_at)
            VALUES (:ce, :biz, :now)
            ON CONFLICT (community_event_id) DO UPDATE SET
              business_id = EXCLUDED.business_id,
              created_at = EXCLUDED.created_at
            """
        ),
        {"ce": str(community_event_id), "biz": str(body.business_id), "now": now},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/listings/{community_event_id}/business",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_listing_business_attachment(
    community_event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_community_listing_owner(session, community_event_id, user_id)
    session.execute(
        text("DELETE FROM business_listing_attachments WHERE community_event_id = :ce"),
        {"ce": str(community_event_id)},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/listings/{community_event_id}/share-alias",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def put_listing_share_alias(
    community_event_id: UUID,
    body: ListingShareAliasPutRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_community_listing_owner(session, community_event_id, user_id)
    norm = normalize_shared_url(body.url.strip())
    row_ce = session.execute(
        text(
            """
            SELECT title, venue, start_time
            FROM community_events WHERE id = :id LIMIT 1
            """
        ),
        {"id": str(community_event_id)},
    ).first()
    if row_ce is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    title, venue, start_time = row_ce[0], row_ce[1], row_ce[2]
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO community_event_share_aliases (normalized_url, community_event_id, created_at, updated_at)
            VALUES (:u, :ce, :now, :now)
            ON CONFLICT (normalized_url) DO UPDATE SET
              community_event_id = EXCLUDED.community_event_id,
              updated_at = EXCLUDED.updated_at
            """
        ),
        {"u": norm, "ce": str(community_event_id), "now": now},
    )
    draft_like = {
        "title": title,
        "venue": venue,
        "confidence_score": 1.0,
        "start_time": start_time,
        "price": None,
    }
    try:
        upsert_shared_link_listing_approved(session, body.url.strip(), draft_like)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/listing-analytics", status_code=status.HTTP_204_NO_CONTENT)
async def listing_analytics(
    body: ListingAnalyticsRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    aid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO listing_analytics_events
              (id, community_event_id, business_id, user_id, metric_type, meta, created_at)
            VALUES (:id, :ce, :biz, :uid, :mt, :meta, :now)
            """
        ),
        {
            "id": aid,
            "ce": str(body.community_event_id) if body.community_event_id else None,
            "biz": str(body.business_id) if body.business_id else None,
            "uid": user_id,
            "mt": body.metric_type,
            "meta": Json(body.meta or {}),
            "now": now,
        },
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/follows", status_code=status.HTTP_200_OK, response_model=list[FollowingRow])
async def list_follows(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT following_user_id, created_at
            FROM follows
            WHERE follower_user_id = :uid
            ORDER BY created_at DESC
            """
        ),
        {"uid": str(user_id)},
    )
    return [FollowingRow(following_user_id=r[0], created_at=r[1]) for r in rows]


@router.post("/follows/{target_user_id}", status_code=status.HTTP_201_CREATED)
async def follow_user(
    target_user_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if target_user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO follows (follower_user_id, following_user_id, created_at)
            VALUES (:a, :b, :now)
            ON CONFLICT (follower_user_id, following_user_id) DO NOTHING
            """
        ),
        {"a": user_id, "b": target_user_id, "now": now},
    )
    session.commit()
    return {"ok": True}


@router.delete("/follows/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(target_user_id: UUID, user_id=Depends(get_current_user_id), session=Depends(get_session)):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    session.execute(
        text(
            """
            DELETE FROM follows
            WHERE follower_user_id = :a AND following_user_id = :b
            """
        ),
        {"a": user_id, "b": target_user_id},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/listings/{community_event_id}/carousel",
    status_code=status.HTTP_200_OK,
    response_model=ListingCarouselResponse,
)
async def listing_carousel(community_event_id: UUID, session=Depends(get_session)):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    row = session.execute(
        text(
            """
            SELECT title, venue, poster_image_uri FROM community_events WHERE id = :id LIMIT 1
            """
        ),
        {"id": str(community_event_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    poster_uri = row[2]
    img = str(poster_uri).strip() if poster_uri else None
    slides: list[CarouselSlide] = [
        CarouselSlide(
            kind="poster",
            title=str(row[0]),
            subtitle=str(row[1]),
            uri=None,
            image_uri=img if img else None,
        ),
    ]
    videos = session.execute(
        text(
            """
            SELECT storage_uri FROM event_videos
            WHERE community_event_id = :id AND moderation_status = 'approved'
            ORDER BY created_at ASC
            """
        ),
        {"id": str(community_event_id)},
    )
    for vr in videos:
        slides.append(CarouselSlide(kind="video", title=None, subtitle=None, uri=str(vr[0]), image_uri=None))
    return ListingCarouselResponse(community_event_id=community_event_id, slides=slides)


@router.post("/event-videos", status_code=status.HTTP_201_CREATED)
async def register_event_video(
    community_event_id: UUID = Query(...),
    storage_uri: str = Query(..., min_length=8, max_length=4096),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    """Register a video URI for moderation (portal/upload pipeline)."""
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _assert_community_listing_owner(session, community_event_id, user_id)
    vid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO event_videos (id, community_event_id, storage_uri, moderation_status, created_at)
            VALUES (:id, :ce, :uri, 'pending', :now)
            """
        ),
        {"id": vid, "ce": str(community_event_id), "uri": storage_uri.strip(), "now": now},
    )
    session.commit()
    return {"video_id": str(vid), "moderation_status": "pending"}


@router.patch("/admin/event-videos/{video_id}/moderation", status_code=status.HTTP_200_OK)
async def admin_patch_event_video_moderation(
    video_id: UUID,
    body: EventVideoModerationPatchRequest,
    session=Depends(get_session),
    _: None = Depends(require_admin_api_token),
):
    if session is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    res = session.execute(
        text(
            """
            UPDATE event_videos
            SET moderation_status = :st
            WHERE id = :id
            """
        ),
        {"st": body.moderation_status, "id": str(video_id)},
    )
    session.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    row = session.execute(
        text("SELECT moderation_status FROM event_videos WHERE id = :id LIMIT 1"),
        {"id": str(video_id)},
    ).first()
    return {"video_id": str(video_id), "moderation_status": row[0] if row else body.moderation_status}


@router.post("/billing/checkout-session", status_code=status.HTTP_200_OK, response_model=BillingCheckoutStubResponse)
async def billing_checkout_stub(provider: str = Query(default="stripe", pattern="^(stripe|mpesa_stub)$")):
    return BillingCheckoutStubResponse(
        checkout_url=f"https://checkout.example.com/eventflow/{provider}/placeholder-session",
        provider="stripe" if provider == "stripe" else "mpesa_stub",
    )
