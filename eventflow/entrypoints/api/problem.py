from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse


def problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    type_url: str = "about:blank",
    instance: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    payload: Dict[str, Any] = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance is not None:
        payload["instance"] = instance
    if extra:
        payload.update(extra)

    return JSONResponse(payload, status_code=status_code, media_type="application/problem+json")

