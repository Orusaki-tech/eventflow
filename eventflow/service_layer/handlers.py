from __future__ import annotations

import ipaddress
import logging
import re
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID
from html import unescape
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

import httpx
from google.genai.errors import APIError as GeminiAPIError
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
import ssl
import certifi
import concurrent.futures

from icalendar import Calendar

from eventflow.adapters.gemini_client import AbstractGeminiClient
from eventflow.adapters.calendar_client import AbstractCalendarClient
from eventflow.adapters import media_extractor
from eventflow.adapters.share_preview_image import try_preview_image_bytes_for_share_url
from eventflow.adapters.push_client import AbstractPushClient
from eventflow.adapters.gemini_client import ParsedEventDraft
from eventflow.adapters.repository import CalendarToken, OutboxMessage
from eventflow.domain import commands
from eventflow.domain import events as domain_events
from eventflow.adapters.gemini import _coerce_optional_price, _inline_image_mime_type
from eventflow.domain.exceptions import DraftNotFound, EventNotFound, InvariantViolation, PermissionDenied
from eventflow.domain.model import EventDraft, ScheduledEvent, TrafficCondition
from eventflow.service_layer.unit_of_work import AbstractUnitOfWork
from eventflow.adapters.repository import CommunityEvent


calendar_client: AbstractCalendarClient | None = None
push_client: AbstractPushClient | None = None
scheduler_client: "AbstractSchedulerClient | None" = None

INSTAGRAM_CAROUSEL_MAX_GEMINI_SLIDES = 2

_log = logging.getLogger(__name__)


def _fallback_parsed_from_share_text(*, url: str, text: str) -> ParsedEventDraft:
    """When Gemini is unavailable, derive a minimal draft from yt-dlp / HTML extracted text."""
    title = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("title:"):
            title = stripped.split(":", 1)[1].strip()
            break
    if not title:
        try:
            p = urlparse(url)
            seg = (p.path or "").rstrip("/").split("/")[-1]
            if seg and seg not in {"p", "reel", "tv", "stories"}:
                title = seg.replace("-", " ").replace("_", " ")[:160]
            else:
                title = p.netloc or "Shared link"
        except Exception:
            title = "Shared link"
    return ParsedEventDraft(
        title=title or "Shared link",
        start_time=None,
        venue="",
        confidence_score=0.2,
        price=None,
    )


class AbstractSchedulerClient(Protocol):
    def schedule_traffic_check(self, *, event_id, user_id, run_at: datetime) -> None: ...

    def cancel_traffic_check(self, *, event_id) -> None: ...

    def schedule_push_due(
        self,
        *,
        job_key: str,
        user_id: str,
        run_at: datetime,
        title: str,
        body: str,
        event_id: str | None = None,
        venue_lat: float | None = None,
        venue_lng: float | None = None,
        action: str | None = None,
    ) -> None: ...

    def cancel_push_due(self, *, job_key: str) -> None: ...


class FakeSchedulerClient:
    def __init__(self) -> None:
        self.scheduled: list[tuple[str, datetime]] = []
        self.cancelled: list[str] = []
        self.push_scheduled: list[dict] = []
        self.push_cancelled: list[str] = []

    def schedule_traffic_check(self, *, event_id, user_id, run_at: datetime) -> None:
        self.scheduled.append((str(event_id), run_at))

    def cancel_traffic_check(self, *, event_id) -> None:
        self.cancelled.append(str(event_id))

    def schedule_push_due(
        self,
        *,
        job_key: str,
        user_id: str,
        run_at: datetime,
        title: str,
        body: str,
        event_id: str | None = None,
        venue_lat: float | None = None,
        venue_lng: float | None = None,
        action: str | None = None,
    ) -> None:
        self.push_scheduled.append(
            {
                "job_key": job_key,
                "user_id": user_id,
                "run_at": run_at,
                "title": title,
                "body": body,
                "event_id": event_id,
                "venue_lat": venue_lat,
                "venue_lng": venue_lng,
                "action": action,
            }
        )

    def cancel_push_due(self, *, job_key: str) -> None:
        self.push_cancelled.append(job_key)


