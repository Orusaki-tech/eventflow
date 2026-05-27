"""Admin console API (Bearer JWT + allowlist): directory reads and business verification writes."""

from __future__ import annotations

import json as _json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from eventflow.adapters import normalize_shared_url
from eventflow.entrypoints.api.business_verified_updates import set_business_verified
from eventflow.entrypoints.api.schemas import (
    AdminBusinessVerifiedPatchRequest,
    AdminConsoleBusinessListResponse,
    AdminConsoleBusinessRow,
    AdminConsoleCommunityEventListResponse,
    AdminConsoleCommunityEventPatchRequest,
    AdminConsoleCommunityEventRow,
    AdminConsoleMeResponse,
    AdminConsolePosterAssetListResponse,
    AdminConsolePosterAssetRow,
    AdminConsolePosterProcessingLogListResponse,
    AdminConsolePosterProcessingLogPatchRequest,
    AdminConsolePosterProcessingLogRow,
    AdminConsoleSharedLinkListingListResponse,
    AdminConsoleSharedLinkListingRow,
    AdminConsoleSummaryResponse,
    AdminConsoleSummaryV3Response,
    AdminSharedLinkListingUpdateRequest,
    BusinessResponse,
)
from eventflow.entrypoints.dependencies import get_session, require_admin_user


_ALLOWED_FILTER_FIELDS = frozenset(["normalized_url ILIKE :pat", "status = :status"])
"""Controlled set of WHERE clause fragments — only these may appear in f-string SQL below."""


def _build_where(filters: list[str]) -> tuple[str, bool]:
    """Join filter fragments with AND.  Returns (sql_snippet, is_safe).

    Each fragment must be in _ALLOWED_FILTER_FIELDS.  Values use :param bindings.
    """
    for f in filters:
        if f not in _ALLOWED_FILTER_FIELDS:
            return ("", False)
    if not filters:
        return ("", True)
    return ("WHERE " + " AND ".join(filters), True)

router = APIRouter(tags=["Admin console"], prefix="/admin/console")


@router.get("/me", response_model=AdminConsoleMeResponse)
async def admin_console_me(user_id: UUID = Depends(require_admin_user)):
    return AdminConsoleMeResponse(ok=True, user_id=user_id)


