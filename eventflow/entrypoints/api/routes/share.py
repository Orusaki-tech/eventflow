from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from google.genai.errors import APIError  # type: ignore
import httpx
import anyio
import functools
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID, uuid4
from pathlib import Path

import redis
from psycopg.types.json import Json
from sqlalchemy import text

from eventflow.domain import commands
from eventflow.domain.exceptions import DraftNotFound, InvariantViolation, PermissionDenied
from eventflow.entrypoints.api.schemas import (
    EventDraftResponse,
    EventDraftDetailResponse,
    InstagramCarouselPreviewResponse,
    InstagramCarouselPreviewSlide,
    ParseDraftFromImageRequest,
    ShareInstagramCarouselRequest,
    ShareMediaResponse,
    SharePosterResponse,
    ShareTextRequest,
    ShareUrlCarouselResponse,
    ShareUrlRequest,
)
from eventflow.entrypoints.dependencies import (
    get_current_user_id,
    get_gemini_client,
    get_image_token_store,
    get_poster_store,
    get_session,
    get_share_parse_cache,
    get_uow,
)
from eventflow.service_layer import handlers
from eventflow.adapters.gemini import _coerce_optional_price
from eventflow.adapters.image_token_store import ImageTokenStore
from eventflow.adapters.share_parse_cache import CachedParsedDraft, NoOpShareParseCache, ShareParseCache, normalize_shared_url
from eventflow.adapters.gemini_client import ParsedEventDraft
from eventflow.adapters.poster_fingerprint import dhash64
from eventflow.adapters.poster_store import PosterStore
from eventflow.adapters.share_preview_image import try_preview_image_bytes_for_share_url
from eventflow.config import get_settings
from eventflow.service_layer.poster_attachment import persist_poster_and_link_draft


router = APIRouter(tags=["Share"])
_log = logging.getLogger(__name__)


def _persist_or_merge_poster_parsed(
    *,
    target_draft_id: UUID | None,
    user_id: UUID,
    parsed: ParsedEventDraft,
    uow,
) -> dict:
    if target_draft_id is None:
        return handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed, uow=uow)
    try:
        return handlers.merge_poster_parse_into_draft(
            draft_id=target_draft_id,
            user_id=user_id,
            parsed=parsed,
            uow=uow,
        )
    except DraftNotFound:
        raise HTTPException(status_code=404, detail="Draft not found")
    except PermissionDenied:
        raise HTTPException(status_code=403, detail="Not your draft")
    except InvariantViolation as e:
        raise HTTPException(status_code=409, detail=str(e))


def _url_parse_log_key(url: str) -> str:
    return hashlib.sha256(normalize_shared_url(url).encode("utf-8")).hexdigest()[:16]


def _safe_fromisoformat(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _gemini_model_label() -> str:
    return getattr(get_settings(), "gemini_model", "unknown")


def upsert_shared_link_listing_approved(session, url: str, draft_out: dict, status: str = "approved", source_url: str | None = None) -> None:
    """Persist moderation-friendly listing metadata for URL ingestions."""
    norm = normalize_shared_url(url)
    st = draft_out.get("start_time")
    payload = {
        "title": draft_out.get("title"),
        "venue": draft_out.get("venue"),
        "confidence_score": draft_out.get("confidence_score"),
        "start_time": st.isoformat() if st is not None and hasattr(st, "isoformat") else None,
        "price": draft_out.get("price"),
    }
    session.execute(
        text(
            """
            INSERT INTO shared_link_listings (normalized_url, source_url_raw, status, cached_payload, created_at, updated_at)
            VALUES (:u, :raw, :st, CAST(:p AS jsonb), NOW(), NOW())
            ON CONFLICT (normalized_url) DO UPDATE SET
              cached_payload = CASE WHEN shared_link_listings.status IN ('approved', 'rejected') THEN shared_link_listings.cached_payload ELSE CAST(:p AS jsonb) END,
              status = CASE WHEN shared_link_listings.status IN ('approved', 'rejected') THEN shared_link_listings.status ELSE :st END,
              updated_at = NOW()
            """
        ),
        {"u": norm, "raw": source_url or url, "p": json.dumps(payload), "st": status},
    )


def _share_url_with_instagram_img_index(url: str, img_index: int) -> str:
    """Attach img_index to Instagram /p/ share URLs so poster provenance matches each carousel slide."""
    try:
        p = urlparse(url.strip())
        pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k not in ("img_index", "carousel_index")]
        pairs.append(("img_index", str(int(img_index))))
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(pairs), p.fragment))
    except Exception:
        return url


