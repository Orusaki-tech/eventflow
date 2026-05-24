from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from eventflow.adapters.repository import EventShare, Group, GroupMembership
from eventflow.entrypoints.api.schemas import (
    GroupCreateRequest,
    GroupEventShareRequest,
    GroupJoinByTokenRequest,
    GroupMemberAddRequest,
    GroupPinRequest,
    GroupResponse,
    GroupRsvpRequest,
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
    g = Group(name=name, owner_user_id=user_id, created_at=now, invite_token=secrets.token_urlsafe(12), group_type="friend")
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        uow.session.add(g)  # type: ignore[attr-defined]
        uow.session.add(GroupMembership(group_id=g.id, user_id=user_id, role="owner", created_at=now))  # type: ignore[attr-defined]
        uow.commit()
    return GroupResponse(
        group_id=g.id,
        name=g.name,
        owner_user_id=g.owner_user_id,
        invite_token=g.invite_token,
        group_type=g.group_type,
    )


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
            SELECT g.id AS group_id,
                   g.name,
                   g.owner_user_id,
                   g.invite_token,
                   g.group_type,
                   gm.role AS my_role
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
        # Enforce membership first to avoid leaking event existence.
        mem = uow.session.get(GroupMembership, {"group_id": group_id, "user_id": user_id})  # type: ignore[attr-defined]
        if mem is None:
            raise HTTPException(status_code=403, detail="Not a group member")
        # Only event owner can share.
        evt = uow.events.get(body.event_id)
        if evt is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if evt.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your event")

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


@router.post("/groups/join-by-token", status_code=status.HTTP_201_CREATED)
async def join_group_by_token(
    body: GroupJoinByTokenRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    now = datetime.now(timezone.utc)
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        row = uow.session.execute(  # type: ignore[attr-defined]
            text("SELECT id FROM groups WHERE invite_token = :t LIMIT 1"),
            {"t": body.invite_token.strip()},
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Invalid invite token")
        gid = row[0]
        uow.session.merge(GroupMembership(group_id=gid, user_id=user_id, role="member", created_at=now))  # type: ignore[attr-defined]
        uow.commit()
    return {"ok": True, "group_id": str(gid)}


@router.post("/groups/{group_id}/rsvp", status_code=status.HTTP_201_CREATED)
async def rsvp_group_event(
    group_id: UUID,
    body: GroupRsvpRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    now = datetime.now(timezone.utc)
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        mem = uow.session.get(GroupMembership, {"group_id": group_id, "user_id": user_id})  # type: ignore[attr-defined]
        if mem is None:
            raise HTTPException(status_code=403, detail="Not a group member")
        # Verify the event is actually shared to this group.
        share = uow.session.execute(  # type: ignore[attr-defined]
            text("SELECT 1 FROM event_shares WHERE event_id = :e AND group_id = :g"),
            {"e": str(body.event_id), "g": str(group_id)},
        ).first()
        if share is None:
            raise HTTPException(status_code=403, detail="Event not shared to this group")
        uow.session.execute(  # type: ignore[attr-defined]
            text(
                """
                INSERT INTO group_rsvps (group_id, user_id, event_id, status, updated_at)
                VALUES (:g, :u, :e, :st, :now)
                ON CONFLICT (group_id, user_id, event_id) DO UPDATE SET
                  status = EXCLUDED.status,
                  updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "g": str(group_id),
                "u": str(user_id),
                "e": str(body.event_id),
                "st": body.status,
                "now": now,
            },
        )
        uow.commit()
    return {"ok": True}


@router.patch("/groups/{group_id}/pin", status_code=status.HTTP_200_OK)
async def pin_group_event(
    group_id: UUID,
    body: GroupPinRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    with uow:
        if not hasattr(uow, "session"):
            raise HTTPException(status_code=500, detail="DB not configured")
        g = uow.session.get(Group, group_id)  # type: ignore[attr-defined]
        if g is None:
            raise HTTPException(status_code=404, detail="Group not found")
        if g.owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Only owner can pin")
        uow.session.execute(  # type: ignore[attr-defined]
            text("UPDATE groups SET pinned_event_id = :e WHERE id = :g"),
            {"g": str(group_id), "e": str(body.event_id) if body.event_id else None},
        )
        uow.commit()
    return {"ok": True}

