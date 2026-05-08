"""
Best-effort preview image extraction for shared URLs (SLA: persist visuals users can correct against).

Used by share ingestion so we fetch thumbnails / og:image even when Gemini runs on text only,
and prefer Gemini vision when bytes are available.
"""

from __future__ import annotations

import ipaddress
import json
import re
import ssl
from urllib.parse import parse_qs, urlparse, urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

import certifi

from eventflow.adapters import media_extractor


def _is_private_address(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        lowered = host.lower()
        return lowered in {"localhost"} or lowered.endswith(".localhost")


def _extract_og_image_url(html: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            u = (m.group(1) or "").strip()
            if u.startswith("http://") or u.startswith("https://"):
                return u
    return None


def _fetch_html_raw(*, url: str, timeout_seconds: float = 8.0, max_bytes: int = 1_500_000) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise ValueError("URL host is not allowed")

    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout_seconds) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        return raw.decode("utf-8", errors="replace")


def _fetch_json_dict(*, url: str, timeout_seconds: float = 8.0, max_bytes: int = 800_000) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise ValueError("URL host is not allowed")

    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout_seconds) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        return obj if isinstance(obj, dict) else {}


def _linkedin_oembed_thumbnail_url(shared_url: str) -> str | None:
    oembed_url = "https://www.linkedin.com/oembed?" + urlencode({"url": shared_url, "format": "json"})
    try:
        data = _fetch_json_dict(url=oembed_url)
    except Exception:
        return None
    thumb = data.get("thumbnail_url")
    return thumb if isinstance(thumb, str) and thumb.startswith(("https://", "http://")) else None


def _fetch_remote_image_bytes(
    *,
    url: str,
    extra_headers: dict[str, str] | None = None,
    timeout_seconds: float = 25.0,
    max_bytes: int = 15_000_000,
) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise ValueError("URL host is not allowed")

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

    req = Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout_seconds) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("Image too large")
        content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        looks_image = (
            raw.startswith(b"\xff\xd8\xff")
            or raw.startswith(b"\x89PNG\r\n\x1a\n")
            or (len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
        )
        if not content_type.startswith("image/") and not looks_image:
            raise ValueError("Remote resource is not an image")
        return raw, content_type or "application/octet-stream"


def _instagram_requested_slide_index(shared_url: str) -> int:
    """1-based slide index from img_index / carousel_index query (Instagram /p/ shares)."""
    try:
        q = parse_qs(urlparse(shared_url).query)
        for key in ("img_index", "carousel_index"):
            vals = q.get(key)
            if not vals:
                continue
            try:
                n = int(str(vals[0]).strip())
                if n >= 1:
                    return n
            except ValueError:
                continue
    except Exception:
        pass
    return 1


def try_instagram_embed_slide_bytes(shared_url: str) -> tuple[bytes, str] | None:
    """
    Full-resolution slide from Instagram's public /embed/ HTML (sidecar CDN URLs).

    Matches mobile carousel preview quality. Honors img_index / carousel_index when multiple slides exist.
    Returns None for fetch/parse failures or when embed has no sidecar URLs (caller falls back to legacy/yt-dlp).
    """
    if not media_extractor.instagram_post_shortcode(shared_url):
        return None
    try:
        embed_html = media_extractor.fetch_instagram_post_embed_html(page_url=shared_url)
    except Exception:
        return None
    urls = media_extractor.instagram_carousel_image_urls_from_embed_html(embed_html)
    if not urls:
        return None
    shortcode = media_extractor.instagram_post_shortcode(shared_url)
    referer = f"https://www.instagram.com/p/{shortcode}/" if shortcode else shared_url.split("#", 1)[0]
    want = _instagram_requested_slide_index(shared_url)
    idx = min(want, len(urls)) - 1
    try:
        return _fetch_remote_image_bytes(url=urls[idx], extra_headers={"Referer": referer})
    except Exception:
        return None


def _instagram_og_or_legacy(shared_url: str) -> tuple[bytes, str] | None:
    legacy = media_extractor.instagram_legacy_media_fetch_params(shared_url)
    if legacy:
        legacy_url, legacy_headers = legacy
        try:
            return _fetch_remote_image_bytes(url=legacy_url, extra_headers=legacy_headers)
        except Exception:
            pass
    try:
        html = _fetch_html_raw(url=shared_url)
        og_image = _extract_og_image_url(html)
        if og_image:
            return _fetch_remote_image_bytes(url=og_image, extra_headers={"Referer": shared_url})
    except Exception:
        pass
    return None


def _linkedin_thumb(shared_url: str) -> tuple[bytes, str] | None:
    oembed_thumb = _linkedin_oembed_thumbnail_url(shared_url)
    if oembed_thumb:
        try:
            return _fetch_remote_image_bytes(url=oembed_thumb, extra_headers={"Referer": shared_url})
        except Exception:
            pass
    try:
        html = _fetch_html_raw(url=shared_url)
        og_image = _extract_og_image_url(html)
        if og_image:
            return _fetch_remote_image_bytes(url=og_image, extra_headers={"Referer": shared_url})
    except Exception:
        pass
    return None


def try_preview_image_bytes_for_share_url(url: str) -> tuple[bytes, str] | None:
    """
    Returns image bytes and declared content-type, or None if no preview could be fetched.

    Order: Instagram /p/ embed sidecar (full slide, honors img_index) → yt-dlp thumbnail →
    Instagram legacy/OG → LinkedIn → generic og:image.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    if _is_private_address(parsed.hostname or ""):
        return None

    host = (parsed.hostname or "").lower()

    if host == "instagram.com" or host.endswith(".instagram.com"):
        got_embed = try_instagram_embed_slide_bytes(url)
        if got_embed:
            return got_embed

    if media_extractor.supports_url(url):
        try:
            meta = media_extractor.extract(url)
            if meta.thumbnail_url:
                try:
                    return _fetch_remote_image_bytes(
                        url=meta.thumbnail_url,
                        extra_headers=meta.thumbnail_request_headers,
                    )
                except Exception:
                    pass
        except Exception:
            pass

        if host == "instagram.com" or host.endswith(".instagram.com"):
            got = _instagram_og_or_legacy(url)
            if got:
                return got

        if host == "linkedin.com" or host.endswith(".linkedin.com"):
            got = _linkedin_thumb(url)
            if got:
                return got

    elif host == "instagram.com" or host.endswith(".instagram.com"):
        got = _instagram_og_or_legacy(url)
        if got:
            return got

    elif host == "linkedin.com" or host.endswith(".linkedin.com"):
        got = _linkedin_thumb(url)
        if got:
            return got

    try:
        html = _fetch_html_raw(url=url)
        og_image = _extract_og_image_url(html)
        if og_image:
            return _fetch_remote_image_bytes(url=og_image, extra_headers={"Referer": url})
    except Exception:
        pass

    return None
