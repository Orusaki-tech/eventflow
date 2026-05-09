from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterator
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from eventflow.config import get_settings
from eventflow.adapters.gemini_client import AbstractGeminiClient, FakeGeminiClient, ParsedEventDraft
from eventflow.adapters.gemini import GeminiClient
from eventflow.adapters.calendar_client import AbstractCalendarClient, GoogleCalendarClient, NoOpCalendarClient
from eventflow.adapters.push_client import AbstractPushClient, NoopPushClient
from eventflow.adapters.event_publisher import AbstractEventPublisher, NoOpEventPublisher, RedisEventPublisher
from eventflow.adapters.image_token_store import ImageTokenStore, InMemoryImageTokenStore
from eventflow.adapters.poster_store import PosterStore
from eventflow.adapters.share_parse_cache import NoOpShareParseCache, ShareParseCache
from eventflow.service_layer.unit_of_work import AbstractUnitOfWork, FakeUnitOfWork, SqlAlchemyUnitOfWork
from eventflow.adapters.orm import start_mappers
from eventflow.auth.supabase import AuthenticatedUser, verify_supabase_jwt
import jwt
from urllib.error import URLError
import logging
import redis


@lru_cache
def get_session_factory():
    db_url = get_settings().effective_db_url
    if not db_url:
        return None
    engine = create_engine(db_url, future=True)
    # Keep attributes available after commit so handlers can safely read ids
    # outside of the UnitOfWork context.
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@lru_cache
def _get_local_fake_uow() -> FakeUnitOfWork:
    # When DB_URL is not configured (common in local/dev), keep a single in-memory
    # unit-of-work so confirmed events show up in subsequent list calls.
    return FakeUnitOfWork()


def get_uow() -> AbstractUnitOfWork:
    session_factory = get_session_factory()
    if session_factory is None:
        return _get_local_fake_uow()

    start_mappers()
    return SqlAlchemyUnitOfWork(session_factory)


_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _get_local_user_id() -> UUID:
    # Stable per-process ID so local unauthenticated flows behave consistently.
    return uuid4()


def _authenticated_user_from_bearer(
    creds: HTTPAuthorizationCredentials | None,
) -> AuthenticatedUser:
    """Resolve bearer (or local synthetic user). Shared by ``get_current_user_id`` and admin checks."""
    settings = get_settings()
    if settings.env == "local" and settings.allow_unauthenticated_local:
        if creds is None or creds.scheme.lower() != "bearer":
            return AuthenticatedUser(id=str(_get_local_user_id()), raw_claims={})

    if not settings.supabase_jwks_url:
        if settings.env in ("prod", "dev") or not settings.allow_unauthenticated_local:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth not configured")
        return AuthenticatedUser(id=str(_get_local_user_id()), raw_claims={})

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        return verify_supabase_jwt(creds.credentials)
    except jwt.PyJWTError as e:
        if settings.env == "local":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {type(e).__name__}: {e}",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except URLError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Auth temporarily unavailable (JWKS fetch failed): {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auth error: {type(e).__name__}: {e}",
        )


def get_authenticated_supabase_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    """Full JWT claims (incl. ``email``) for admin allowlist; same local shortcut as ``get_current_user_id``."""
    return _authenticated_user_from_bearer(creds)


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    return UUID(_authenticated_user_from_bearer(creds).id)


def _parse_admin_user_ids_csv() -> set[str]:
    csv = get_settings().admin_user_ids_csv or ""
    return {s.strip() for s in csv.split(",") if s.strip()}


def _parse_admin_operator_emails_csv() -> set[str]:
    csv = get_settings().admin_operator_emails_csv or ""
    return {s.strip().lower() for s in csv.split(",") if s.strip()}


def _admin_in_allowlist_table(session: object, user_id: UUID) -> bool:
    """True when ``admin_console_allowlist`` contains ``user_id``. Missing table → False (run migrations)."""
    try:
        row = session.execute(
            text("SELECT 1 FROM admin_console_allowlist WHERE user_id = :u LIMIT 1"),
            {"u": user_id},
        ).first()
        return row is not None
    except ProgrammingError:
        return False


def is_admin_user(
    user_id: UUID,
    session: object | None = None,
    jwt_claims: dict | None = None,
) -> bool:
    """
    Operator access for JWT routes.

    If ``ADMIN_OPERATOR_EMAILS`` is non-empty: allow only when JWT ``email`` (case-insensitive) is listed;
    ``ADMIN_USER_IDS`` and ``admin_console_allowlist`` are ignored.

    Otherwise: ``ADMIN_USER_IDS`` env and/or ``admin_console_allowlist`` table (when ``session`` is set).
    """
    emails = _parse_admin_operator_emails_csv()
    if emails:
        raw = (jwt_claims or {}).get("email")
        if not raw or not isinstance(raw, str):
            return False
        return raw.strip().lower() in emails

    if str(user_id) in _parse_admin_user_ids_csv():
        return True
    if session is None:
        return False
    return _admin_in_allowlist_table(session, user_id)


