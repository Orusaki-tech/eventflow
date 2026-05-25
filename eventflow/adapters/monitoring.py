from __future__ import annotations

import time
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest, REGISTRY
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        method = request.method
        path = _normalize_path(request.url.path)
        start = time.monotonic()

        response = await call_next(request)

        duration = time.monotonic() - start
        status = response.status_code

        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

        return response


def _normalize_path(path: str) -> str:
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        if part.isdigit() or _is_uuid(part):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


def _is_uuid(s: str) -> bool:
    return (
        len(s) == 36
        and s[8] == "-"
        and s[13] == "-"
        and s[18] == "-"
        and s[23] == "-"
        and all(c in "0123456789abcdefABCDEF-" for c in s)
    )


def metrics_handler(request: Request) -> Response:
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