def _attach_share_url_preview_poster(
    *,
    uow,
    poster_store: PosterStore,
    user_id: UUID,
    source_url: str,
    draft_out: dict,
    session=None,
) -> dict:
    """
    Persist extracted preview bytes as poster_assets and drop transient handler keys
    so responses stay JSON-serializable.
    """
    image_bytes = draft_out.get("_share_preview_image_bytes")
    content_type = draft_out.get("_share_preview_content_type")
    try:
        if image_bytes and content_type:
            settings = get_settings()
            if settings.effective_db_url:
                redis_client = None
                if settings.redis_url:
                    try:
                        redis_client = redis.Redis.from_url(settings.redis_url)
                    except Exception:
                        redis_client = None
                with uow:
                    sess = getattr(uow, "session", None)
                    if sess is not None:
                        pid = persist_poster_and_link_draft(
                            session=sess,
                            poster_store=poster_store,
                            redis_client=redis_client,
                            user_id=user_id,
                            draft_id=draft_out["draft_id"],
                            image_bytes=image_bytes,
                            content_type=content_type,
                            source_url=source_url,
                            parsed_snapshot=draft_out,
                            model_version=_gemini_model_label(),
                        )
                        uow.commit()
                        if pid:
                            draft_out["poster_asset_id"] = pid
    except Exception as e:
        _log.warning("share_url preview poster attachment failed: %s", e)
    finally:
        draft_out.pop("_share_preview_image_bytes", None)
        draft_out.pop("_share_preview_content_type", None)
    if session is not None:
        try:
            upsert_shared_link_listing_approved(session, source_url, draft_out)
            session.commit()
        except Exception as exc:
            _log.warning("shared_link_listings upsert failed: %s", exc)
    return draft_out


def try_share_url_from_community_listing_alias(
    *,
    session,
    normalized_url: str,
    user_id: UUID,
    uow,
    poster_store: PosterStore,
    source_url: str,
) -> dict | None:
    """Registered listing alias: hydrate draft from ``community_events`` (skip Gemini)."""
    row = session.execute(
        text(
            """
            SELECT e.title, e.start_time, e.venue, e.poster_image_uri
            FROM community_event_share_aliases a
            INNER JOIN community_events e ON e.id = a.community_event_id
            WHERE a.normalized_url = :u
            LIMIT 1
            """
        ),
        {"u": normalized_url},
    ).first()
    if row is None:
        return None
    title, start_time, venue, poster_uri = row[0], row[1], row[2], row[3]
    if start_time is None:
        return None
    parsed = ParsedEventDraft(
        title=str(title or "Event"),
        start_time=start_time,
        venue=str(venue or ""),
        confidence_score=1.0,
        price=None,
    )
    out = handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed, uow=uow)
    uri_str = str(poster_uri).strip() if poster_uri else ""
    if uri_str.lower().startswith(("http://", "https://")):
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                r = client.get(uri_str)
                if r.status_code == 200 and r.content:
                    ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
                    if ct.startswith("image/"):
                        out["_share_preview_image_bytes"] = r.content
                        out["_share_preview_content_type"] = ct
        except Exception as exc:
            _log.warning(
                "community_listing_alias poster fetch failed url_key=%s err=%s",
                _url_parse_log_key(source_url),
                exc,
            )
    _log.info(
        "share_url_parse listing_alias_hit url_key=%s",
        _url_parse_log_key(source_url),
    )
    return _attach_share_url_preview_poster(
        uow=uow,
        poster_store=poster_store,
        user_id=user_id,
        source_url=source_url,
        draft_out=out,
        session=session,
    )


