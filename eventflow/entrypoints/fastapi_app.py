from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from eventflow.adapters.monitoring import PrometheusMiddleware, metrics_handler
from eventflow.api.errors import domain_error_handler
from eventflow.domain.exceptions import DomainError
from eventflow.entrypoints.api.routes import (
    admin_console,
    alerts,
    calendar_oauth,
    capture,
    discovery,
    drafts,
    events,
    groups,
    health,
    media,
    places,
    product_gap,
    share,
    ticketing,
    users,
    venues,
)
from eventflow.entrypoints.api.problem import problem
from eventflow.entrypoints.dependencies import get_calendar_client, get_push_client
from eventflow.config import get_settings
from eventflow.workers.scheduler import build_scheduler_client
from eventflow.service_layer import handlers

_log = logging.getLogger(__name__)


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _install_middleware(app: FastAPI) -> None:
    """
    Wire up CORS + TrustedHost middleware from settings.

    - CORS: native React Native fetches are not subject to CORS, so leaving
      `CORS_ALLOW_ORIGINS` unset is fine for a mobile-only client. Set it
      (CSV) the moment you have an Expo Web build, an admin web UI, or any
      browser-based client.

    - TrustedHost: only enforced when env=prod. Prevents Host-header attacks
      once you're behind a reverse proxy. Use "*" to disable.

    `allow_credentials` is False because auth is `Authorization: Bearer …`,
    not cookies — and the CORS spec forbids `*` origins with credentials, so
    keeping credentials off lets us safely use `*` in dev.
    """
    settings = get_settings()

    trusted = _split_csv(settings.trusted_hosts)
    if settings.env == "prod" and trusted and trusted != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted)

    origins = _split_csv(settings.cors_allow_origins)
    if not origins:
        # In non-prod, default to wide-open so Expo Web / curl / dashboards
        # "just work" during development. In prod, default to no CORS at all
        # (native mobile clients don't need it).
        if settings.env == "prod":
            return
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
        max_age=600,
    )


def create_app() -> FastAPI:
    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        settings = get_settings()
        if settings.supabase_jwks_url and not settings.effective_db_url:
            _log.warning(
                "SUPABASE_JWKS_URL is set but DB_URL is empty: API will use in-memory stores only — "
                "drafts/events will not persist. Point DB_URL at Postgres (e.g. Supabase Database URI) "
                "and run `alembic upgrade head`."
            )
        handlers.calendar_client = get_calendar_client()
        handlers.push_client = get_push_client()
        # In tests/dev, we allow API boot without a DB_URL; scheduling is a no-op then.
        # In local dev, DB_URL may be present but temporarily unreachable (DNS/VPN/etc) —
        # don't block API boot on scheduler jobstore connectivity.
        if not settings.effective_db_url:
            handlers.scheduler_client = handlers.FakeSchedulerClient()
        else:
            try:
                handlers.scheduler_client = build_scheduler_client()
            except Exception as e:
                _log.warning("Scheduler disabled (DB unavailable): %s", e)
                handlers.scheduler_client = handlers.FakeSchedulerClient()
        yield

    app = FastAPI(title="EventFlow", version="1.0.0", lifespan=_lifespan)

    _install_middleware(app)

    app.add_middleware(PrometheusMiddleware)
    app.add_api_route("/metrics", endpoint=metrics_handler, include_in_schema=False)

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        return await domain_error_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return problem(
            status_code=422,
            title="Validation error",
            detail="Request validation failed",
            instance=str(request.url),
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException):
        # Wrap HTTPExceptions in RFC7807.
        return problem(
            status_code=exc.status_code,
            title="HTTP error",
            detail=str(exc.detail),
            instance=str(request.url),
        )

    @app.exception_handler(ResponseValidationError)
    async def _response_validation_error(request: Request, exc: ResponseValidationError):
        _log.warning("response validation failed path=%s errors=%s", request.url.path, exc.errors())
        return problem(
            status_code=500,
            title="Response validation error",
            detail=json.dumps(exc.errors(), default=str),
            instance=str(request.url),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        root = getattr(exc, "orig", None)
        msg = str(root) if root is not None else str(exc)
        _log.exception("database error on %s: %s", request.url.path, msg)
        return problem(
            status_code=503,
            title="Database error",
            detail=msg,
            instance=str(request.url),
        )

    app.include_router(capture.router, prefix="/api/v1")
    app.include_router(events.router, prefix="/api/v1")
    app.include_router(drafts.router, prefix="/api/v1")
    app.include_router(share.router, prefix="/api/v1")
    app.include_router(media.router, prefix="/api/v1")
    app.include_router(discovery.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(venues.router, prefix="/api/v1")
    app.include_router(places.router, prefix="/api/v1")
    app.include_router(groups.router, prefix="/api/v1")
    app.include_router(product_gap.router, prefix="/api/v1")
    app.include_router(ticketing.router, prefix="/api/v1")
    app.include_router(admin_console.router, prefix="/api/v1")
    app.include_router(calendar_oauth.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")

    @app.get("/portal", include_in_schema=False)
    async def business_portal_stub() -> HTMLResponse:
        return HTMLResponse(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>EventFlow Business Portal</title></head>"
            "<body><h1>EventFlow Business Portal</h1>"
            "<p>Use the mobile app for attendee flows. Claim listings and upload videos via API:</p>"
            "<ul><li>POST /api/v1/businesses</li><li>POST /api/v1/listing-analytics</li>"
            "<li>POST /api/v1/event-videos</li></ul></body></html>"
        )

    return app


app = create_app()

