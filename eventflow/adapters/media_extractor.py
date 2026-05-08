from __future__ import annotations

import os
import re
import ssl
import http.cookiejar
from functools import lru_cache
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

import certifi

try:
    # Optional at import time (e.g. some test environments).
    # Production/container installs it via requirements.txt.
    from yt_dlp import YoutubeDL  # type: ignore
except Exception:  # pragma: no cover
    YoutubeDL = None  # type: ignore[assignment]

class _SilentYtDlpLogger:
    """
    yt-dlp can print error lines directly even with quiet/no_warnings.
    We provide a logger to keep extraction silent; callers handle exceptions.
    """

    def debug(self, msg: str) -> None:  # noqa: D401
        return None

    def warning(self, msg: str) -> None:  # noqa: D401
        return None

    def error(self, msg: str) -> None:  # noqa: D401
        return None


@dataclass(frozen=True)
class ExtractedMedia:
    source_url: str
    title: str | None
    description: str | None
    uploader: str | None
    upload_date: date | None
    thumbnail_url: str | None
    # Some providers (notably Instagram) require specific request headers
    # (e.g. Referer/User-Agent) to fetch thumbnails successfully.
    thumbnail_request_headers: dict[str, str] | None


_SUPPORTED_DOMAINS: tuple[str, ...] = (
    # YouTube
    "youtube.com",
    "youtu.be",
    # TikTok
    "tiktok.com",
    # Instagram
    "instagram.com",
    # Facebook
    "facebook.com",
    "fb.watch",
    # X/Twitter
    "x.com",
    "twitter.com",
    # Reddit
    "reddit.com",
    # LinkedIn (preview via OG image; yt-dlp may be best-effort)
    "linkedin.com",
)


def _host_matches(host: str, domain: str) -> bool:
    host = host.lower().strip(".")
    domain = domain.lower().strip(".")
    return host == domain or host.endswith("." + domain)


def supports_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(_host_matches(host, d) for d in _SUPPORTED_DOMAINS)


def instagram_legacy_media_fetch_params(url: str) -> tuple[str, dict[str, str]] | None:
    """
    Instagram carousel shares often include ?img_index=N; the public redirect endpoint
    https://www.instagram.com/p/<shortcode>/media/?size=l&img_index=N returns that slide.

    yt-dlp thumbnails for sidecar posts are often missing or only reflect the first slide,
    so callers use this as a fetch URL + headers pair.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if not (host == "instagram.com" or host.endswith(".instagram.com")):
        return None
    m = re.search(r"/p/([^/]+)/?", parsed.path or "")
    if not m:
        return None
    shortcode = m.group(1)
    qs = parse_qs(parsed.query)
    idx_val: int | None = None
    for key in ("img_index", "carousel_index"):
        vals = qs.get(key)
        if not vals:
            continue
        try:
            v = int(str(vals[0]).strip())
            if v >= 1:
                idx_val = v
                break
        except ValueError:
            continue

    media_url = f"https://www.instagram.com/p/{shortcode}/media/?size=l"
    if idx_val is not None:
        media_url += f"&img_index={idx_val}"

    headers = {
        "Referer": url,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    return media_url, headers


# Maximum number of carousel slide URLs we will attempt to parse from Instagram embed HTML.
# Some posts can have up to 20 slides; keep this high enough for accurate previews.
INSTAGRAM_CAROUSEL_MAX_SLIDES = 20


def instagram_post_shortcode(url: str) -> str | None:
    """Shortcode from instagram.com/p/<shortcode>/ URLs (query/fragment ignored)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if not (host == "instagram.com" or host.endswith(".instagram.com")):
        return None
    m = re.search(r"/p/([^/]+)/?", parsed.path or "")
    return m.group(1) if m else None


def _decode_instagram_embed_url_fragment(fragment: str) -> str:
    """Undo JS-style escaping used in Instagram embed HTML (e.g. \\\\/ → /)."""
    out = fragment
    changed = True
    while changed:
        changed = False
        if "\\\\/" in out:
            out = out.replace("\\\\/", "/")
            changed = True
        elif "\\/" in out:
            out = out.replace("\\/", "/")
            changed = True
    return out


def instagram_carousel_image_urls_from_embed_html(html: str) -> list[str]:
    """
    Ordered CDN URLs for multi-image sidecar posts from /p/<code>/embed/ HTML.

    Returns an empty list when the post is a single image (no sidecar marker) or parsing fails.
    """
    marker = "edge_sidecar_to_children"
    i = html.find(marker)
    if i == -1:
        return []

    segment = html[i : i + 800_000]
    needle = 'display_url\\":\\"'
    found: list[str] = []
    pos = 0
    for _ in range(96):
        j = segment.find(needle, pos)
        if j == -1:
            break
        start = j + len(needle)
        end = segment.find('\\"', start)
        if end == -1:
            break
        raw = segment[start:end]
        url = _decode_instagram_embed_url_fragment(raw)
        # Instagram CDN URLs change shape; accept any https fbcdn URL.
        if url.startswith("https://") and "fbcdn.net" in url.lower():
            found.append(url)
        pos = end + 1

    deduped: list[str] = []
    seen: set[str] = set()
    for u in found:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
        if len(deduped) >= INSTAGRAM_CAROUSEL_MAX_SLIDES:
            break
    return deduped


