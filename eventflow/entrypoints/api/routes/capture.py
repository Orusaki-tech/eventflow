from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from eventflow.domain import commands
from eventflow.entrypoints.api.schemas import CaptureRequest, EventDraftResponse
from eventflow.entrypoints.dependencies import get_current_user_id, get_gemini_client, get_uow
from eventflow.service_layer import handlers


router = APIRouter(tags=["Capture"])
_log = logging.getLogger(__name__)


@router.post("/capture/image", status_code=status.HTTP_201_CREATED, response_model=EventDraftResponse)
async def capture_event_image(
    body: CaptureRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
):
    try:
        image_bytes = base64.b64decode(body.image_base64)
    except Exception:
        _log.exception("Failed to decode base64 image payload")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 payload")

    result = handlers.handle_capture_event_image(
        commands.CaptureEventImage(user_id=user_id, image_bytes=image_bytes),
        uow,
        gemini=gemini,
    )
    return result