def require_admin_api_token(x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> None:
    settings = get_settings()
    expected = (settings.admin_api_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API token not configured (set ADMIN_API_TOKEN)",
        )
    if not x_admin_token or x_admin_token.strip() != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_gemini_client() -> AbstractGeminiClient:
    settings = get_settings()
    if settings.gemini_api_key:
        return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)

    parsed = ParsedEventDraft(
        title="Sample Event",
        start_time=datetime.now(timezone.utc),
        venue="Sample Venue",
        confidence_score=0.5,
        price=None,
    )
    return FakeGeminiClient(parsed=parsed)


def get_calendar_client() -> AbstractCalendarClient:
    settings = get_settings()
    if settings.google_calendar_credentials_json:
        return GoogleCalendarClient(credentials_json=settings.google_calendar_credentials_json)
    return NoOpCalendarClient()


@lru_cache
def get_write_scheduler_client():
    """Paused APScheduler client writing jobs to the shared SQL jobstore (scheduler worker executes)."""
    from eventflow.workers.scheduler import build_scheduler_client

    return build_scheduler_client()


def get_push_client() -> AbstractPushClient:
    return NoopPushClient()


def get_event_publisher() -> AbstractEventPublisher:
    settings = get_settings()
    if not settings.redis_url:
        return NoOpEventPublisher()
    return RedisEventPublisher(settings.redis_url)


_log = logging.getLogger(__name__)


def _redis_is_healthy(redis_url: str) -> bool:
    try:
        r = redis.Redis.from_url(redis_url)
        return bool(r.ping())
    except Exception:
        return False


@lru_cache
def _redis_image_token_store(redis_url: str) -> ImageTokenStore:
    return ImageTokenStore(redis_url, ttl_seconds=600)


_memory_image_token_store: InMemoryImageTokenStore | None = None


def get_image_token_store() -> ImageTokenStore | InMemoryImageTokenStore:
    """Redis-backed in deployed environments; in-memory fallback for local dev without Redis."""
    settings = get_settings()
    if settings.redis_url:
        if _redis_is_healthy(settings.redis_url):
            return _redis_image_token_store(settings.redis_url)
        if settings.env in ("prod", "dev"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="REDIS_URL is set but Redis is unreachable.",
            )
        _log.warning("Redis unreachable; using in-memory image token store (ENV=local).")
    if settings.env in ("prod", "dev"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "REDIS_URL is required for image preview tokens. "
                "Start Redis or set ENV=local to use an in-memory fallback."
            ),
        )
    global _memory_image_token_store
    if _memory_image_token_store is None:
        _memory_image_token_store = InMemoryImageTokenStore(ttl_seconds=600)
    return _memory_image_token_store


@lru_cache
def get_share_parse_cache() -> ShareParseCache | NoOpShareParseCache:
    settings = get_settings()
    if not settings.redis_url:
        # Global first-seen URL → Gemini dedupe requires Redis-backed cache in deployed envs.
        if settings.env in ("dev", "prod"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="REDIS_URL is required for share URL parse cache (global URL dedupe / single Gemini parse per URL).",
            )
        return NoOpShareParseCache()
    if not _redis_is_healthy(settings.redis_url):
        if settings.env in ("dev", "prod"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="REDIS_URL is set but Redis is unreachable (required in dev/prod).",
            )
        _log.warning("Redis unreachable; disabling share URL parse cache (ENV=local).")
        return NoOpShareParseCache()
    return ShareParseCache(settings.redis_url)


@lru_cache
def get_poster_store() -> PosterStore:
    settings = get_settings()
    return PosterStore(settings.poster_storage_dir)


def get_session() -> Iterator[object]:
    session_factory = get_session_factory()
    if session_factory is None:
        yield None
        return

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def require_admin_user(
    auth_user: AuthenticatedUser = Depends(get_authenticated_supabase_user),
    session=Depends(get_session),
) -> UUID:
    """JWT dependency: see ``is_admin_user`` (email allowlist or UUID/table)."""
    user_id = UUID(auth_user.id)
    if not is_admin_user(user_id, session=session, jwt_claims=auth_user.raw_claims):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return user_id
