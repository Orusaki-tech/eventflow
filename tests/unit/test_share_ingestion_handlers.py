from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from google.genai.errors import APIError as GeminiAPIError

from eventflow.adapters.gemini_client import AbstractGeminiClient, FakeGeminiClient, ParsedEventDraft
from eventflow.domain import commands
from eventflow.service_layer import handlers
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_fallback_parsed_prefers_ytdlp_title_line():
    p = handlers._fallback_parsed_from_share_text(
        url="https://www.instagram.com/p/ZZ/",
        text="URL: https://x\nTitle: Mother's Day Session\n",
    )
    assert p.title == "Mother's Day Session"
    assert p.start_time is None
    assert p.confidence_score == 0.2


class _BoomImageGemini(AbstractGeminiClient):
    """parse_event_image fails (carousel path); parse_event_text succeeds (URL fallback)."""

    def parse_event_image(
        self,
        *,
        image_bytes: bytes,
        content_type: str | None = None,
        reference_calendar_date=None,
    ) -> ParsedEventDraft:
        raise GeminiAPIError(403, {"error": {"message": "SERVICE_DISABLED"}})

    def parse_event_text(self, *, text: str, reference_calendar_date=None) -> ParsedEventDraft:
        return ParsedEventDraft(
            title="Caption-derived title",
            start_time=None,
            venue="",
            confidence_score=0.44,
            price=None,
        )


def test_instagram_carousel_gemini_failure_falls_back_to_single_metadata_draft(monkeypatch):
    user_id = uuid4()
    uow = FakeUnitOfWork()
    tiny_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\xff\xd9"

    monkeypatch.setattr(
        handlers,
        "_instagram_carousel_slide_fetch_targets",
        lambda url: ([("https://cdn.example.com/x.jpg", {"Referer": "https://www.instagram.com/"})], True),
    )
    monkeypatch.setattr(handlers, "_fetch_remote_image_bytes", lambda url, extra_headers=None: (tiny_jpeg, "image/jpeg"))
    monkeypatch.setattr(handlers.media_extractor, "supports_url", lambda _u: False)
    monkeypatch.setattr(handlers, "_fetch_url_text", lambda url: "Title: Ignored\n")
    monkeypatch.setattr(handlers, "try_preview_image_bytes_for_share_url", lambda _u: None)

    rows, slides_used = handlers.handle_capture_instagram_carousel_url(
        user_id=user_id,
        url="https://www.instagram.com/p/AbCd123eFGh/",
        uow=uow,
        gemini=_BoomImageGemini(),
        carousel_slide_indices=[1],
    )
    assert len(rows) == 1
    assert slides_used == [1]
    assert rows[0]["title"] == "Caption-derived title"
    assert rows[0]["_share_preview_image_bytes"] == tiny_jpeg


def test_capture_event_url_gemini_failure_falls_back_to_metadata_draft(monkeypatch):
    user_id = uuid4()
    uow = FakeUnitOfWork()

    monkeypatch.setattr(handlers.media_extractor, "supports_url", lambda _u: False)
    monkeypatch.setattr(handlers, "_fetch_url_text", lambda url: "Title: Offline Title\n")
    monkeypatch.setattr(handlers, "try_preview_image_bytes_for_share_url", lambda _u: None)

    def boom(*args, **kwargs):
        raise GeminiAPIError(403, {"error": {"message": "SERVICE_DISABLED"}})

    monkeypatch.setattr(handlers, "handle_capture_event_text", boom)

    out = handlers.handle_capture_event_url(
        commands.CaptureEventUrl(user_id=user_id, url="https://www.instagram.com/p/AbCd123eFGh/"),
        uow,
        gemini=object(),
    )
    assert out["title"] == "Offline Title"
    assert out["start_time"] is None
    assert uow.committed is True


def test_capture_event_text_creates_draft():
    user_id = uuid4()
    parsed = ParsedEventDraft(
        title="Shared text event",
        start_time=datetime.now(timezone.utc),
        venue="Somewhere",
        confidence_score=0.9,
    )
    gemini = FakeGeminiClient(parsed=parsed)
    uow = FakeUnitOfWork()

    out = handlers.handle_capture_event_text(commands.CaptureEventText(user_id=user_id, text="hello"), uow, gemini=gemini)
    assert out["title"] == parsed.title
    assert uow.committed is True

