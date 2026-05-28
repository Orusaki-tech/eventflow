from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from eventflow.domain.model import UserLocation
from eventflow.adapters.repository import DevicePushToken
from eventflow.entrypoints.api.schemas import (
    BudgetSummaryResponse,
    PushTokenResponse,
    PushTokenUpsertRequest,
    UserLocationResponse,
    UserLocationUpsertRequest,
    UserPreferencesPatchRequest,
    UserPreferencesResponse,
    UserProfileResponse,
    UserProfileUpsertRequest,
    UserProfileSearchResponse,
    PublicProfileEventRow,
    UserPublicProfileResponse,
)
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, get_uow
from eventflow.service_layer import budget_views


router = APIRouter(tags=["Users"])


@router.get("/users/me/preferences", status_code=status.HTTP_200_OK, response_model=UserPreferencesResponse)
async def get_user_preferences(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return UserPreferencesResponse(monthly_budget_minor_units=None)
    row = session.execute(
        text("SELECT monthly_budget_minor_units FROM user_preferences WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    if row is None:
        return UserPreferencesResponse(monthly_budget_minor_units=None)
    return UserPreferencesResponse(monthly_budget_minor_units=row.monthly_budget_minor_units)


@router.patch("/users/me/preferences", status_code=status.HTTP_200_OK, response_model=UserPreferencesResponse)
async def patch_user_preferences(
    body: UserPreferencesPatchRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    patch = body.model_dump(exclude_unset=True)
    if "monthly_budget_minor_units" not in patch:
        row = session.execute(
            text("SELECT monthly_budget_minor_units FROM user_preferences WHERE user_id = :uid"),
            {"uid": str(user_id)},
        ).first()
        return UserPreferencesResponse(monthly_budget_minor_units=None if row is None else row.monthly_budget_minor_units)

    budget = patch["monthly_budget_minor_units"]
    if budget is not None and budget < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="monthly_budget_minor_units cannot be negative")
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO user_preferences (user_id, monthly_budget_minor_units, updated_at)
            VALUES (:uid, :budget, :now)
            ON CONFLICT (user_id) DO UPDATE SET
              monthly_budget_minor_units = EXCLUDED.monthly_budget_minor_units,
              updated_at = EXCLUDED.updated_at
            """
        ),
        {"uid": str(user_id), "budget": budget, "now": now},
    )
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save preferences")
    return UserPreferencesResponse(monthly_budget_minor_units=budget)


@router.get("/users/me/budget-summary", status_code=status.HTTP_200_OK, response_model=BudgetSummaryResponse)
async def get_budget_summary(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    pref = session.execute(
        text("SELECT monthly_budget_minor_units FROM user_preferences WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    budget_minor = None if pref is None else pref[0]
    summary = budget_views.month_budget_summary(
        session=session,
        user_id=user_id,
        year=year,
        month=month,
        tz_offset_minutes=tz_offset_minutes,
        budget_minor_units=budget_minor,
    )
    return BudgetSummaryResponse(**summary)


@router.put(
    "/users/me/locations/{label}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upsert_location(
    label: str,
    body: UserLocationUpsertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    if label not in {"home", "work"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="label must be 'home' or 'work'")

    loc = UserLocation(user_id=user_id, label=label, address=body.address, lat=body.lat, lng=body.lng)
    with uow:
        uow.user_locations.upsert(loc)
        uow.commit()
    return None


@router.get(
    "/users/me/locations/{label}",
    status_code=status.HTTP_200_OK,
    response_model=UserLocationResponse,
)
async def get_location(
    label: str,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    if label not in {"home", "work"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="label must be 'home' or 'work'")

    with uow:
        loc = uow.user_locations.get(user_id=user_id, label=label)
        if loc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not set")
        return UserLocationResponse(label=loc.label, address=loc.address, lat=loc.lat, lng=loc.lng)


@router.post(
    "/users/me/push-tokens",
    status_code=status.HTTP_201_CREATED,
    response_model=PushTokenResponse,
)
async def register_push_token(
    body: PushTokenUpsertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    if not body.expo_push_token or not body.expo_push_token.startswith("ExponentPushToken["):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Expo push token")

    now = datetime.now(timezone.utc)
    tok = DevicePushToken(
        user_id=user_id,
        expo_push_token=body.expo_push_token,
        platform=body.platform,
        device_id=body.device_id,
        created_at=now,
        last_seen_at=now,
    )
    with uow:
        saved = uow.device_push_tokens.upsert(tok)
        uow.commit()
        return PushTokenResponse(
            token_id=saved.id,
            expo_push_token=saved.expo_push_token,
            platform=saved.platform,
            device_id=saved.device_id,
        )


@router.delete(
    "/users/me/push-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unregister_push_token(
    token_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    now = datetime.now(timezone.utc)
    with uow:
        tok = uow.device_push_tokens.get(token_id=token_id)
        if tok is None:
            uow.commit()
            return None
        if tok.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your push token")
        uow.device_push_tokens.disable(token_id=token_id, disabled_at=now)
        uow.commit()
    return None


@router.get("/users/me/profile", status_code=status.HTTP_200_OK, response_model=UserProfileResponse)
async def get_my_profile(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    row = session.execute(
        text("SELECT display_name, avatar_url, is_public FROM user_profiles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    if row is None:
        return UserProfileResponse(user_id=user_id, display_name="User")
    return UserProfileResponse(user_id=user_id, display_name=row.display_name, avatar_url=row.avatar_url, is_public=row.is_public)


@router.put("/users/me/profile", status_code=status.HTTP_200_OK, response_model=UserProfileResponse)
async def upsert_my_profile(
    body: UserProfileUpsertRequest,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    now = datetime.now(timezone.utc)
    session.execute(
        text("""
            INSERT INTO user_profiles (user_id, display_name, avatar_url, is_public, created_at, updated_at)
            VALUES (:uid, :name, :avatar, COALESCE(:public, true), :now, :now)
            ON CONFLICT (user_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                avatar_url = EXCLUDED.avatar_url,
                is_public = COALESCE(EXCLUDED.is_public, user_profiles.is_public),
                updated_at = EXCLUDED.updated_at
        """),
        {"uid": str(user_id), "name": body.display_name, "avatar": body.avatar_url, "public": body.is_public, "now": now},
    )
    session.commit()
    row = session.execute(
        text("SELECT display_name, avatar_url, is_public FROM user_profiles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    return UserProfileResponse(user_id=user_id, display_name=row.display_name, avatar_url=row.avatar_url, is_public=row.is_public)


@router.get("/users/search", status_code=status.HTTP_200_OK, response_model=UserProfileSearchResponse)
async def search_users(
    q: str = Query(default="", min_length=0, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session=Depends(get_session),
):
    if session is None:
        return UserProfileSearchResponse(results=[], total=0)
    query = q.strip()
    if not query:
        rows = session.execute(
            text("SELECT user_id, display_name, avatar_url FROM user_profiles WHERE is_public = true ORDER BY display_name LIMIT :lim OFFSET :off"),
            {"lim": limit, "off": offset},
        ).all()
        total = session.execute(
            text("SELECT COUNT(*) FROM user_profiles WHERE is_public = true")
        ).scalar() or 0
    else:
        pattern = f"%{query}%"
        rows = session.execute(
            text("SELECT user_id, display_name, avatar_url FROM user_profiles WHERE is_public = true AND display_name ILIKE :q ORDER BY display_name LIMIT :lim OFFSET :off"),
            {"q": pattern, "lim": limit, "off": offset},
        ).all()
        total = session.execute(
            text("SELECT COUNT(*) FROM user_profiles WHERE is_public = true AND display_name ILIKE :q"),
            {"q": pattern},
        ).scalar() or 0
    results = [UserProfileResponse(user_id=r[0], display_name=r[1], avatar_url=r[2]) for r in rows]
    return UserProfileSearchResponse(results=results, total=total)


@router.get("/users/{user_id}/profile", status_code=status.HTTP_200_OK, response_model=UserProfileResponse)
async def get_user_profile(
    user_id: UUID,
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    row = session.execute(
        text("SELECT display_name, avatar_url, is_public FROM user_profiles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not row.is_public:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserProfileResponse(user_id=user_id, display_name=row.display_name, avatar_url=row.avatar_url, is_public=row.is_public)


@router.get("/users/{user_id}/public-profile", status_code=status.HTTP_200_OK)
async def get_user_public_profile(
    user_id: UUID,
    session=Depends(get_session),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    row = session.execute(
        text("SELECT display_name, avatar_url, is_public FROM user_profiles WHERE user_id = :uid"),
        {"uid": str(user_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not row.is_public:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    events_organized = session.execute(
        text("""
            SELECT id, title, start_time, venue, poster_image_uri
            FROM community_events
            WHERE user_id = :uid AND visibility = 'public'
            ORDER BY start_time DESC
            LIMIT 20
        """),
        {"uid": str(user_id)},
    ).fetchall()

    events_attended = session.execute(
        text("""
            SELECT DISTINCT ce.id, ce.title, ce.start_time, ce.venue, ce.poster_image_uri
            FROM community_events ce
            INNER JOIN tickets t ON t.community_event_id = ce.id AND t.user_id = :uid AND t.status = 'active'
            WHERE ce.visibility = 'public'
            ORDER BY ce.start_time DESC
            LIMIT 20
        """),
        {"uid": str(user_id)},
    ).fetchall()

    events = []
    seen = set()
    for r in events_organized:
        eid = str(r.id)
        seen.add(eid)
        events.append(PublicProfileEventRow(
            community_event_id=r.id, title=r.title, start_time=r.start_time,
            venue=r.venue, poster_image_uri=r.poster_image_uri, role="organizer",
        ))
    for r in events_attended:
        eid = str(r.id)
        if eid in seen:
            continue
        events.append(PublicProfileEventRow(
            community_event_id=r.id, title=r.title, start_time=r.start_time,
            venue=r.venue, poster_image_uri=r.poster_image_uri, role="attendee",
        ))

    return UserPublicProfileResponse(
        user_id=user_id,
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        events=events,
        total=len(events),
    )