def handle_capture_event_image(
    cmd: commands.CaptureEventImage,
    uow: AbstractUnitOfWork,
    *,
    gemini: AbstractGeminiClient | None = None,
) -> dict:
    if gemini is None:
        raise RuntimeError("Gemini client not configured")

    parsed = gemini.parse_event_image(image_bytes=cmd.image_bytes)
    draft = EventDraft.new(
        user_id=cmd.user_id,
        title=parsed.title,
        start_time=parsed.start_time,
        venue=parsed.venue,
        confidence_score=parsed.confidence_score,
        price=parsed.price,
    )

    with uow:
        uow.drafts.add(draft)
        uow.commit()

    return {
        "draft_id": draft.id,
        "title": draft.title,
        "start_time": draft.start_time,
        "venue": draft.venue,
        "confidence_score": draft.confidence_score,
        "price": draft.price,
    }


def _is_private_address(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        # Not an IP literal. We can't reliably resolve without a DNS lookup; block obvious localhost patterns.
        lowered = host.lower()
        return lowered in {"localhost"} or lowered.endswith(".localhost")


def _extract_text_from_html(html: str) -> str:
    # Extremely small/robust extraction: remove scripts/styles, strip tags, normalize whitespace.
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = unescape(html)
    html = re.sub(r"\s+", " ", html).strip()
    return html


def _fetch_url_text(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 1_000_000) -> str:
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
            "User-Agent": "EventFlow/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1",
        },
        method="GET",
    )

    try:
        # Avoid environment proxy settings for local/dev reliability. Some networks/proxies
        # break CONNECT tunnels and surface confusing errors like "tunnel connection failed".
        ctx = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
        with opener.open(req, timeout=timeout_seconds) as resp:
            # Read up to max_bytes (+1 to detect truncation), but don't fail hard if it's large.
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raw = raw[:max_bytes]
            # Best-effort decode.
            text = raw.decode("utf-8", errors="replace")
            return _extract_text_from_html(text)
    except HTTPError as e:
        raise InvariantViolation(f"URL fetch failed ({e.code})")
    except URLError as e:
        raise InvariantViolation(f"URL fetch failed ({e})")