def fetch_instagram_post_embed_html(*, page_url: str, timeout_seconds: float = 12.0, max_bytes: int = 2_000_000) -> str:
    """Download HTML for https://www.instagram.com/p/<shortcode>/embed/ (public embed page)."""
    parsed = urlparse(page_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Invalid URL")
    if not (host == "instagram.com" or host.endswith(".instagram.com")):
        raise ValueError("Not an Instagram URL")

    shortcode = instagram_post_shortcode(page_url)
    if not shortcode:
        raise ValueError("Not an Instagram /p/ post URL")

    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
    cookie = instagram_cookie_header_for_url(embed_url)
    req = Request(
        embed_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": page_url.split("#", 1)[0],
            **({"Cookie": cookie} if cookie else {}),
        },
        method="GET",
    )

    ctx = ssl.create_default_context(cafile=certifi.where())
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    try:
        with opener.open(req, timeout=timeout_seconds) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            return raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        raise RuntimeError(f"Instagram embed fetch failed ({e.code})") from e
    except URLError as e:
        raise RuntimeError(f"Instagram embed fetch failed ({e})") from e


@lru_cache
def _load_cookie_jar() -> http.cookiejar.MozillaCookieJar | None:
    """
    Load Netscape-format cookies.txt for Instagram fetching.

    Controlled by env var `YTDLP_COOKIE_FILE`.
    """
    cookiefile = (os.getenv("YTDLP_COOKIE_FILE") or "").strip()
    if not cookiefile or not os.path.exists(cookiefile):
        return None
    jar = http.cookiejar.MozillaCookieJar(cookiefile)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except Exception:
        return None
    return jar


def instagram_cookie_header_for_url(url: str) -> str | None:
    """
    Return a Cookie header string for `url` if `YTDLP_COOKIE_FILE` is configured.
    """
    jar = _load_cookie_jar()
    if jar is None:
        return None
    try:
        req = Request(url)
        jar.add_cookie_header(req)
        cookie = req.get_header("Cookie")
        return cookie if isinstance(cookie, str) and cookie.strip() else None
    except Exception:
        return None


def _parse_upload_date(value: Any) -> date | None:
    # yt-dlp commonly returns YYYYMMDD as a string like "20240131"
    if not value or not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        y = int(value[0:4])
        m = int(value[4:6])
        d = int(value[6:8])
        return date(y, m, d)
    except ValueError:
        return None


def _pick_best_thumbnail(info: dict[str, Any]) -> str | None:
    thumb = info.get("thumbnail")
    if isinstance(thumb, str) and thumb:
        return thumb

    thumbs = info.get("thumbnails")
    if not isinstance(thumbs, list) or not thumbs:
        return None

    candidates: list[tuple[int, int, str]] = []
    for t in thumbs:
        if not isinstance(t, dict):
            continue
        url = t.get("url")
        if not isinstance(url, str) or not url:
            continue
        w = t.get("width")
        h = t.get("height")
        w_i = int(w) if isinstance(w, int) else 0
        h_i = int(h) if isinstance(h, int) else 0
        candidates.append((w_i, h_i, url))

    if not candidates:
        return None

    # Prefer largest area; fall back to first if width/height missing.
    candidates.sort(key=lambda x: (x[0] * x[1], x[0], x[1]), reverse=True)
    return candidates[0][2]


def _safe_thumbnail_headers(info: dict[str, Any]) -> dict[str, str] | None:
    """
    yt-dlp may return `http_headers` to successfully fetch derived assets.
    We only forward a small safe subset (no cookies/auth).
    """
    headers = info.get("http_headers")
    if not isinstance(headers, dict) or not headers:
        return None

    allowlist = {"user-agent", "referer", "accept-language"}
    out: dict[str, str] = {}
    for k, v in headers.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        lk = k.lower().strip()
        if lk in allowlist and v.strip():
            # Normalize to conventional header casing
            if lk == "user-agent":
                out["User-Agent"] = v
            elif lk == "referer":
                out["Referer"] = v
            elif lk == "accept-language":
                out["Accept-Language"] = v

    return out or None


def extract(url: str, *, socket_timeout_seconds: float = 5.0) -> ExtractedMedia:
    """
    Extract best-effort metadata for supported social/video URLs.
    Intended for metadata-only usage; it does not download media.
    """
    if YoutubeDL is None:  # pragma: no cover
        raise RuntimeError("yt-dlp is not installed")

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": socket_timeout_seconds,
        "retries": 1,
        # Prevent yt-dlp from printing `ERROR: [Instagram] ...` to stderr.
        "logger": _SilentYtDlpLogger(),
    }

    cookiefile = (os.getenv("YTDLP_COOKIE_FILE") or "").strip()
    if cookiefile and os.path.exists(cookiefile):
        # Improves reliability for sites that gate content behind login/rate limits.
        opts["cookiefile"] = cookiefile

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)  # type: ignore[no-untyped-call]

    if not isinstance(info, dict):
        info = {}

    media = ExtractedMedia(
        source_url=url,
        title=info.get("title") if isinstance(info.get("title"), str) else None,
        description=info.get("description") if isinstance(info.get("description"), str) else None,
        uploader=info.get("uploader") if isinstance(info.get("uploader"), str) else None,
        upload_date=_parse_upload_date(info.get("upload_date")),
        thumbnail_url=_pick_best_thumbnail(info),
        thumbnail_request_headers=_safe_thumbnail_headers(info),
    )

    legacy = instagram_legacy_media_fetch_params(url)
    if legacy is None:
        return media

    legacy_url, legacy_headers = legacy
    qs = parse_qs(urlparse(url).query)
    asks_slide = bool(qs.get("img_index") or qs.get("carousel_index"))
    if asks_slide or media.thumbnail_url is None:
        return ExtractedMedia(
            source_url=media.source_url,
            title=media.title,
            description=media.description,
            uploader=media.uploader,
            upload_date=media.upload_date,
            thumbnail_url=legacy_url,
            thumbnail_request_headers=legacy_headers,
        )
    return media

