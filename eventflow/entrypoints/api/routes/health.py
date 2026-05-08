from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from eventflow.config import get_settings


router = APIRouter(tags=["Health"])


@router.get("/healthz")
async def healthz():
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.env,
        "time": datetime.now(timezone.utc).isoformat(),
    }

