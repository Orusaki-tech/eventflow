"""Admin console API (Bearer JWT + allowlist): directory reads and business verification writes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from eventflow.entrypoints.api.business_verified_updates import set_business_verified
from eventflow.entrypoints.api.schemas import (
    AdminBusinessVerifiedPatchRequest,
    AdminConsoleBusinessListResponse,
    AdminConsoleBusinessRow,
    AdminConsoleCommunityEventListResponse,
    AdminConsoleCommunityEventRow,
    AdminConsoleMeResponse,
    AdminConsolePosterAssetListResponse,
    AdminConsolePosterAssetRow,
    AdminConsoleSummaryResponse,
    BusinessResponse,
)
from eventflow.entrypoints.dependencies import get_session, require_admin_user

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
