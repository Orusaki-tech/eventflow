"""Persist extracted preview bytes as poster_assets and link them to drafts (event_sources)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

import redis
from psycopg.types.json import Json
from sqlalchemy import text

from eventflow.adapters.gemini import _coerce_optional_price
from eventflow.adapters.poster_fingerprint import dhash64
from eventflow.adapters.poster_store import PosterStore

_log = logging.getLogger(__name__)


def _poster_cache_key_sha256(content_sha256_hex: str) -> str:
    return f"eventflow:poster:sha256:{content_sha256_hex}"


def link_event_source_poster(
    *,
    session,
    user_id: UUID,
    draft_id: UUID,
    poster_asset_id: UUID,
    source_url: str | None,
) -> None:
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO event_sources (id, user_id, draft_id, source_url_raw, source_url_normalized, poster_asset_id, created_at)
            VALUES (:id, :user_id, :draft_id, :raw, :norm, :poster_asset_id, :created_at)
            ON CONFLICT (user_id, draft_id) DO UPDATE SET
              source_url_raw = EXCLUDED.source_url_raw,
              source_url_normalized = EXCLUDED.source_url_normalized,
              poster_asset_id = EXCLUDED.poster_asset_id
            """
        ),
        {
            "id": str(uuid4()),
            "user_id": str(user_id),
            "draft_id": str(draft_id),
            "raw": source_url,
            "norm": (source_url or "").split("?", 1)[0] if source_url else None,
            "poster_asset_id": str(poster_asset_id),
            "created_at": now,
        },
    )


def persist_poster_and_link_draft(
    *,
    session,
    poster_store: PosterStore,
    redis_client: redis.Redis | None,
    user_id: UUID,
    draft_id: UUID,
    image_bytes: bytes,
    content_type: str,
    source_url: str | None,
    parsed_snapshot: dict,
    model_version: str,
) -> UUID | None:
    """
    Dedupe by content SHA-256; store bytes in PosterStore; upsert poster_assets / parses / event_sources.
    parsed_snapshot: draft-like dict with title, start_time, venue, confidence_score, price.
    """
    if session is None:
        return None

    content_sha256_hex = hashlib.sha256(image_bytes).hexdigest()
    dh = dhash64(image_bytes)
    dh_hex = f"{dh:016x}"

    poster_asset_id_from_cache: UUID | None = None
    if redis_client is not None:
        cached_asset_id = redis_client.get(_poster_cache_key_sha256(content_sha256_hex))
        if cached_asset_id:
            try:
                poster_asset_id_from_cache = UUID(cached_asset_id.decode("utf-8"))
            except Exception:
                poster_asset_id_from_cache = None

    # Redis → validate SHA matches, reuse asset id.
    if poster_asset_id_from_cache is not None:
        sha_row = session.execute(
            text("SELECT content_sha256 FROM poster_assets WHERE id = :id"),
            {"id": str(poster_asset_id_from_cache)},
        ).first()
        if sha_row and sha_row[0] == content_sha256_hex:
            link_event_source_poster(
                session=session,
                user_id=user_id,
                draft_id=draft_id,
                poster_asset_id=poster_asset_id_from_cache,
                source_url=source_url,
            )
            return poster_asset_id_from_cache

    existing = session.execute(
        text("SELECT id FROM poster_assets WHERE content_sha256 = :sha"),
        {"sha": content_sha256_hex},
    ).first()
    if existing:
        poster_asset_id = UUID(str(existing[0]))
        link_event_source_poster(
            session=session,
            user_id=user_id,
            draft_id=draft_id,
            poster_asset_id=poster_asset_id,
            source_url=source_url,
        )
        if redis_client is not None:
            try:
                redis_client.set(_poster_cache_key_sha256(content_sha256_hex), str(poster_asset_id), ex=30 * 24 * 3600)
            except Exception as e:
                _log.warning("poster redis pointer set failed: %s", e)
        return poster_asset_id

    poster_id = poster_store.put(content_type=content_type or "application/octet-stream", image_bytes=image_bytes)
    now = datetime.now(timezone.utc)
    poster_asset_id = uuid4()
    session.execute(
        text(
            """
            INSERT INTO poster_assets (id, dhash64, content_sha256, poster_id, content_type, created_at)
            VALUES (:id, :dhash64, :content_sha256, :poster_id, :content_type, :created_at)
            """
        ),
        {
            "id": str(poster_asset_id),
            "dhash64": dh_hex,
            "content_sha256": content_sha256_hex,
            "poster_id": str(poster_id),
            "content_type": content_type or "application/octet-stream",
            "created_at": now,
        },
    )

    start_val = parsed_snapshot.get("start_time")
    start_iso = start_val.isoformat() if start_val is not None and hasattr(start_val, "isoformat") else None

    session.execute(
        text(
            """
            INSERT INTO poster_asset_parses (id, poster_asset_id, parsed_json, model_version, created_at)
            VALUES (:id, :poster_asset_id, :parsed_json, :model_version, :created_at)
            ON CONFLICT (poster_asset_id) DO UPDATE SET
              parsed_json = EXCLUDED.parsed_json,
              model_version = EXCLUDED.model_version,
              created_at = EXCLUDED.created_at
            """
        ),
        {
            "id": str(uuid4()),
            "poster_asset_id": str(poster_asset_id),
            "parsed_json": Json(
                {
                    "title": parsed_snapshot.get("title"),
                    "start_time": start_iso,
                    "venue": parsed_snapshot.get("venue"),
                    "confidence_score": parsed_snapshot.get("confidence_score"),
                    "price": _coerce_optional_price(parsed_snapshot.get("price")),
                }
            ),
            "model_version": model_version,
            "created_at": now,
        },
    )

    link_event_source_poster(
        session=session,
        user_id=user_id,
        draft_id=draft_id,
        poster_asset_id=poster_asset_id,
        source_url=source_url,
    )

    if redis_client is not None:
        try:
            redis_client.set(_poster_cache_key_sha256(content_sha256_hex), str(poster_asset_id), ex=30 * 24 * 3600)
        except Exception as e:
            _log.warning("poster redis pointer set failed: %s", e)

    return poster_asset_id
