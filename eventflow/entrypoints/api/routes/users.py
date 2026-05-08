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
    return UserPreferencesResponse(monthly_budget_minor_units=row[0])


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
        return UserPreferencesResponse(monthly_budget_minor_units=None if row is None else row[0])

    budget = patch["monthly_budget_minor_units"]
    if budget is not None and budget < 0:
        raise HTTPException(status_code=400, detail="monthly_budget_minor_units cannot be negative")
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
    session.commit()
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
        raise HTTPException(status_code=400, detail="label must be 'home' or 'work'")

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
        raise HTTPException(status_code=400, detail="label must be 'home' or 'work'")

    with uow:
        loc = uow.user_locations.get(user_id=user_id, label=label)
        if loc is None:
            raise HTTPException(status_code=404, detail="Location not set")
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
        raise HTTPException(status_code=400, detail="Invalid Expo push token")

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
            raise HTTPException(status_code=403, detail="Not your push token")
        uow.device_push_tokens.disable(token_id=token_id, disabled_at=now)
        uow.commit()
    return None