@router.post("/share/url", status_code=status.HTTP_201_CREATED, response_model=EventDraftResponse)
async def share_url(
    body: ShareUrlRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
    poster_store: PosterStore = Depends(get_poster_store),
    cache: ShareParseCache | NoOpShareParseCache = Depends(get_share_parse_cache),
    session=Depends(get_session),
):
    norm = normalize_shared_url(body.url)
    if session is not None:
        # Query returns (status, cached_payload) — both checks below depend on this shape.
        row = session.execute(
            text("SELECT status, cached_payload FROM shared_link_listings WHERE normalized_url = :u LIMIT 1"),
            {"u": norm},
        ).first()
        if row is not None and row[0] == "rejected":
            raise HTTPException(
                status_code=409,
                detail="This shared link was rejected. Enter event details manually.",
            )

        # Admin-approved link — use cached_payload (row[1]) directly, skip model.
        # Note: row[0]=status, row[1]=cached_payload — see query above.
        if row is not None and row[0] == "approved" and row[1] is not None:
            _log.info(
                "share_url_parse admin_approved url_key=%s",
                _url_parse_log_key(body.url),
            )
            payload = row[1]
            parsed_adm = ParsedEventDraft(
                title=str(payload.get("title") or ""),
                start_time=_safe_fromisoformat(payload.get("start_time")),
                venue=str(payload.get("venue") or ""),
                confidence_score=1.0,
                price=payload.get("price"),
            )
            out_adm = handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed_adm, uow=uow)
            preview_adm = try_preview_image_bytes_for_share_url(body.url)
            if preview_adm:
                out_adm["_share_preview_image_bytes"] = preview_adm[0]
                out_adm["_share_preview_content_type"] = preview_adm[1]
            return _attach_share_url_preview_poster(
                uow=uow,
                poster_store=poster_store,
                user_id=user_id,
                source_url=body.url,
                draft_out=out_adm,
                session=session,
            )

        alias_out = try_share_url_from_community_listing_alias(
            session=session,
            normalized_url=norm,
            user_id=user_id,
            uow=uow,
            poster_store=poster_store,
            source_url=body.url,
        )
        if alias_out is not None:
            return alias_out

    cached = cache.get(url=body.url)
    cached_start = _safe_fromisoformat(getattr(cached, "start_time_iso", None)) if cached is not None else None
    if cached is not None and cached_start is not None:
        _log.info(
            "share_url_parse cache_hit url_key=%s",
            _url_parse_log_key(body.url),
        )
        parsed = ParsedEventDraft(
            title=cached.title,
            start_time=cached_start,
            venue=cached.venue,
            confidence_score=float(cached.confidence_score),
            price=cached.price,
        )
        out = handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed, uow=uow)
        preview = try_preview_image_bytes_for_share_url(body.url)
        if preview:
            out["_share_preview_image_bytes"] = preview[0]
            out["_share_preview_content_type"] = preview[1]
        return _attach_share_url_preview_poster(
            uow=uow,
            poster_store=poster_store,
            user_id=user_id,
            source_url=body.url,
            draft_out=out,
            session=session,
        )

    _log.info(
        "share_url_parse cache_miss url_key=%s",
        _url_parse_log_key(body.url),
    )

    # Stampede protection: only one request does the Gemini call for a URL at a time.
    owner = uuid4().hex
    if not cache.try_acquire_lock(url=body.url, owner=owner):
        # Another worker is parsing; try the cache one more time after a short delay.
        # (We avoid importing asyncio at module import time; FastAPI runs this in an event loop.)
        import asyncio

        await asyncio.sleep(0.6)
        cached2 = cache.get(url=body.url)
        cached2_start = _safe_fromisoformat(getattr(cached2, "start_time_iso", None)) if cached2 is not None else None
        if cached2 is not None and cached2_start is not None:
            _log.info(
                "share_url_parse lock_contended_then_cache_hit url_key=%s",
                _url_parse_log_key(body.url),
            )
            parsed2 = ParsedEventDraft(
                title=cached2.title,
                start_time=cached2_start,
                venue=cached2.venue,
                confidence_score=float(cached2.confidence_score),
                price=cached2.price,
            )
            out2 = handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed2, uow=uow)
            preview2 = try_preview_image_bytes_for_share_url(body.url)
            if preview2:
                out2["_share_preview_image_bytes"] = preview2[0]
                out2["_share_preview_content_type"] = preview2[1]
            return _attach_share_url_preview_poster(
                uow=uow,
                poster_store=poster_store,
                user_id=user_id,
                source_url=body.url,
                draft_out=out2,
                session=session,
            )
        _log.info(
            "share_url_parse lock_contended_no_cache_yet url_key=%s",
            _url_parse_log_key(body.url),
        )

    try:
        _log.info(
            "share_url_parse gemini_invoke url_key=%s",
            _url_parse_log_key(body.url),
        )
        out = handlers.handle_capture_event_url(commands.CaptureEventUrl(user_id=user_id, url=body.url), uow, gemini=gemini)
        out = _attach_share_url_preview_poster(
            uow=uow,
            poster_store=poster_store,
            user_id=user_id,
            source_url=body.url,
            draft_out=out,
            session=session,
        )
        # Store parsed fields for reuse; we cache the final structured values (not draft_id).
        cache.put(
            url=body.url,
            parsed=CachedParsedDraft(
                title=str(out.get("title") or ""),
                start_time_iso=str(out.get("start_time").isoformat() if out.get("start_time") else ""),
                venue=str(out.get("venue") or ""),
                confidence_score=float(out.get("confidence_score") or 0.0),
                price=out.get("price"),
            ),
        )
        return out
    except InvariantViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except APIError as e:
        # Surface as a dependency/upstream failure (invalid key, quota, etc.)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")


