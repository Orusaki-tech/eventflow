from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterator
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
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
from eventflow.auth.supabase import verify_supabase_jwt
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


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    settings = get_settings()
    # Local dev fallback: allow missing auth header for quick iteration/testing.
    if settings.env == "local" and settings.allow_unauthenticated_local:
        if creds is None or creds.scheme.lower() != "bearer":
            return _get_local_user_id()

    if not settings.supabase_jwks_url:
        if settings.env in ("prod", "dev") or not settings.allow_unauthenticated_local:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth not configured")
        # Local/test fallback until auth env is configured.
        return _get_local_user_id()

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        user = verify_supabase_jwt(creds.credentials)
        return UUID(user.id)
    except jwt.PyJWTError as e:
        # In local dev, surface the underlying reason to speed up setup/debugging.
        if settings.env == "local":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {type(e).__name__}: {e}",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except URLError as e:
        # JWKS fetch / network failure should not masquerade as a bad user token.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Auth temporarily unavailable (JWKS fetch failed): {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auth error: {type(e).__name__}: {e}",
        )


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

