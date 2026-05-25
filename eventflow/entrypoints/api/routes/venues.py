from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eventflow.adapters.repository import Venue
from eventflow.entrypoints.api.schemas import VenueCreateRequest, VenueResponse, VenueUpdateRequest
from eventflow.entrypoints.dependencies import (
    get_current_user_id,
    get_session,
    get_uow,
    require_admin_user,
)


router = APIRouter(tags=["Venues"])


@router.get("/venues/search", response_model=list[VenueResponse], status_code=status.HTTP_200_OK)
async def search_venues(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    with uow:
        rows = uow.venues.search(q=q, limit=limit)
        uow.commit()
    return [
        VenueResponse(id=v.id, name=v.name, address=v.address, lat=v.lat, lng=v.lng, place_id=v.place_id) for v in rows
    ]


@router.post("/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    body: VenueCreateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    now = datetime.now(timezone.utc)
    v = Venue(
        name=body.name.strip(),
        address=body.address.strip() if body.address else None,
        lat=float(body.lat),
        lng=float(body.lng),
        place_id=body.place_id.strip() if body.place_id else None,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    with uow:
        saved = uow.venues.upsert_by_place_id(venue=v) if v.place_id else uow.venues.add(v)
        uow.commit()
        return VenueResponse(id=saved.id, name=saved.name, address=saved.address, lat=saved.lat, lng=saved.lng, place_id=saved.place_id)


@router.patch("/venues/{venue_id}", response_model=VenueResponse, status_code=status.HTTP_200_OK)
async def update_venue(
    venue_id: UUID,
    body: VenueUpdateRequest,
    _admin: UUID = Depends(require_admin_user),
    session=Depends(get_session),
    uow=Depends(get_uow),
):
    user_id = _admin

    with uow:
        v = uow.venues.get(venue_id=venue_id)
        if v is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
        if body.name is not None:
            v.name = body.name.strip()
        if body.address is not None:
            v.address = body.address.strip() or None
        if body.lat is not None:
            v.lat = float(body.lat)
        if body.lng is not None:
            v.lng = float(body.lng)
        v.updated_by_user_id = user_id
        v.updated_at = datetime.now(timezone.utc)
        uow.commit()
        return VenueResponse(id=v.id, name=v.name, address=v.address, lat=v.lat, lng=v.lng, place_id=v.place_id)