@router.post(
    "/share/url/instagram-carousel",
    status_code=status.HTTP_201_CREATED,
    response_model=ShareUrlCarouselResponse,
)
async def share_instagram_carousel_url(
    body: ShareInstagramCarouselRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
    poster_store: PosterStore = Depends(get_poster_store),
):
    try:
        rows, slides_used = handlers.handle_capture_instagram_carousel_url(
            user_id=user_id,
            url=body.url,
            uow=uow,
            gemini=gemini,
            carousel_slide_indices=body.carousel_slide_indices,
        )
        sealed: list[dict] = []
        for i, r in enumerate(rows):
            slide = slides_used[i] if i < len(slides_used) else i + 1
            src = _share_url_with_instagram_img_index(body.url, slide)
            sealed.append(
                _attach_share_url_preview_poster(
                    uow=uow,
                    poster_store=poster_store,
                    user_id=user_id,
                    source_url=src,
                    draft_out=r,
                )
            )
        drafts = [EventDraftResponse.model_validate(x) for x in sealed]
        return ShareUrlCarouselResponse(drafts=drafts, slides_used=slides_used)
    except InvariantViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")


@router.post(
    "/share/url/instagram-carousel-preview",
    status_code=status.HTTP_200_OK,
    response_model=InstagramCarouselPreviewResponse,
)
async def instagram_carousel_preview(
    body: ShareUrlRequest,
    _user_id=Depends(get_current_user_id),
    store: ImageTokenStore = Depends(get_image_token_store),
):
    """Fetch all Instagram /p/ carousel slide images as short-lived tokens for client preview and selection."""
    try:
        t0 = datetime.now(timezone.utc)
        _log.info("instagram_carousel_preview start url_key=%s", _url_parse_log_key(body.url))
        # Hard stop so mobile never waits forever.
        with anyio.fail_after(18):
            slides_data = await anyio.to_thread.run_sync(
                functools.partial(handlers.instagram_carousel_preview_slide_bytes, url=body.url),
                cancellable=True,
            )
        dt_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
        _log.info(
            "instagram_carousel_preview ok url_key=%s slides=%s ms=%s",
            _url_parse_log_key(body.url),
            len(slides_data),
            dt_ms,
        )
    except InvariantViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Carousel preview timed out. Try again (or continue without slide picker).",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Carousel preview failed: {type(e).__name__}: {e}",
        )

    slides = [
        InstagramCarouselPreviewSlide(
            slide_index=idx,
            image_token=store.put(content_type=ct, image_bytes=blob),
        )
        for idx, blob, ct in slides_data
    ]
    return InstagramCarouselPreviewResponse(slides=slides)


