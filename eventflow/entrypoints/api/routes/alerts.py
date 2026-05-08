from __future__ import annotations

from fastapi import APIRouter, status


router = APIRouter(tags=["Alerts"])


@router.get("/alerts/health", status_code=status.HTTP_200_OK)
async def alerts_health():
    return {"ok": True}

