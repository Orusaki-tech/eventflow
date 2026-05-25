from __future__ import annotations

import logging
import re
import ssl
import json
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

import certifi
from fastapi import APIRouter, Depends, HTTPException, Query, status
from starlette.responses import Response
from sqlalchemy import text

from eventflow.adapters import media_extractor
from eventflow.adapters.share_preview_image import _extract_og_image_url, try_instagram_embed_slide_bytes
from eventflow.adapters.image_token_store import ImageTokenStore
from eventflow.adapters.poster_store import PosterStore
from eventflow.domain.exceptions import InvariantViolation
from eventflow.entrypoints.api.schemas import ResolveImageRequest, ResolveImageResponse
from eventflow.entrypoints.dependencies import get_image_token_store, get_poster_store, get_session, get_current_user_id
from eventflow.service_layer.handlers import _is_private_address


router = APIRouter(tags=["Media"])
_log_media = logging.getLogger(__name__)


def _fetch_html_text(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 1_000_000) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolation("Only http/https URLs are supported")
    if not parsed.netloc:
        raise InvariantViolation("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise InvariantViolation("URL host is not allowed")

    req = Request(
        url,
        headers={
            # Instagram is sensitive to headers; a realistic UA helps.
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )

    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
        with opener.open(req, timeout=timeout_seconds) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            return raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        # Fetch failures are upstream errors, not client input errors.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e.code})")
    except URLError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e})")


def _fetch_json(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 1_000_000) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolation("Only http/https URLs are supported")
    if not parsed.netloc:
        raise InvariantViolation("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise InvariantViolation("URL host is not allowed")

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
        with opener.open(req, timeout=timeout_seconds) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            obj = json.loads(raw.decode("utf-8", errors="replace"))
            return obj if isinstance(obj, dict) else {}
    except HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e.code})")
    except URLError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e})")
    except Exception:
        _log_media.exception("_fetch_json failed for URL")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="URL fetch failed")


def _linkedin_oembed_thumbnail_url(shared_url: str) -> str | None:
    """
    LinkedIn often blocks direct HTML fetches with 403. Their oEmbed endpoint
    sometimes returns a `thumbnail_url` for public posts.
    """
    oembed_url = "https://www.linkedin.com/oembed?" + urlencode({"url": shared_url, "format": "json"})
    data = _fetch_json(url=oembed_url)
    thumb = data.get("thumbnail_url")
    return thumb if isinstance(thumb, str) and thumb.startswith(("https://", "http://")) else None


def _fetch_image_bytes(
    *,
    url: str,
    timeout_seconds: float = 5.0,
    max_bytes: int = 5_000_000,
    extra_headers: dict[str, str] | None = None,
) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolation("Only http/https URLs are supported")
    if not parsed.netloc:
        raise InvariantViolation("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise InvariantViolation("URL host is not allowed")

    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if extra_headers:
        for k, v in extra_headers.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                headers[k] = v

    req = Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
        with opener.open(req, timeout=timeout_seconds) as resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/"):
                raise InvariantViolation("Remote resource is not an image")

            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise InvariantViolation("Image too large")
            return raw, content_type or "application/octet-stream"
    except HTTPError as e:
        # Fetch failures are upstream errors, not client input errors.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e.code})")
    except URLError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"URL fetch failed ({e})")


def _resolve_preview_image_bytes(shared_url: str) -> tuple[bytes, str]:
    """
    Resolve a shared social/video URL into a concrete preview image (bytes + content-type).
    This mirrors the logic of `/media/thumbnail` but returns bytes for token storage.
    """
    if not media_extractor.supports_url(shared_url):
        raise InvariantViolation("Unsupported URL for thumbnail extraction")

    parsed = urlparse(shared_url)
    host = (parsed.hostname or "").lower()
    if host and (host == "instagram.com" or host.endswith(".instagram.com")):
        embed_slide = try_instagram_embed_slide_bytes(shared_url)
        if embed_slide:
            return embed_slide

    try:
        meta = media_extractor.extract(shared_url)
        if not meta.thumbnail_url:
            raise InvariantViolation("No thumbnail found")
        return _fetch_image_bytes(url=meta.thumbnail_url, extra_headers=meta.thumbnail_request_headers)
    except Exception:
        _log_media.warning("yt-dlp extraction failed, falling back to OG/legacy for url", exc_info=True)
        host = (urlparse(shared_url).hostname or "").lower()
        if host and (host == "instagram.com" or host.endswith(".instagram.com")):
            legacy = media_extractor.instagram_legacy_media_fetch_params(shared_url)
            if legacy:
                legacy_media_url, legacy_headers = legacy
                return _fetch_image_bytes(url=legacy_media_url, extra_headers=legacy_headers)

            # og:image/tw:image fallback (e.g. /reel/ or unsupported paths)
            html = _fetch_html_text(url=shared_url)
            og_image = _extract_og_image_url(html)
            if not og_image:
                raise InvariantViolation("No image found")
            return _fetch_image_bytes(url=og_image, extra_headers={"Referer": shared_url})

        if host and (host == "linkedin.com" or host.endswith(".linkedin.com")):
            oembed_thumb = _linkedin_oembed_thumbnail_url(shared_url)
            if oembed_thumb:
                return _fetch_image_bytes(url=oembed_thumb, extra_headers={"Referer": shared_url})

            html = _fetch_html_text(url=shared_url)
            og_image = _extract_og_image_url(html)
            if not og_image:
                raise InvariantViolation("No image found")
            return _fetch_image_bytes(url=og_image, extra_headers={"Referer": shared_url})

        raise