def _fetch_remote_image_bytes(
    *,
    url: str,
    extra_headers: dict[str, str] | None = None,
    timeout_seconds: float = 25.0,
    max_bytes: int = 15_000_000,
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

    req = Request(url, headers=headers, method="GET")
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
        with opener.open(req, timeout=timeout_seconds) as resp:
            raw = resp.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise InvariantViolation("Image too large")
            content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            looks_image = (
                raw.startswith(b"\xff\xd8\xff")
                or raw.startswith(b"\x89PNG\r\n\x1a\n")
                or (len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
            )
            if not content_type.startswith("image/") and not looks_image:
                raise InvariantViolation("Remote resource is not an image")
            return raw, content_type or "application/octet-stream"
    except HTTPError as e:
        raise InvariantViolation(f"Image fetch failed ({e.code})")
    except URLError as e:
        raise InvariantViolation(f"Image fetch failed ({e})")


def handle_capture_event_text(
    cmd: commands.CaptureEventText,
    uow: AbstractUnitOfWork,
    *,
    gemini: AbstractGeminiClient | None = None,
) -> dict:
    if gemini is None:
        raise RuntimeError("Gemini client not configured")

    parsed = gemini.parse_event_text(text=cmd.text)
    draft = EventDraft.new(
        user_id=cmd.user_id,
        title=parsed.title,
        start_time=parsed.start_time,
        venue=parsed.venue,
        confidence_score=parsed.confidence_score,
        price=parsed.price,
    )

    with uow:
        uow.drafts.add(draft)
        uow.commit()

    return {
        "draft_id": draft.id,
        "title": draft.title,
        "start_time": draft.start_time,
        "venue": draft.venue,
        "confidence_score": draft.confidence_score,
        "price": draft.price,
    }


def persist_draft_from_parsed(*, user_id, parsed: ParsedEventDraft, uow: AbstractUnitOfWork) -> dict:
    draft = EventDraft.new(
        user_id=user_id,
        title=parsed.title,
        start_time=parsed.start_time,
        venue=parsed.venue,
        confidence_score=parsed.confidence_score,
        price=parsed.price,
    )
    with uow:
        uow.drafts.add(draft)
        uow.commit()
    return {
        "draft_id": draft.id,
        "title": draft.title,
        "start_time": draft.start_time,
        "venue": draft.venue,
        "confidence_score": draft.confidence_score,
        "price": draft.price,
    }


def merge_poster_parse_into_draft(
    *,
    draft_id: UUID,
    user_id: UUID,
    parsed: ParsedEventDraft,
    uow: AbstractUnitOfWork,
) -> dict:
    """Apply poster/visual parse onto an existing pending draft (same draft row)."""
    with uow:
        draft = uow.drafts.get(draft_id)
        if draft is None:
            raise DraftNotFound(f"Draft {draft_id} not found")
        if draft.user_id != user_id:
            raise PermissionDenied("Not your draft")
        if draft.is_confirmed:
            raise InvariantViolation("Cannot attach a poster to a confirmed draft")

        draft.title = parsed.title
        draft.start_time = parsed.start_time
        draft.venue = parsed.venue
        draft.confidence_score = parsed.confidence_score
        draft.price = parsed.price

        uow.commit()

        return {
            "draft_id": draft.id,
            "title": draft.title,
            "start_time": draft.start_time,
            "venue": draft.venue,
            "confidence_score": draft.confidence_score,
            "price": draft.price,
            "confirmed_at": draft.confirmed_at,
        }


def handle_capture_event_url(
    cmd: commands.CaptureEventUrl,
    uow: AbstractUnitOfWork,
    *,
    gemini: AbstractGeminiClient | None = None,
) -> dict:
    # Prefer yt-dlp metadata for supported social/video links; fall back to HTML extraction.
    # Keep the downstream pipeline stable by always calling `handle_capture_event_text`.
    parsed = urlparse(cmd.url)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolation("Only http/https URLs are supported")
    if not parsed.netloc:
        raise InvariantViolation("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise InvariantViolation("URL host is not allowed")

    text: str
    if media_extractor.supports_url(cmd.url):
        try:
            meta = media_extractor.extract(cmd.url)
            parts: list[str] = []
            parts.append(f"URL: {cmd.url}")
            if meta.title:
                parts.append(f"Title: {meta.title}")
            if meta.uploader:
                parts.append(f"Uploader: {meta.uploader}")
            if meta.upload_date:
                parts.append(f"Upload date: {meta.upload_date.isoformat()}")
            if meta.description:
                parts.append("")
                parts.append(meta.description)
            text = "\n".join(parts).strip() or cmd.url
        except Exception:
            # Best-effort: if extraction fails for any reason, fall back to HTML fetch.
            text = _fetch_url_text(url=cmd.url)
    else:
        text = _fetch_url_text(url=cmd.url)

    preview = try_preview_image_bytes_for_share_url(cmd.url)
    if preview and gemini is not None:
        image_bytes, declared_ct = preview
        mime = _inline_image_mime_type(declared_content_type=declared_ct, image_bytes=image_bytes)
        try:
            parsed = gemini.parse_event_image(image_bytes=image_bytes, content_type=mime)
            out = persist_draft_from_parsed(user_id=cmd.user_id, parsed=parsed, uow=uow)
            out["_share_preview_image_bytes"] = image_bytes
            out["_share_preview_content_type"] = declared_ct
            return out
        except Exception:
            pass

    try:
        out = handle_capture_event_text(commands.CaptureEventText(user_id=cmd.user_id, text=text), uow, gemini=gemini)
    except (GeminiAPIError, httpx.HTTPError) as e:
        # Disabled API key, quota, or network — still create a draft from fetched metadata so imports don't hard-fail.
        _log.warning(
            "capture_event_url gemini_text_failed url_host=%s err=%s",
            (urlparse(cmd.url).hostname or ""),
            e,
        )
        out = persist_draft_from_parsed(
            user_id=cmd.user_id,
            parsed=_fallback_parsed_from_share_text(url=cmd.url, text=text),
            uow=uow,
        )
    if preview:
        out["_share_preview_image_bytes"] = preview[0]
        out["_share_preview_content_type"] = preview[1]
    return out


def _resolve_instagram_carousel_slide_indices(*, requested: list[int] | None, num_slides: int) -> list[int]:
    """
    Pick which 1-based carousel slides to send to Gemini (max INSTAGRAM_CAROUSEL_MAX_GEMINI_SLIDES).

    Default: slides 1 and 2 when present; single-slide carousels yield [1] only.
    """
    if num_slides < 1:
        raise InvariantViolation("Carousel has no slides")

    if requested:
        uniq_sorted = sorted({int(i) for i in requested})
        invalid = [i for i in uniq_sorted if i < 1 or i > num_slides]
        if invalid:
            raise InvariantViolation(
                f"carousel_slide_indices out of range for this post (valid 1–{num_slides}; got {sorted(set(requested))})"
            )
        if not uniq_sorted:
            raise InvariantViolation("carousel_slide_indices must not be empty when provided")
        if len(uniq_sorted) > INSTAGRAM_CAROUSEL_MAX_GEMINI_SLIDES:
            raise InvariantViolation(f"At most {INSTAGRAM_CAROUSEL_MAX_GEMINI_SLIDES} carousel_slide_indices allowed")
        return uniq_sorted

    return [i for i in (1, 2) if i <= num_slides]


def _instagram_carousel_slide_fetch_targets(url: str) -> tuple[list[tuple[str, dict[str, str]]], bool]:
    """
    Ordered (image_url, extra_headers) for each slide of an Instagram /p/<shortcode>/ post.

    Second value is True when the post is a sidecar carousel from embed HTML; False when a single
    image resolved via legacy media params.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvariantViolation("Only http/https URLs are supported")
    if not parsed.netloc:
        raise InvariantViolation("Invalid URL")
    if _is_private_address(parsed.hostname or ""):
        raise InvariantViolation("URL host is not allowed")

    shortcode = media_extractor.instagram_post_shortcode(url)
    if shortcode is None:
        raise InvariantViolation("Only Instagram photo posts (/p/...) support carousel extraction")

    referer = f"https://www.instagram.com/p/{shortcode}/"

    try:
        embed_html = media_extractor.fetch_instagram_post_embed_html(page_url=url)
    except RuntimeError as e:
        raise InvariantViolation(str(e)) from e

    image_urls = media_extractor.instagram_carousel_image_urls_from_embed_html(embed_html)
    cdn_headers: dict[str, str] = {"Referer": referer}

    if image_urls:
        return [(u, cdn_headers) for u in image_urls], True

    legacy = media_extractor.instagram_legacy_media_fetch_params(url)
    if legacy is None:
        raise InvariantViolation("Could not resolve Instagram image for this post")
    legacy_url, legacy_hdrs = legacy
    return [(legacy_url, legacy_hdrs)], False


def instagram_carousel_preview_slide_bytes(*, url: str) -> list[tuple[int, bytes, str]]:
    """
    Fetch Instagram slide images for client preview.

    Key constraint: this must be fast/reliable even when Instagram embed HTML is slow/blocked.
    So we prefer the direct `/media/?size=l&img_index=N` slide endpoint and only try a small number
    of slides in parallel.
    """
    MAX_PREVIEW_SLIDES = 20

    def _fetch_one(i: int, img_url: str, hdrs: dict[str, str]) -> tuple[int, bytes, str] | None:
        try:
            image_bytes, declared_ct = _fetch_remote_image_bytes(
                url=img_url,
                extra_headers=hdrs,
                timeout_seconds=4.5,
            )
            return (i, image_bytes, declared_ct)
        except Exception as e:
            _log.warning("instagram_carousel_preview_slide_failed idx=%s err=%s", i, e)
            return None

    def _fetch_batch(targets: list[tuple[str, dict[str, str]]], *, cap: int) -> list[tuple[int, bytes, str]]:
        out: list[tuple[int, bytes, str]] = []
        batch = list(enumerate(targets[:cap], start=1))
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(batch) or 1)) as ex:
            futs = [ex.submit(_fetch_one, i, img_url, hdrs) for i, (img_url, hdrs) in batch]
            for fut in concurrent.futures.as_completed(futs):
                row = fut.result()
                if row is not None:
                    out.append(row)
        out.sort(key=lambda t: t[0])
        return out

    # Attempt 1: embed HTML extraction (most accurate for real carousels).
    targets_embed, _ = _instagram_carousel_slide_fetch_targets(url)
    out_embed = _fetch_batch(targets_embed, cap=min(MAX_PREVIEW_SLIDES, len(targets_embed)))
    if len(out_embed) >= 2:
        # Ensure we actually got different slides (not a CDN error page cached as an "image").
        uniq = {hashlib.sha256(bts).digest() for _idx, bts, _ct in out_embed}
        if len(uniq) >= 2:
            return out_embed

    # Attempt 2: direct /media slide endpoints (faster, but can return duplicates / blocks).
    direct_targets: list[tuple[str, dict[str, str]]] = []
    shortcode = media_extractor.instagram_post_shortcode(url)
    if shortcode:
        hdrs = {
            "Referer": url.split("#", 1)[0],
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        }
        cookie = media_extractor.instagram_cookie_header_for_url(url)
        if cookie:
            hdrs["Cookie"] = cookie
        for i in range(1, MAX_PREVIEW_SLIDES + 1):
            direct_targets.append((f"https://www.instagram.com/p/{shortcode}/media/?size=l&img_index={i}", hdrs))
    if direct_targets:
        out_direct = _fetch_batch(direct_targets, cap=MAX_PREVIEW_SLIDES)
        if out_direct:
            # Drop duplicates (Instagram sometimes serves the same poster for many indices).
            seen: set[bytes] = set()
            deduped: list[tuple[int, bytes, str]] = []
            for idx, bts, ct in out_direct:
                h = hashlib.sha256(bts).digest()
                if h in seen:
                    continue
                seen.add(h)
                deduped.append((idx, bts, ct))
            return deduped

    # If embed returned a single slide, keep it as best-effort.
    if out_embed:
        return out_embed
    raise InvariantViolation("Could not fetch carousel preview images")


def handle_capture_instagram_carousel_url(
    *,
    user_id: UUID,
    url: str,
    uow: AbstractUnitOfWork,
    gemini: AbstractGeminiClient | None = None,
    carousel_slide_indices: list[int] | None = None,
) -> tuple[list[dict], list[int]]:
    """
    Instagram /p/<shortcode>/ posts: parse up to two carousel slides with Gemini (default slides 1–2).

    Returns (draft dict rows, 1-based slides_used aligned with drafts).
    Single-image posts use one legacy media fetch (slides_used always [1]).
    """
    if gemini is None:
        raise RuntimeError("Gemini client not configured")

    targets, is_sidecar = _instagram_carousel_slide_fetch_targets(url)

    if not is_sidecar:
        if carousel_slide_indices is not None:
            uniq = sorted({int(i) for i in carousel_slide_indices})
            if uniq != [1]:
                raise InvariantViolation("This post has a single image; only carousel_slide_indices [1] is valid")

    indices = _resolve_instagram_carousel_slide_indices(
        requested=carousel_slide_indices,
        num_slides=len(targets),
    )

    out: list[dict] = []
    try:
        batches: list[tuple[int, bytes, str]] = []
        for idx in indices:
            img_url, hdrs = targets[idx - 1]
            image_bytes, declared_ct = _fetch_remote_image_bytes(url=img_url, extra_headers=hdrs)
            batches.append((idx, image_bytes, declared_ct))

        for idx, image_bytes, declared_ct in batches:
            mime = _inline_image_mime_type(declared_content_type=declared_ct, image_bytes=image_bytes)
            parsed_ev = gemini.parse_event_image(image_bytes=image_bytes, content_type=mime)
            row = persist_draft_from_parsed(user_id=user_id, parsed=parsed_ev, uow=uow)
            row["_share_preview_image_bytes"] = image_bytes
            row["_share_preview_content_type"] = declared_ct
            out.append(row)
        return out, indices
    except (GeminiAPIError, httpx.HTTPError) as e:
        _log.warning(
            "instagram_carousel_gemini_failed url_host=%s err=%s",
            (urlparse(url).hostname or ""),
            e,
        )
        row = handle_capture_event_url(
            commands.CaptureEventUrl(user_id=user_id, url=url),
            uow,
            gemini=gemini,
        )
        first_idx, image_bytes, declared_ct = batches[0]
        row["_share_preview_image_bytes"] = image_bytes
        row["_share_preview_content_type"] = declared_ct
        return [row], [first_idx]
    if not batches:
        return [], []


def handle_capture_event_upload_image(
    cmd: commands.CaptureEventUploadImage,
    uow: AbstractUnitOfWork,
    *,
    gemini: AbstractGeminiClient | None = None,
) -> dict:
    return handle_capture_event_image(
        commands.CaptureEventImage(user_id=cmd.user_id, image_bytes=cmd.image_bytes),
        uow,
        gemini=gemini,
    )


def handle_capture_event_ics(cmd: commands.CaptureEventIcs, uow: AbstractUnitOfWork) -> dict:
    try:
        cal = Calendar.from_ical(cmd.ics_bytes)
    except Exception:
        raise InvariantViolation("Invalid ICS payload")

    vevent = None
    for component in cal.walk():
        if component.name == "VEVENT":
            vevent = component
            break
    if vevent is None:
        raise InvariantViolation("ICS contains no VEVENT")

    summary = str(vevent.get("SUMMARY") or "Event")
    dtstart = vevent.get("DTSTART")
    if dtstart is None:
        raise InvariantViolation("ICS missing DTSTART")
    start = dtstart.dt
    if isinstance(start, datetime):
        start_time = start if start.tzinfo is not None else start.replace(tzinfo=timezone.utc)
    else:
        # date-only DTSTART; default to midnight UTC.
        start_time = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)

    venue = str(vevent.get("LOCATION") or "")
    draft = EventDraft.new(
        user_id=cmd.user_id,
        title=summary,
        start_time=start_time,
        venue=venue,
        confidence_score=1.0,
    )
    with uow:
        uow.drafts.add(draft)
        uow.commit()

    return {
        "draft_id": draft.id,
        "title": draft.title,
        "start_time": draft.start_time,
        "venue": draft.venue,
        "confidence_score": draft.confidence_score,
        "price": draft.price,
    }


def handle_upsert_community_event(cmd: commands.UpsertCommunityEvent, uow: AbstractUnitOfWork) -> dict:
    with uow:
        evt = CommunityEvent(
            user_id=cmd.user_id,
            source=cmd.source,
            title=cmd.title,
            start_time=cmd.start_time,
            venue=cmd.venue,
            description=cmd.description,
            poster_image_uri=cmd.poster_image_uri,
            created_at=datetime.now(timezone.utc),
        )
        uow.community_events.upsert(evt)
        now = datetime.now(timezone.utc)
        uow.outbox.add(OutboxMessage(topic="community_event.upserted", payload={"community_event_id": str(evt.id)}, occurred_at=now))
        uow.commit()

    return {
        "community_event_id": evt.id,
        "source": evt.source,
        "title": evt.title,
        "start_time": evt.start_time,
        "venue": evt.venue,
        "description": evt.description,
        "poster_image_uri": evt.poster_image_uri,
    }


def handle_confirm_event_draft(
    cmd: commands.ConfirmEventDraft,
    uow: AbstractUnitOfWork,
) -> str:
    draft = uow.drafts.get(cmd.draft_id)
    if draft is None:
        raise DraftNotFound(f"Draft {cmd.draft_id} not found")
    if draft.user_id != cmd.user_id:
        raise PermissionDenied("Not your draft")
    if draft.start_time is None:
        raise InvariantViolation("Add a date and time before confirming this event.")

    # If this draft has a known source URL or poster asset and we already have an event for it,
    # return the existing event instead of creating duplicates.
    sess = getattr(uow, "session", None)
    if sess is not None:
        try:
            from sqlalchemy import text

            with sess.begin_nested():
                src = sess.execute(
                    text(
                        """
                        SELECT source_url_normalized, poster_asset_id
                        FROM event_sources
                        WHERE user_id = :user_id
                          AND draft_id = :draft_id
                        """
                    ),
                    {"user_id": str(cmd.user_id), "draft_id": str(cmd.draft_id)},
                ).first()

                if src:
                    src_url_norm = src[0]
                    poster_asset_id = src[1]
                    if src_url_norm or poster_asset_id:
                        existing = sess.execute(
                            text(
                                """
                                SELECT event_id
                                FROM event_sources
                                WHERE user_id = :user_id
                                  AND event_id IS NOT NULL
                                  AND (
                                    (:src_url_norm IS NOT NULL AND source_url_normalized = :src_url_norm)
                                    OR
                                    (:poster_asset_id IS NOT NULL AND poster_asset_id = :poster_asset_id)
                                  )
                                ORDER BY created_at DESC
                                LIMIT 1
                                """
                            ),
                            {
                                "user_id": str(cmd.user_id),
                                "src_url_norm": src_url_norm,
                                "poster_asset_id": str(poster_asset_id) if poster_asset_id else None,
                            },
                        ).first()
                        if existing and existing[0]:
                            draft.confirm()
                            list(uow.collect_new_events())
                            return str(existing[0])
        except Exception:
            _log.warning("confirm_draft source migration failed for draft_id=%s", cmd.draft_id)

    draft.confirm()
    scheduled = ScheduledEvent.from_confirmed_draft(draft)
    uow.events.add(scheduled)

    # If this draft was created from a poster/link, migrate its source metadata to the event.
    # Best-effort: only applies to SQLAlchemy UoW with a session.
    if sess is not None:
        # IMPORTANT: if this update fails (e.g. table missing in a dev DB),
        # Postgres marks the whole transaction as failed. Use a SAVEPOINT so a failure
        # doesn't abort the surrounding transaction.
        try:
            from sqlalchemy import text

            with sess.begin_nested():
                sess.execute(
                    text(
                        """
                        UPDATE event_sources
                        SET event_id = :event_id
                        WHERE user_id = :user_id
                          AND draft_id = :draft_id
                        """
                    ),
                    {
                        "event_id": str(scheduled.id),
                        "user_id": str(cmd.user_id),
                        "draft_id": str(cmd.draft_id),
                    },
                )
        except Exception:
            _log.warning("confirm_draft source migration UPDATE failed for draft_id=%s", cmd.draft_id)
    return str(scheduled.id)


def patch_draft_fields(*, draft_id: UUID, user_id: UUID, patch: dict, uow: AbstractUnitOfWork) -> dict:
    """Apply partial updates to a pending draft. Keys use model_dump(exclude_unset=True) semantics."""
    with uow:
        draft = uow.drafts.get(draft_id)
        if draft is None:
            raise DraftNotFound(f"Draft {draft_id} not found")
        if draft.user_id != user_id:
            raise PermissionDenied("Not your draft")
        if draft.is_confirmed:
            raise InvariantViolation("Cannot edit a confirmed draft")

        if "title" in patch:
            draft.title = str(patch["title"])
        if "start_time" in patch:
            draft.start_time = patch["start_time"]
        if "venue" in patch:
            draft.venue = str(patch["venue"])
        if "confidence_score" in patch:
            draft.confidence_score = float(patch["confidence_score"])
        if "price" in patch:
            draft.price = _coerce_optional_price(patch.get("price"))

        uow.commit()

        return {
            "draft_id": draft.id,
            "title": draft.title,
            "start_time": draft.start_time,
            "venue": draft.venue,
            "confidence_score": draft.confidence_score,
            "price": draft.price,
            "confirmed_at": draft.confirmed_at,
        }


def handle_update_event_draft(cmd: commands.UpdateEventDraft, uow: AbstractUnitOfWork) -> dict:
    patch: dict = {}
    if cmd.title is not None:
        patch["title"] = cmd.title
    if cmd.start_time is not None:
        patch["start_time"] = cmd.start_time
    if cmd.venue is not None:
        patch["venue"] = cmd.venue
    return patch_draft_fields(draft_id=cmd.draft_id, user_id=cmd.user_id, patch=patch, uow=uow)


def handle_cancel_event(cmd: commands.CancelEvent, uow: AbstractUnitOfWork) -> None:
    evt = uow.events.get(cmd.event_id)
    if evt is None:
        raise EventNotFound(f"Event {cmd.event_id} not found")
    if evt.user_id != cmd.user_id:
        raise PermissionDenied("Not your event")
    evt.cancel()
    uow.commit()


def handle_schedule_traffic_alert(cmd: commands.ScheduleTrafficAlert, uow: AbstractUnitOfWork) -> None:
    evt = uow.events.get(cmd.event_id)
    if evt is None:
        return
    if evt.user_id != cmd.user_id:
        raise PermissionDenied("Not your event")
    evt.schedule_traffic_alert(traffic=TrafficCondition(travel_seconds=cmd.travel_seconds))
    uow.commit()


def handle_schedule_reminder_alert(cmd: commands.ScheduleReminderAlert, uow: AbstractUnitOfWork) -> None:
    evt = uow.events.get(cmd.event_id)
    if evt is None:
        return
    if evt.user_id != cmd.user_id:
        raise PermissionDenied("Not your event")
    evt.schedule_reminder_alert(minutes_before=cmd.minutes_before)
    uow.commit()


def sync_to_calendar(evt, uow: AbstractUnitOfWork) -> None:
    if not isinstance(evt, domain_events.EventConfirmed):
        return
    if calendar_client is None:
        return

    scheduled = uow.events.get(evt.event_id)
    if scheduled is None:
        return

    token = uow.calendar_tokens.get(scheduled.user_id)
    if token is None:
        # No OAuth yet: API can still serve .ics via a fallback route.
        return

    result = calendar_client.upsert_event(
        user_id=str(scheduled.user_id),
        event=scheduled,
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        external_id=getattr(scheduled, "calendar_external_id", None),
    )
    scheduled.calendar_external_id = result.ref.external_id

    uow.calendar_tokens.upsert(
        CalendarToken(
            user_id=token.user_id,
            provider=token.provider,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_uri=token.token_uri,
            scopes=token.scopes,
            expiry=result.expiry,
        )
    )
    uow.commit()


def schedule_traffic_monitor(evt, uow: AbstractUnitOfWork) -> None:
    if not isinstance(evt, domain_events.EventConfirmed):
        return
    if scheduler_client is None:
        return

    with uow:
        scheduled = uow.events.get(evt.event_id)
        if scheduled is None:
            return
        run_at = max(
            datetime.now(timezone.utc) + timedelta(seconds=1),
            scheduled.start_time - timedelta(hours=3),
        )
        scheduler_client.schedule_traffic_check(event_id=scheduled.id, user_id=scheduled.user_id, run_at=run_at)
        uow.commit()


def register_push_notification(evt, uow: AbstractUnitOfWork) -> None:
    if not isinstance(evt, domain_events.AlertScheduled):
        return
    if push_client is None:
        return

    scheduled = uow.events.get(evt.event_id)
    if scheduled is None:
        return

    push_client.schedule_push(
        user_id=str(scheduled.user_id),
        title="EventFlow alert",
        body="Leave now",
        trigger_at_iso=evt.trigger_at.isoformat(),
    )


def cancel_calendar_entry(evt, uow: AbstractUnitOfWork) -> None:
    if not isinstance(evt, domain_events.EventCancelled):
        return
    if calendar_client is None:
        return
    scheduled = uow.events.get(evt.event_id)
    if scheduled is None:
        return
    external_id = getattr(scheduled, "calendar_external_id", None)
    if not external_id:
        return
    token = uow.calendar_tokens.get(scheduled.user_id)
    if token is None:
        return
    result = calendar_client.delete_event(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        external_id=str(external_id),
    )
    setattr(scheduled, "calendar_external_id", None)
    uow.calendar_tokens.upsert(
        CalendarToken(
            user_id=token.user_id,
            provider=token.provider,
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_uri=token.token_uri,
            scopes=token.scopes,
            expiry=result.expiry,
        )
    )
    uow.commit()


def cancel_alerts(evt, uow: AbstractUnitOfWork) -> None:
    if not isinstance(evt, domain_events.EventCancelled):
        return
    if scheduler_client is None:
        return
    scheduler_client.cancel_traffic_check(event_id=evt.event_id)
    scheduler_client.cancel_push_due(job_key=f"user_snooze:{evt.event_id}")