@router.post(
    "/share/url/parse-image",
    status_code=status.HTTP_200_OK,
    response_model=EventDraftDetailResponse,
)
async def parse_draft_from_image(
    body: ParseDraftFromImageRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
    store: ImageTokenStore = Depends(get_image_token_store),
    poster_store: PosterStore = Depends(get_poster_store),
):
    img = store.get(token=body.image_token)
    if img is None:
        raise HTTPException(status_code=404, detail="Image token expired or not found")

    try:
        parsed_ev = gemini.parse_event_image(image_bytes=img.image_bytes, content_type=img.content_type)
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")

    try:
        merged = handlers.merge_poster_parse_into_draft(
            draft_id=body.draft_id,
            user_id=user_id,
            parsed=parsed_ev,
            uow=uow,
        )
    except DraftNotFound:
        raise HTTPException(status_code=404, detail="Draft not found")
    except PermissionDenied:
        raise HTTPException(status_code=403, detail="Not your draft")
    except InvariantViolation as e:
        raise HTTPException(status_code=409, detail=str(e))

    poster_asset_id = None
    settings = get_settings()
    if settings.effective_db_url:
        redis_client = None
        if settings.redis_url:
            try:
                redis_client = redis.Redis.from_url(settings.redis_url)
            except Exception:
                redis_client = None
        try:
            with uow:
                sess = getattr(uow, "session", None)
                if sess is not None:
                    poster_asset_id = persist_poster_and_link_draft(
                        session=sess,
                        poster_store=poster_store,
                        redis_client=redis_client,
                        user_id=user_id,
                        draft_id=body.draft_id,
                        image_bytes=img.image_bytes,
                        content_type=img.content_type,
                        source_url=None,
                        parsed_snapshot=merged,
                        model_version=_gemini_model_label(),
                    )
                    uow.commit()
        except Exception as e:
            _log.warning("parse-image poster persist failed: %s", e)

    return EventDraftDetailResponse(**merged, poster_asset_id=poster_asset_id)


@router.post("/share/text", status_code=status.HTTP_201_CREATED, response_model=EventDraftResponse)
async def share_text(
    body: ShareTextRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
):
    try:
        return handlers.handle_capture_event_text(commands.CaptureEventText(user_id=user_id, text=body.text), uow, gemini=gemini)
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")


@router.post("/share/image", status_code=status.HTTP_201_CREATED, response_model=EventDraftResponse)
async def share_image(
    file: UploadFile = File(...),
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        return handlers.handle_capture_event_upload_image(
            commands.CaptureEventUploadImage(user_id=user_id, image_bytes=image_bytes),
            uow,
            gemini=gemini,
        )
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")


@router.post("/share/media", status_code=status.HTTP_201_CREATED, response_model=ShareMediaResponse)
async def share_media(
    file: UploadFile = File(...),
    source_text: str | None = Form(default=None),
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
):
    ct = (file.content_type or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    if ct.startswith("image/"):
        try:
            out = handlers.handle_capture_event_upload_image(
                commands.CaptureEventUploadImage(user_id=user_id, image_bytes=raw),
                uow,
                gemini=gemini,
            )
            return ShareMediaResponse(**out, media_kind="image", media_id=None)
        except APIError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {e}")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed (network): {e}")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI parsing failed: {type(e).__name__}: {e}")

    if ct.startswith("video/"):
        # Durable store (filesystem) + create a minimal draft. Video parsing can be added later.
        base = Path(get_settings().poster_storage_dir).expanduser().resolve()
        vdir = base / "videos"
        vdir.mkdir(parents=True, exist_ok=True)
        vid = uuid4()
        (vdir / f"{vid}.bin").write_bytes(raw)
        (vdir / f"{vid}.ct").write_text(ct or "application/octet-stream", encoding="utf-8")
        parsed = ParsedEventDraft(
            title="Shared video",
            start_time=None,
            venue="",
            confidence_score=0.1,
            price=None,
        )
        out = handlers.persist_draft_from_parsed(user_id=user_id, parsed=parsed, uow=uow)
        # Best-effort: store text provenance in memory only for now (mobile also stores locally).
        _ = source_text
        return ShareMediaResponse(**out, media_kind="video", media_id=vid)

    raise HTTPException(status_code=400, detail="file must be an image or video")


def _redis_for_posters(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


def _poster_cache_key_sha256(content_sha256_hex: str) -> str:
    """Redis pointer from exact poster bytes → poster_assets.id (parse reuse only on identical upload)."""
    return f"eventflow:poster:sha256:{content_sha256_hex}"


@router.post("/share/poster", status_code=status.HTTP_201_CREATED, response_model=SharePosterResponse)
async def share_poster(
    file: UploadFile = File(...),
    source_url: str | None = Form(default=None),
    draft_id: str | None = Form(default=None),
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
    gemini=Depends(get_gemini_client),
    store: PosterStore = Depends(get_poster_store),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty file")

    target_draft_id: UUID | None = None
    if isinstance(draft_id, str) and draft_id.strip():
        try:
            target_draft_id = UUID(draft_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="draft_id must be a UUID")

    content_sha256_hex = hashlib.sha256(image_bytes).hexdigest()
    dh = dhash64(image_bytes)
    dh_hex = f"{dh:016x}"

    from eventflow.config import get_settings

    settings = get_settings()
    if not settings.redis_url:
        raise HTTPException(status_code=500, detail="Redis not configured")
    if not settings.effective_db_url:
        raise HTTPException(status_code=500, detail="DB not configured")

    r = _redis_for_posters(settings.redis_url)
    cached_asset_id = r.get(_poster_cache_key_sha256(content_sha256_hex))
    poster_asset_id_from_cache: UUID | None = None
    if cached_asset_id:
        try:
            poster_asset_id_from_cache = UUID(cached_asset_id.decode("utf-8"))
        except Exception:
            poster_asset_id_from_cache = None

    def _link_source(*, poster_asset_id: UUID, draft_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        uow.session.execute(
            text(
                """
                INSERT INTO event_sources (id, user_id, draft_id, source_url_raw, source_url_normalized, poster_asset_id, created_at, updated_at)
                VALUES (:id, :user_id, :draft_id, :raw, :norm, :poster_asset_id, :created_at, :created_at)
                ON CONFLICT (user_id, draft_id) DO UPDATE SET
                  source_url_raw = EXCLUDED.source_url_raw,
                  source_url_normalized = EXCLUDED.source_url_normalized,
                  poster_asset_id = EXCLUDED.poster_asset_id,
                  updated_at = NOW()
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

    def _load_parsed(poster_asset_id: UUID) -> ParsedEventDraft | None:
        row = uow.session.execute(
            text("SELECT p.parsed_json FROM poster_asset_parses p WHERE p.poster_asset_id = :pid"),
            {"pid": str(poster_asset_id)},
        ).first()
        if not row or not isinstance(row[0], dict):
            return None
        pj = row[0]
        start_iso = pj.get("start_time")
        start_dt = None
        if isinstance(start_iso, str) and start_iso.strip():
            try:
                start_dt = datetime.fromisoformat(start_iso.strip().replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
            except Exception:
                start_dt = None
        title = str(pj.get("title") or "").strip()
        venue = str(pj.get("venue") or "").strip()
        if not title and not venue:
            return None
        return ParsedEventDraft(
            title=title or "Event",
            start_time=start_dt,
            venue=venue or "Unknown venue",
            confidence_score=float(pj.get("confidence_score") or 0.8),
            price=_coerce_optional_price(pj.get("price")),
        )

    # Cache hit: validate Redis points at a row for these exact bytes, then reuse stored parse.
    if poster_asset_id_from_cache is not None:
        with uow:
            sha_row = uow.session.execute(
                text("SELECT content_sha256 FROM poster_assets WHERE id = :id"),
                {"id": str(poster_asset_id_from_cache)},
            ).first()
            if sha_row and sha_row[0] == content_sha256_hex:
                parsed = _load_parsed(poster_asset_id_from_cache)
                if parsed is not None:
                    out = _persist_or_merge_poster_parsed(
                        target_draft_id=target_draft_id,
                        user_id=user_id,
                        parsed=parsed,
                        uow=uow,
                    )
                    _link_source(poster_asset_id=poster_asset_id_from_cache, draft_id=out["draft_id"])
                    uow.commit()
                    return SharePosterResponse(
                        draft_id=out["draft_id"],
                        title=out["title"],
                        start_time=out["start_time"],
                        venue=out["venue"],
                        confidence_score=out["confidence_score"],
                        poster_asset_id=poster_asset_id_from_cache,
                        source_url_raw=source_url,
                        price=out.get("price"),
                    )

    # Cache miss: persist poster + parse with Gemini once.
    with uow:
        # DB check (cold Redis). Reuse parse only when this exact image was uploaded before.
        existing = uow.session.execute(
            text("SELECT id FROM poster_assets WHERE content_sha256 = :sha"),
            {"sha": content_sha256_hex},
        ).first()
        if existing:
            poster_asset_id = existing[0]
            parsed = _load_parsed(poster_asset_id)
            if parsed is not None:
                out = _persist_or_merge_poster_parsed(
                    target_draft_id=target_draft_id,
                    user_id=user_id,
                    parsed=parsed,
                    uow=uow,
                )
                _link_source(poster_asset_id=poster_asset_id, draft_id=out["draft_id"])
                uow.commit()
                r.set(_poster_cache_key_sha256(content_sha256_hex), str(poster_asset_id), ex=30 * 24 * 3600)
                return SharePosterResponse(
                    draft_id=out["draft_id"],
                    title=out["title"],
                    start_time=out["start_time"],
                    venue=out["venue"],
                    confidence_score=out["confidence_score"],
                    poster_asset_id=poster_asset_id,
                    source_url_raw=source_url,
                    price=out.get("price"),
                )

        poster_id = store.put(content_type=file.content_type or "application/octet-stream", image_bytes=image_bytes)
        now = datetime.now(timezone.utc)
        poster_asset_id = uuid4()
        uow.session.execute(
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
                "content_type": file.content_type or "application/octet-stream",
                "created_at": now,
            },
        )

        if target_draft_id is not None:
            if gemini is None:
                raise HTTPException(status_code=500, detail="Gemini client not configured")
            parsed_img = gemini.parse_event_image(image_bytes=image_bytes, content_type=file.content_type)
            out = _persist_or_merge_poster_parsed(
                target_draft_id=target_draft_id,
                user_id=user_id,
                parsed=parsed_img,
                uow=uow,
            )
        else:
            out = handlers.handle_capture_event_upload_image(
                commands.CaptureEventUploadImage(user_id=user_id, image_bytes=image_bytes),
                uow,
                gemini=gemini,
            )

        # Persist parsed payload for reuse.
        uow.session.execute(
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
                        "title": out.get("title"),
                        "start_time": out.get("start_time").isoformat() if out.get("start_time") else None,
                        "venue": out.get("venue"),
                        "confidence_score": out.get("confidence_score"),
                        "price": out.get("price"),
                    }
                ),
                "model_version": getattr(settings, "gemini_model", "unknown"),
                "created_at": now,
            },
        )

        # Link this user's draft to the poster + source URL.
        _link_source(poster_asset_id=poster_asset_id, draft_id=out["draft_id"])
        uow.commit()

    r.set(_poster_cache_key_sha256(content_sha256_hex), str(poster_asset_id), ex=30 * 24 * 3600)

    return SharePosterResponse(
        draft_id=out["draft_id"],
        title=out["title"],
        start_time=out["start_time"],
        venue=out["venue"],
        confidence_score=out["confidence_score"],
        poster_asset_id=poster_asset_id,
        source_url_raw=source_url,
        price=out.get("price"),
    )


@router.post("/share/ics", status_code=status.HTTP_201_CREATED, response_model=EventDraftResponse)
async def share_ics(
    file: UploadFile = File(...),
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    ics_bytes = await file.read()
    if not ics_bytes:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        return handlers.handle_capture_event_ics(commands.CaptureEventIcs(user_id=user_id, ics_bytes=ics_bytes), uow)
    except InvariantViolation as e:
        raise HTTPException(status_code=400, detail=str(e))