@router.post("/media/resolve-image", status_code=status.HTTP_200_OK, response_model=ResolveImageResponse)
def resolve_image(
    body: ResolveImageRequest,
    user_id=Depends(get_current_user_id),
    store: ImageTokenStore = Depends(get_image_token_store),
):
    try:
        image_bytes, content_type = _resolve_preview_image_bytes(body.url)
        token = store.put(content_type=content_type, image_bytes=image_bytes)
        return ResolveImageResponse(image_token=token)
    except InvariantViolation as e:
        host = ""
        try:
            host = urlparse(body.url).hostname or ""
        except Exception:
            _log_media.exception("Failed to parse hostname from URL for diagnostic logging")
        _log_media.warning("resolve_image_bad_request host=%s detail=%s", host, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        _log_media.exception("resolve_image unexpected failure for URL")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Image resolve failed")


@router.get("/media/image", response_class=Response)
def get_image(
    token: str = Query(..., min_length=8),
    user_id=Depends(get_current_user_id),
    store: ImageTokenStore = Depends(get_image_token_store),
):
    img = store.get(token=token)
    if img is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image token expired or not found")
    return Response(content=img.image_bytes, media_type=img.content_type, headers={"Cache-Control": "private, max-age=600"})


@router.get("/media/poster/{poster_asset_id}", response_class=Response)
def get_poster(
    poster_asset_id: UUID,
    user_id=Depends(get_current_user_id),
    session=Depends(get_session),
    store: PosterStore = Depends(get_poster_store),
):
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DB not configured")
    row = session.execute(
        text("SELECT poster_id, content_type FROM poster_assets WHERE id = :id LIMIT 1"),
        {"id": str(poster_asset_id)},
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster not found")
    content_type = row[1]
    img = store.get(poster_id=poster_asset_id)
    if img is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster not found")
    return Response(content=img.image_bytes, media_type=content_type or img.content_type, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/media/thumbnail", response_class=Response)
def get_thumbnail(
    url: str = Query(..., description="Original shared URL (YouTube/TikTok/etc.)."),
    user_id=Depends(get_current_user_id),
):
    if not media_extractor.supports_url(url):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported URL for thumbnail extraction")

    try:
        meta = media_extractor.extract(url)
    except Exception:
        # Some providers (notably Instagram/LinkedIn) may fail extraction due to auth/rate limits
        # or content type mismatches. Fall back to OpenGraph image extraction for known hosts.
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host and (host == "instagram.com" or host.endswith(".instagram.com")):
            try:
                legacy = media_extractor.instagram_legacy_media_fetch_params(url)
                if legacy:
                    legacy_media_url, legacy_headers = legacy
                    image_bytes, content_type = _fetch_image_bytes(url=legacy_media_url, extra_headers=legacy_headers)
                    return Response(
                        content=image_bytes,
                        media_type=content_type,
                        headers={"Cache-Control": "public, max-age=3600"},
                    )

                # Fallback: parse HTML for OpenGraph/Twitter image.
                html = _fetch_html_text(url=url)
                og_image = _extract_og_image_url(html)
                if not og_image:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No image found")
                image_bytes, content_type = _fetch_image_bytes(url=og_image, extra_headers={"Referer": url})
                return Response(
                    content=image_bytes,
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=3600"},
                )
            except HTTPException:
                raise
            except InvariantViolation as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                _log_media.warning("get_thumbnail instagram fallback failed: %s", e, exc_info=True)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Thumbnail extraction failed: {type(e).__name__}")

        if host and (host == "linkedin.com" or host.endswith(".linkedin.com")):
            try:
                oembed_thumb = _linkedin_oembed_thumbnail_url(url)
                if oembed_thumb:
                    image_bytes, content_type = _fetch_image_bytes(url=oembed_thumb, extra_headers={"Referer": url})
                    return Response(
                        content=image_bytes,
                        media_type=content_type,
                        headers={"Cache-Control": "public, max-age=3600"},
                    )

                html = _fetch_html_text(url=url)
                og_image = _extract_og_image_url(html)
                if not og_image:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No image found")
                image_bytes, content_type = _fetch_image_bytes(url=og_image, extra_headers={"Referer": url})
                return Response(
                    content=image_bytes,
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=3600"},
                )
            except HTTPException:
                raise
            except InvariantViolation as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                _log_media.warning("get_thumbnail linkedin fallback failed: %s", e, exc_info=True)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Thumbnail extraction failed: {type(e).__name__}")

        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Thumbnail extraction failed")

    if not meta.thumbnail_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No thumbnail found")

    try:
        image_bytes, content_type = _fetch_image_bytes(
            url=meta.thumbnail_url,
            extra_headers=meta.thumbnail_request_headers,
        )
    except InvariantViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _log_media.warning("get_thumbnail fetch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Thumbnail fetch failed: {type(e).__name__}")

    return Response(
        content=image_bytes,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )

