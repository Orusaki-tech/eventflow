from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from eventflow.adapters.repository import EventShare, Group, GroupMembership
from eventflow.entrypoints.api.schemas import (
    GroupCreateRequest,
    GroupEventShareRequest,
    GroupMemberAddRequest,
    GroupResponse,
)
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, get_uow


router = APIRouter(tags=["Groups"])


@router.post("/groups", status_code=status.HTTP_201_CREATED, response_model=GroupResponse)
async def create_group(
    body: GroupCreateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    now = datetime.now(timezone.utc)
    g = Group(name=name, owner_user_id=user_id, created_at=now)
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        uow.session.add(g)  # type: ignore[attr-defined]
        uow.session.add(GroupMembership(group_id=g.id, user_id=user_id, role="owner", created_at=now))  # type: ignore[attr-defined]
        uow.commit()
    return GroupResponse(group_id=g.id, name=g.name, owner_user_id=g.owner_user_id)


@router.get("/groups", status_code=status.HTTP_200_OK, response_model=list[GroupResponse])
async def list_groups(
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    rows = session.execute(
        text(
            """
            SELECT g.id as group_id, g.name, g.owner_user_id
            FROM groups g
            JOIN group_memberships gm ON gm.group_id = g.id
            WHERE gm.user_id = :user_id
            ORDER BY g.created_at DESC
            """
        ),
        {"user_id": str(user_id)},
    )
    return [GroupResponse(**dict(r._mapping)) for r in rows]


@router.post("/groups/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: UUID,
    body: GroupMemberAddRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    role = body.role.strip() or "member"
    if role not in {"owner", "member"}:
        raise HTTPException(status_code=400, detail="role must be owner|member")
    now = datetime.now(timezone.utc)
    with uow:
        # Require group owner to add members.
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        g = uow.session.get(Group, group_id)  # type: ignore[attr-defined]
        if g is None:
            raise HTTPException(status_code=404, detail="Group not found")
        if g.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Not group owner")
        uow.session.merge(GroupMembership(group_id=group_id, user_id=body.user_id, role=role, created_at=now))  # type: ignore[attr-defined]
        uow.commit()
    return {"ok": True}


@router.post("/groups/{group_id}/events", status_code=status.HTTP_201_CREATED)
async def share_event_to_group(
    group_id: UUID,
    body: GroupEventShareRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    now = datetime.now(timezone.utc)
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        g = uow.session.get(Group, group_id)  # type: ignore[attr-defined]
        if g is None:
            raise HTTPException(status_code=404, detail="Group not found")
        # Only event owner can share; enforce membership in group.
        evt = uow.events.get(body.event_id)
        if evt is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your event")

        mem = uow.session.get(GroupMembership, {"group_id": group_id, "user_id": user_id})  # type: ignore[attr-defined]
        if mem is None:
            raise HTTPException(status_code=403, detail="Not a group member")

        uow.session.merge(EventShare(event_id=body.event_id, group_id=group_id, shared_by_user_id=user_id, created_at=now))  # type: ignore[attr-defined]
        uow.commit()
    return {"ok": True}


@router.get("/groups/{group_id}/events", status_code=status.HTTP_200_OK)
async def list_group_events(
    group_id: UUID,
    day: str = Query(default="today", pattern="^(today)$"),
    tz_offset_minutes: int = Query(default=0, ge=-840, le=840),
    limit: int = Query(default=200, ge=1, le=500),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
):
    if session is None:
        return []
    # Minimal: reuse today query and filter for group membership + event_shares.
    # We'll refine later when adding richer response models.
    if day != "today":
        raise HTTPException(status_code=400, detail="Only day=today supported")

    results = session.execute(
        text(
            """
            WITH bounds AS (
              SELECT
                date_trunc('day', (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval) AS local_day_start,
                date_trunc('day', (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval) + interval '1 day' AS local_day_end
            )
            SELECT e.id, e.user_id, e.title, e.start_time, e.venue, e.visibility
            FROM scheduled_events e
            JOIN event_shares es ON es.event_id = e.id
            JOIN group_memberships gm ON gm.group_id = es.group_id
            JOIN bounds b ON true
            WHERE es.group_id = :group_id
              AND gm.user_id = :user_id
              AND e.cancelled_at IS NULL
              AND (e.start_time AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval >= b.local_day_start
              AND (e.start_time AT TIME ZONE 'UTC') + (:offset_mins || ' minutes')::interval < b.local_day_end
            ORDER BY e.start_time ASC
            LIMIT :limit
            """
        ),
        {"group_id": str(group_id), "user_id": str(user_id), "offset_mins": int(tz_offset_minutes), "limit": int(limit)},
    )
    return [dict(r._mapping) for r in results]

