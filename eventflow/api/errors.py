from __future__ import annotations

from fastapi import Request

from eventflow.domain.exceptions import DomainError, DraftNotFound, InvariantViolation, PastEventError, PermissionDenied
from eventflow.entrypoints.api.problem import problem


async def domain_error_handler(request: Request, exc: DomainError):
    if isinstance(exc, DraftNotFound):
        return problem(status_code=404, title="Not found", detail=str(exc), instance=str(request.url))
    if isinstance(exc, PermissionDenied):
        return problem(status_code=403, title="Forbidden", detail=str(exc), instance=str(request.url))
    if isinstance(exc, (InvariantViolation, PastEventError)):
        return problem(status_code=409, title="Conflict", detail=str(exc), instance=str(request.url))
    return problem(status_code=400, title="Domain error", detail=str(exc), instance=str(request.url))

