from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from eventflow.adapters.places_client import FakePlacesClient, GooglePlacesClient
from eventflow.domain import commands
from eventflow.domain.exceptions import DraftNotFound, EventNotFound, InvariantViolation, PastEventError, PermissionDenied
from sqlalchemy import text

from eventflow.adapters.gemini import _coerce_optional_price
from eventflow.entrypoints.api.schemas import (
    EtaRequest,
    EtaResponse,
    EventBasicsUpdateRequest,
    EventDetailResponse,
    EventDescriptionUpdateRequest,
    EventPriceUpdateRequest,
    EventVisibilityUpdateRequest,
    EventConfirmedResponse,
    DeviceCalendarPutRequest,
    ReminderAlertRequest,
    SnoozeAlertRequest,
    ResolveVenueRequest,
    ResolveVenueResponse,
    VenueCreateRequest,
    VenueResponse,
)
from eventflow.entrypoints.dependencies import (
    get_calendar_client,
    get_current_user_id,
    get_event_publisher,
    get_session,
    get_uow,
    get_write_scheduler_client,
)
from eventflow.config import get_settings
from eventflow.adapters.repository import Venue
from eventflow.adapters.maps_client import FakeMapsClient, GoogleMapsClient
from eventflow.domain.geo_coordinates import validate_wgs84_coordinates
from eventflow.service_layer import messagebus, views


router = APIRouter(tags=["Events"])


@router.post("/events/confirm/{draft_id}", status_code=status.HTTP_201_CREATED, response_model=EventConfirmedResponse)
async def confirm_event(
    draft_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    publisher=Depends(get_event_publisher),
):
    try:
        event_id = messagebus.handle_with_publisher(
            commands.ConfirmEventDraft(draft_id=draft_id, user_id=user_id),
            uow,
            publisher=publisher,
        )
        return EventConfirmedResponse(event_id=UUID(event_id))
    except DraftNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/events/{event_id}/basics", status_code=status.HTTP_200_OK)
async def update_event_basics(
    event_id: UUID,
    body: EventBasicsUpdateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")
        if evt.cancelled_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a cancelled event")

        if body.title is not None:
            t = body.title.strip()
            if not t:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title cannot be empty")
            evt.title = t
        if body.venue is not None:
            v = body.venue.strip()
            if not v:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="venue cannot be empty")
            evt.venue = v
            evt.raw_venue_text = v
        if body.start_time is not None:
            st = body.start_time
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            evt.start_time = st

        uow.commit()

        return {
            "ok": True,
            "title": evt.title,
            "start_time": evt.start_time,
            "venue": evt.venue,
        }


