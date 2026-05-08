from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eventflow.domain.exceptions import DraftNotFound, InvariantViolation, PermissionDenied
from eventflow.entrypoints.api.schemas import DraftUpdateRequest, EventDraftDetailResponse
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, get_uow
from eventflow.service_layer import handlers, views


router = APIRouter(tags=["Drafts"])


@router.get("/drafts/{draft_id}", status_code=status.HTTP_200_OK, response_model=EventDraftDetailResponse)
async def get_draft(
    draft_id: UUID,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    with uow:
        draft = uow.drafts.get(draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        if draft.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your draft")
        uow.commit()

        return EventDraftDetailResponse(
            draft_id=draft.id,
            title=draft.title,
            start_time=draft.start_time,
            venue=draft.venue,
            confidence_score=draft.confidence_score,
            confirmed_at=draft.confirmed_at,
            price=getattr(draft, "price", None),
        )


@router.get("/drafts", status_code=status.HTTP_200_OK)
async def list_drafts(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|confirmed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
    uow=Depends(get_uow),
):
    if session is None:
        with uow:
            rows = views.list_drafts(user_id=user_id, session=None, drafts_repo=uow.drafts, status=status_filter, limit=limit)
            uow.commit()
            return rows
    return views.list_drafts(user_id=user_id, session=session, status=status_filter, limit=limit)


@router.patch("/drafts/{draft_id}", status_code=status.HTTP_200_OK, response_model=EventDraftDetailResponse)
async def patch_draft(
    draft_id: UUID,
    body: DraftUpdateRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    try:
        result = handlers.patch_draft_fields(
            draft_id=draft_id,
            user_id=user_id,
            patch=body.model_dump(exclude_unset=True),
            uow=uow,
        )
        return result
    except DraftNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e))
    except InvariantViolation as e:
        raise HTTPException(status_code=409, detail=str(e))