@router.get("/summary", response_model=AdminConsoleSummaryResponse)
async def admin_console_summary(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    biz = session.execute(text("SELECT COUNT(*) FROM businesses")).scalar_one()
    ce = session.execute(text("SELECT COUNT(*) FROM community_events")).scalar_one()
    pa = session.execute(text("SELECT COUNT(*) FROM poster_assets")).scalar_one()
    dr = session.execute(text("SELECT COUNT(*) FROM event_drafts")).scalar_one()

    users = session.execute(
        text(
            """
            SELECT COUNT(*) FROM (
              SELECT user_id AS uid FROM community_events
              UNION
              SELECT user_id FROM event_drafts
              UNION
              SELECT owner_user_id FROM businesses
            ) u
            """
        )
    ).scalar_one()

    return AdminConsoleSummaryResponse(
        businesses=int(biz),
        community_events=int(ce),
        poster_assets=int(pa),
        event_drafts=int(dr),
        distinct_active_user_ids=int(users),
    )


@router.get("/summary-v3", response_model=AdminConsoleSummaryV3Response)
async def admin_console_summary_v3(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    biz = session.execute(text("SELECT COUNT(*) FROM businesses")).scalar_one()
    ce = session.execute(text("SELECT COUNT(*) FROM community_events")).scalar_one()
    pa = session.execute(text("SELECT COUNT(*) FROM poster_assets")).scalar_one()
    dr = session.execute(text("SELECT COUNT(*) FROM event_drafts")).scalar_one()

    users = session.execute(
        text(
            """
            SELECT COUNT(*) FROM (
              SELECT user_id AS uid FROM community_events
              UNION
              SELECT user_id FROM event_drafts
              UNION
              SELECT owner_user_id FROM businesses
            ) u
            """
        )
    ).scalar_one()

    total_orders = session.execute(text("SELECT COUNT(*) FROM orders WHERE type = 'ticket'")).scalar_one()
    total_revenue = session.execute(text("SELECT COALESCE(SUM(total_minor_units),0) FROM orders WHERE status = 'paid' AND type = 'ticket'")).scalar_one()
    pending_claims = session.execute(text("SELECT COUNT(*) FROM claims WHERE status = 'open'")).scalar_one()
    pending_payouts = session.execute(text("SELECT COUNT(*) FROM business_payouts WHERE status = 'pending'")).scalar_one()
    pending_videos = session.execute(text("SELECT COUNT(*) FROM feed_videos WHERE moderation_status = 'pending'")).scalar_one()

    return AdminConsoleSummaryV3Response(
        businesses=int(biz),
        community_events=int(ce),
        poster_assets=int(pa),
        event_drafts=int(dr),
        distinct_active_user_ids=int(users),
        total_orders=int(total_orders),
        total_revenue_minor=int(total_revenue),
        pending_claims=int(pending_claims),
        pending_payouts=int(pending_payouts),
        pending_videos=int(pending_videos),
    )


@router.get("/businesses", response_model=AdminConsoleBusinessListResponse)
async def admin_console_businesses(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    pat = f"%{q.strip()}%" if q and q.strip() else "%"
    rows = session.execute(
        text(
            """
            SELECT id, name, whatsapp_e164, owner_user_id, verified, created_at,
                   COUNT(*) OVER() AS __total
            FROM businesses
            WHERE name ILIKE :pat
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"pat": pat, "limit": limit, "offset": offset},
    ).fetchall()

    if not rows:
        return AdminConsoleBusinessListResponse(items=[], total=0, limit=limit, offset=offset)

    total = int(rows[0][-1])
    items = [
        AdminConsoleBusinessRow(
            business_id=r[0],
            name=r[1],
            whatsapp_e164=r[2],
            owner_user_id=r[3],
            verified=bool(r[4]),
            created_at=r[5],
        )
        for r in rows
    ]
    return AdminConsoleBusinessListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/community-events", response_model=AdminConsoleCommunityEventListResponse)
async def admin_console_community_events(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    pat = f"%{q.strip()}%" if q and q.strip() else "%"
    rows = session.execute(
        text(
            """
            SELECT e.id, e.user_id, e.title, e.start_time, e.venue, e.source, e.poster_image_uri,
                   (
                     SELECT business_id FROM business_listing_attachments
                     WHERE community_event_id = e.id LIMIT 1
                   ) AS attached_business_id,
                   COUNT(*) OVER() AS __total
            FROM community_events e
            WHERE (e.title ILIKE :pat OR e.venue ILIKE :pat)
            ORDER BY e.start_time DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"pat": pat, "limit": limit, "offset": offset},
    ).fetchall()

    if not rows:
        return AdminConsoleCommunityEventListResponse(items=[], total=0, limit=limit, offset=offset)

    total = int(rows[0][-1])
    items = [
        AdminConsoleCommunityEventRow(
            community_event_id=r[0],
            user_id=r[1],
            title=r[2],
            start_time=r[3],
            venue=r[4],
            source=r[5],
            poster_image_uri=r[6],
            attached_business_id=r[7],
        )
        for r in rows
    ]
    return AdminConsoleCommunityEventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/poster-assets", response_model=AdminConsolePosterAssetListResponse)
async def admin_console_poster_assets(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    rows = session.execute(
        text(
            """
            SELECT p.id, p.content_sha256, p.dhash64, p.created_at, p.content_type,
                   (
                     SELECT COUNT(*) FROM event_sources es WHERE es.poster_asset_id = p.id
                   ) AS event_source_links,
                   (
                     SELECT COUNT(*) FROM event_sources es
                     WHERE es.poster_asset_id = p.id AND es.draft_id IS NOT NULL
                   ) AS draft_links,
                   (
                     SELECT COUNT(*) FROM event_sources es
                     WHERE es.poster_asset_id = p.id AND es.event_id IS NOT NULL
                   ) AS scheduled_event_links,
                   COUNT(*) OVER() AS __total
            FROM poster_assets p
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).fetchall()

    if not rows:
        return AdminConsolePosterAssetListResponse(items=[], total=0, limit=limit, offset=offset)

    total = int(rows[0][-1])
    items = [
        AdminConsolePosterAssetRow(
            poster_asset_id=r[0],
            content_sha256=r[1],
            dhash64=r[2],
            created_at=r[3],
            content_type=r[4],
            event_source_links=int(r[5]),
            draft_links=int(r[6]),
            scheduled_event_links=int(r[7]),
        )
        for r in rows
    ]
    return AdminConsolePosterAssetListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/poster-processing-logs", response_model=AdminConsolePosterProcessingLogListResponse)
async def admin_console_poster_processing_logs(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    status_filter: str | None = Query(default=None, description="Filter by status (success/failed)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    where_clause = ""
    params = {"limit": limit, "offset": offset}
    if status_filter:
        where_clause = "WHERE ppl.status = :status"
        params["status"] = status_filter

    rows = session.execute(
        text(
            f"""
            SELECT ppl.id, ppl.poster_asset_id, ppl.user_id,
                   ppl.extracted_title, ppl.extracted_start_time, ppl.extracted_venue,
                   ppl.confidence_score, ppl.extracted_price, ppl.model_version,
                   ppl.status, ppl.error_message, ppl.created_at,
                   COUNT(*) OVER() AS __total
            FROM poster_processing_logs ppl
            {where_clause}
            ORDER BY ppl.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).fetchall()

    if not rows:
        return AdminConsolePosterProcessingLogListResponse(items=[], total=0, limit=limit, offset=offset)

    total = int(rows[0][-1])
    items = [
        AdminConsolePosterProcessingLogRow(
            id=r[0],
            poster_asset_id=r[1],
            user_id=r[2],
            extracted_title=r[3],
            extracted_start_time=r[4],
            extracted_venue=r[5],
            confidence_score=float(r[6]) if r[6] is not None else None,
            extracted_price=r[7],
            model_version=r[8],
            status=r[9],
            error_message=r[10],
            created_at=r[11],
        )
        for r in rows
    ]
    return AdminConsolePosterProcessingLogListResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch(
    "/businesses/{business_id}/verified",
    status_code=status.HTTP_200_OK,
    response_model=BusinessResponse,
)
async def admin_console_patch_business_verified(
    business_id: UUID,
    body: AdminBusinessVerifiedPatchRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return set_business_verified(session, business_id=business_id, verified=body.verified)


@router.get("/shared-link-listings", response_model=AdminConsoleSharedLinkListingListResponse)
async def admin_console_shared_link_listings(
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=500),
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    filter_frags: list[str] = []
    params: dict = {"limit": limit, "offset": offset}
    if q and q.strip():
        pat = f"%{q.strip()}%"
        filter_frags.append("normalized_url ILIKE :pat")
        params["pat"] = pat
    if status:
        filter_frags.append("status = :status")
        params["status"] = status

    where_sql, safe = _build_where(filter_frags)
    if not safe:
        raise ValueError(f"Unsafe SQL: unexpected filter fragment in {filter_frags}")

    rows = session.execute(
        text(
            f"""
            SELECT normalized_url, source_url_raw, status, cached_payload, created_at, updated_at,
                   COUNT(*) OVER() AS __total
            FROM shared_link_listings
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).fetchall()

    if not rows:
        return AdminConsoleSharedLinkListingListResponse(items=[], total=0, limit=limit, offset=offset)

    total = int(rows[0][-1])
    items = [
        AdminConsoleSharedLinkListingRow(
            normalized_url=r[0],
            source_url_raw=r[1],
            status=r[2],
            cached_payload=r[3],
            created_at=r[4],
            updated_at=r[5],
        )
        for r in rows
    ]
    return AdminConsoleSharedLinkListingListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/shared-link-listing", response_model=AdminConsoleSharedLinkListingRow)
async def admin_console_get_shared_link_listing(
    url: str = Query(..., min_length=4, max_length=4096),
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    norm = normalize_shared_url(url)
    row = session.execute(
        text(
            "SELECT normalized_url, source_url_raw, status, cached_payload, created_at, updated_at "
            "FROM shared_link_listings WHERE normalized_url = :u LIMIT 1"
        ),
        {"u": norm},
    ).first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared link not found")

    return AdminConsoleSharedLinkListingRow(
        normalized_url=row[0],
        source_url_raw=row[1],
        status=row[2],
        cached_payload=row[3],
        created_at=row[4],
        updated_at=row[5],
    )


@router.patch("/community-events/{event_id}", response_model=AdminConsoleCommunityEventRow)
async def admin_console_patch_community_event(
    event_id: UUID,
    body: AdminConsoleCommunityEventPatchRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    existing = session.execute(
        text("SELECT id FROM community_events WHERE id = :id LIMIT 1"),
        {"id": str(event_id)},
    ).first()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community event not found")

    sets = []
    params: dict = {}
    if body.title is not None:
        sets.append("title = :title")
        params["title"] = body.title
    if body.start_time is not None:
        sets.append("start_time = :start_time")
        params["start_time"] = body.start_time
    if body.venue is not None:
        sets.append("venue = :venue")
        params["venue"] = body.venue
    if body.description is not None:
        sets.append("description = :description")
        params["description"] = body.description
    if body.poster_image_uri is not None:
        sets.append("poster_image_uri = :poster_image_uri")
        params["poster_image_uri"] = body.poster_image_uri
    if not sets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    params["id"] = str(event_id)
    session.execute(
        text(f"UPDATE community_events SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    session.commit()

    updated = session.execute(
        text(
            """
            SELECT e.id, e.user_id, e.title, e.start_time, e.venue, e.source, e.poster_image_uri,
                   (SELECT business_id FROM business_listing_attachments WHERE community_event_id = e.id LIMIT 1) AS attached_business_id
            FROM community_events e WHERE e.id = :id
            """
        ),
        {"id": str(event_id)},
    ).first()

    return AdminConsoleCommunityEventRow(
        community_event_id=updated[0],
        user_id=updated[1],
        title=updated[2],
        start_time=updated[3],
        venue=updated[4],
        source=updated[5],
        poster_image_uri=updated[6],
        attached_business_id=updated[7],
    )


@router.patch("/poster-processing-logs/{log_id}", response_model=AdminConsolePosterProcessingLogRow)
async def admin_console_patch_poster_processing_log(
    log_id: UUID,
    body: AdminConsolePosterProcessingLogPatchRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    existing = session.execute(
        text("SELECT id FROM poster_processing_logs WHERE id = :id LIMIT 1"),
        {"id": str(log_id)},
    ).first()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processing log not found")

    sets = []
    params: dict = {}
    if body.extracted_title is not None:
        sets.append("extracted_title = :extracted_title")
        params["extracted_title"] = body.extracted_title
    if body.extracted_start_time is not None:
        sets.append("extracted_start_time = :extracted_start_time")
        params["extracted_start_time"] = body.extracted_start_time
    if body.extracted_venue is not None:
        sets.append("extracted_venue = :extracted_venue")
        params["extracted_venue"] = body.extracted_venue
    if body.confidence_score is not None:
        sets.append("confidence_score = :confidence_score")
        params["confidence_score"] = body.confidence_score
    if body.extracted_price is not None:
        sets.append("extracted_price = :extracted_price")
        params["extracted_price"] = body.extracted_price
    if body.status is not None:
        sets.append("status = :status")
        params["status"] = body.status
    if not sets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    params["id"] = str(log_id)
    session.execute(
        text(f"UPDATE poster_processing_logs SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    session.commit()

    updated = session.execute(
        text(
            """
            SELECT id, poster_asset_id, user_id, extracted_title, extracted_start_time, extracted_venue,
                   confidence_score, extracted_price, model_version, status, error_message, created_at
            FROM poster_processing_logs WHERE id = :id
            """
        ),
        {"id": str(log_id)},
    ).first()

    return AdminConsolePosterProcessingLogRow(
        id=updated[0],
        poster_asset_id=updated[1],
        user_id=updated[2],
        extracted_title=updated[3],
        extracted_start_time=updated[4],
        extracted_venue=updated[5],
        confidence_score=float(updated[6]) if updated[6] is not None else None,
        extracted_price=updated[7],
        model_version=updated[8],
        status=updated[9],
        error_message=updated[10],
        created_at=updated[11],
    )


@router.put("/shared-link-listing", response_model=AdminConsoleSharedLinkListingRow)
async def admin_console_update_shared_link_listing(
    body: AdminSharedLinkListingUpdateRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    norm = normalize_shared_url(body.url)
    row = session.execute(
        text(
            "SELECT normalized_url, source_url_raw, status, cached_payload, created_at, updated_at "
            "FROM shared_link_listings WHERE normalized_url = :u LIMIT 1"
        ),
        {"u": norm},
    ).first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared link not found")

    existing_payload = dict(row[3]) if row[3] else {}
    if body.title is not None:
        existing_payload["title"] = body.title
    if body.venue is not None:
        existing_payload["venue"] = body.venue
    if body.start_time is not None:
        if body.start_time.strip():
            existing_payload["start_time"] = body.start_time.strip()
        else:
            existing_payload.pop("start_time", None)
    if body.price is not None:
        existing_payload["price"] = body.price

    new_status = body.status if body.status else row[2]

    session.execute(
        text(
            """
            UPDATE shared_link_listings
            SET cached_payload = CAST(:payload AS jsonb),
                status = :status,
                updated_at = NOW()
            WHERE normalized_url = :u
            """
        ),
        {"u": norm, "payload": _json.dumps(existing_payload), "status": new_status},
    )
    session.commit()

    updated = session.execute(
        text(
            "SELECT normalized_url, source_url_raw, status, cached_payload, created_at, updated_at "
            "FROM shared_link_listings WHERE normalized_url = :u LIMIT 1"
        ),
        {"u": norm},
    ).first()

    return AdminConsoleSharedLinkListingRow(
        normalized_url=updated[0],
        source_url_raw=updated[1],
        status=updated[2],
        cached_payload=updated[3],
        created_at=updated[4],
        updated_at=updated[5],
    )