@router.patch("/events/{event_id}/price", status_code=status.HTTP_200_OK)
async def update_event_price(
    event_id: UUID,
    body: EventPriceUpdateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    normalized = _coerce_optional_price(body.price)
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")
        evt.price = normalized
        uow.commit()
    return {"ok": True, "price": normalized}


@router.patch("/events/{event_id}", status_code=status.HTTP_200_OK)
async def update_event_visibility(
    event_id: UUID,
    body: EventVisibilityUpdateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    if body.visibility not in {"private", "public"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="visibility must be 'private' or 'public'")
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")
        evt.visibility = body.visibility
        uow.commit()
    return {"ok": True, "visibility": body.visibility}


@router.get("/events/{event_id}", status_code=status.HTTP_200_OK, response_model=EventDetailResponse)
async def get_event_detail(
    event_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    session=Depends(get_session),
):
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        allowed = evt.user_id == user_id or evt.visibility == "public"
        if not allowed and session is not None:
            r = session.execute(
                text(
                    """
                    SELECT 1
                    FROM event_shares es
                    JOIN group_memberships gm ON gm.group_id = es.group_id
                    WHERE es.event_id = :event_id
                      AND gm.user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"event_id": str(event_id), "user_id": str(user_id)},
            ).first()
            allowed = r is not None

        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

        uow.commit()
        return EventDetailResponse(
            id=evt.id,
            user_id=evt.user_id,
            title=evt.title,
            start_time=evt.start_time,
            venue=evt.venue,
            price=evt.price,
            visibility=evt.visibility.value,
            description_public=evt.description_public,
            description_close_friends=evt.description_close_friends,
            cancelled_at=evt.cancelled_at,
        )


@router.patch("/events/{event_id}/description", status_code=status.HTTP_200_OK)
async def update_event_description(
    event_id: UUID,
    body: EventDescriptionUpdateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    session=Depends(get_session),
):
    audience = body.audience.strip()
    if audience not in {"public", "close_friends"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="audience must be public|close_friends")
    desc = (body.description or "").strip()
    if desc == "":
        desc = None

    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        # Allow updates by:
        # - owner
        # - any authenticated user for public events
        # - members of groups the event is shared to
        allowed = evt.user_id == user_id or evt.visibility == "public"
        if not allowed:
            if session is None:
                allowed = False
            else:
                r = session.execute(
                    text(
                        """
                        SELECT 1
                        FROM event_shares es
                        JOIN group_memberships gm ON gm.group_id = es.group_id
                        WHERE es.event_id = :event_id
                          AND gm.user_id = :user_id
                        LIMIT 1
                        """
                    ),
                    {"event_id": str(event_id), "user_id": str(user_id)},
                ).first()
                allowed = r is not None

        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

        if audience == "public":
            setattr(evt, "description_public", desc)
        else:
            setattr(evt, "description_close_friends", desc)
        uow.commit()

    return {"ok": True}


@router.post("/events/{event_id}/resolve-venue", status_code=status.HTTP_200_OK, response_model=ResolveVenueResponse)
async def resolve_venue(
    event_id: UUID,
    body: ResolveVenueRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    settings = get_settings()
    if settings.google_maps_api_key:
        places = GooglePlacesClient(api_key=settings.google_maps_api_key)
    else:
        places = FakePlacesClient()

    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")

        candidates = places.text_search(query=body.query, near_lat=body.near_lat, near_lng=body.near_lng)
        if not candidates:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching venue found")
        best = candidates[0]
        try:
            validate_wgs84_coordinates(best.lat, best.lng)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Venue search returned unusable coordinates; try manual pin or another query. ({exc})",
            ) from exc

        now = datetime.now(timezone.utc)
        v = Venue(
            name=best.name,
            address=best.address,
            lat=best.lat,
            lng=best.lng,
            place_id=best.place_id,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        saved = uow.venues.upsert_by_place_id(venue=v)

        # Attach venue to event; keep venue text as display name.
        evt.venue_id = saved.id
        evt.venue = saved.name

        uow.commit()

        return ResolveVenueResponse(
            venue=VenueResponse(
                id=saved.id,
                name=saved.name,
                address=saved.address,
                lat=saved.lat,
                lng=saved.lng,
                place_id=saved.place_id,
            )
        )


@router.post("/events/{event_id}/venue/manual", status_code=status.HTTP_200_OK, response_model=ResolveVenueResponse)
async def attach_manual_venue(
    event_id: UUID,
    body: VenueCreateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    """Create a venue from explicit coordinates (no Places match required) and attach it to the event."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Venue name is required")

    now = datetime.now(timezone.utc)
    v = Venue(
        name=name,
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
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")

        saved = uow.venues.upsert_by_place_id(venue=v) if v.place_id else uow.venues.add(v)
        evt.venue_id = saved.id
        evt.venue = saved.name
        uow.commit()

        return ResolveVenueResponse(
            venue=VenueResponse(
                id=saved.id,
                name=saved.name,
                address=saved.address,
                lat=saved.lat,
                lng=saved.lng,
                place_id=saved.place_id,
            )
        )


@router.post("/events/{event_id}/eta", status_code=status.HTTP_200_OK, response_model=EtaResponse)
async def event_eta(
    event_id: UUID,
    body: EtaRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    settings = get_settings()
    if settings.google_maps_api_key:
        maps = GoogleMapsClient(api_key=settings.google_maps_api_key)
    else:
        maps = FakeMapsClient()

    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        # Allow ETA for events visible to the user (owner or shared/public) later; for now owner-only.
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")

        if not getattr(evt, "venue_id", None):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Venue not resolved for this event")
        venue = uow.venues.get(venue_id=evt.venue_id)
        if venue is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Venue not resolved for this event")

        try:
            validate_wgs84_coordinates(venue.lat, venue.lng)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stored venue has invalid coordinates; re-save the venue pin. ({exc})",
            ) from exc

        now = datetime.now(timezone.utc)
        dist_m, dur_s, dur_traffic_s = maps.estimate_distance_and_duration_seconds(
            origin_lat=body.lat,
            origin_lng=body.lng,
            destination_lat=venue.lat,
            destination_lng=venue.lng,
            depart_at=now,
        )
        uow.commit()

    return EtaResponse(distance_meters=dist_m, duration_seconds=dur_s, duration_in_traffic_seconds=dur_traffic_s)


@router.post("/events/cancel/{event_id}", status_code=status.HTTP_202_ACCEPTED)
async def cancel_event(
    event_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    publisher=Depends(get_event_publisher),
):
    try:
        messagebus.handle_with_publisher(
            commands.CancelEvent(event_id=event_id, user_id=user_id),
            uow,
            publisher=publisher,
        )
        return {"status": "cancelled"}
    except EventNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/events/upcoming", status_code=status.HTTP_200_OK)
async def upcoming_events(
    days_ahead: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
    uow=Depends(get_uow),
):
    if session is None:
        with uow:
            rows = views.get_upcoming_events(
                user_id=user_id,
                session=None,
                events_repo=uow.events,
                days_ahead=days_ahead,
                limit=limit,
            )
            uow.commit()
            return rows
    return views.get_upcoming_events(user_id=user_id, session=session, days_ahead=days_ahead, limit=limit)


@router.get("/events/today", status_code=status.HTTP_200_OK)
async def today_events(
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840, description="Client timezone offset in minutes (e.g. +180)."),
    limit: int = Query(default=200, ge=1, le=500),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    return views.list_today_events(user_id=user_id, session=session, tz_offset_minutes=tz_offset_minutes, limit=limit)


@router.get("/events/{event_id}/ics", status_code=status.HTTP_200_OK)
async def download_ics(
    event_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    calendar_client=Depends(get_calendar_client),
):
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")

        ics = calendar_client.build_ics(event=evt)
        uow.commit()

    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="eventflow-{event_id}.ics"'},
    )


@router.post("/events/{event_id}/alerts/reminder", status_code=status.HTTP_202_ACCEPTED)
async def schedule_reminder_alert(
    event_id: UUID,
    body: ReminderAlertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    publisher=Depends(get_event_publisher),
):
    try:
        messagebus.handle_with_publisher(
            commands.ScheduleReminderAlert(event_id=event_id, user_id=user_id, minutes_before=body.minutes_before),
            uow,
            publisher=publisher,
        )
        return {"status": "scheduled"}
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PastEventError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvariantViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/events/{event_id}/alerts/snooze", status_code=status.HTTP_202_ACCEPTED)
async def snooze_leave_alert(
    event_id: UUID,
    body: SnoozeAlertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    scheduler=Depends(get_write_scheduler_client),
):
    """Schedule a one-off reminder push (replaces prior snooze job for this event)."""
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")
        if evt.cancelled_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event is cancelled")
        now = datetime.now(timezone.utc)
        if evt.start_time <= now:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event already started or ended")
        run_at = now + timedelta(minutes=int(body.minutes))
        scheduler.schedule_push_due(
            job_key=f"user_snooze:{event_id}",
            user_id=str(evt.user_id),
            run_at=run_at,
            title="EventFlow",
            body=f"Reminder: {evt.title}",
            event_id=str(event_id),
            action="snooze",
        )
        uow.commit()
    return {"status": "scheduled", "fire_at": run_at.isoformat()}


@router.get("/events/{event_id}/device-calendar", status_code=status.HTTP_200_OK)
async def get_device_calendar_link(
    event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    row = session.execute(
        text(
            """
            SELECT external_event_id, calendar_id
            FROM device_calendar_links
            WHERE user_id = :uid AND event_id = :eid
            LIMIT 1
            """
        ),
        {"uid": str(user_id), "eid": str(event_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No device calendar mapping")
    return {"external_event_id": row[0], "calendar_id": row[1]}


@router.put("/events/{event_id}/device-calendar", status_code=status.HTTP_200_OK)
async def put_device_calendar_link(
    event_id: UUID,
    body: DeviceCalendarPutRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
    uow=Depends(get_uow),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    with uow:
        evt = uow.events.get(event_id)
        if evt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your event")
        uow.commit()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO device_calendar_links (user_id, event_id, external_event_id, calendar_id, updated_at)
            VALUES (:uid, :eid, :ext, :cal, :now)
            ON CONFLICT (user_id, event_id) DO UPDATE SET
              external_event_id = EXCLUDED.external_event_id,
              calendar_id = EXCLUDED.calendar_id,
              updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "uid": str(user_id),
            "eid": str(event_id),
            "ext": body.external_event_id.strip(),
            "cal": body.calendar_id.strip() if body.calendar_id else None,
            "now": now,
        },
    )
    session.commit()
    return {"ok": True}


@router.delete("/events/{event_id}/device-calendar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_calendar_link(
    event_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    session.execute(
        text(
            """
            DELETE FROM device_calendar_links
            WHERE user_id = :uid AND event_id = :eid
            """
        ),
        {"uid": str(user_id), "eid": str(event_id)},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

