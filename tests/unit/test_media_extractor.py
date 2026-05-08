from __future__ import annotations

from datetime import date

import pytest

from eventflow.adapters import media_extractor


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.tiktok.com/@user/video/123",
        "https://www.instagram.com/reel/abc/",
        "https://www.facebook.com/some/video/1",
        "https://fb.watch/xyz/",
        "https://twitter.com/user/status/1",
        "https://x.com/user/status/1",
        "https://www.reddit.com/r/test/comments/abc/title/",
        "https://www.linkedin.com/posts/someone_some-post-123/",
    ],
)
def test_supports_url_for_top_social(url: str):
    assert media_extractor.supports_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://notyoutube.com/watch?v=1",
        "https://evil.twitter.com.example.com/status/1",
        "file:///etc/passwd",
        "http://127.0.0.1:8000/",
    ],
)
def test_supports_url_rejects_non_matches(url: str):
    assert media_extractor.supports_url(url) is False


def test_parse_upload_date_handles_valid_yyyymmdd():
    d = media_extractor._parse_upload_date("20250131")  # type: ignore[attr-defined]
    assert d == date(2025, 1, 31)


def test_extract_picks_best_thumbnail_without_network(monkeypatch: pytest.MonkeyPatch):
    class _FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def extract_info(self, url, download=False):  # noqa: ANN001
            return {
                "title": "T",
                "description": "D",
                "uploader": "U",
                "upload_date": "20250131",
                "http_headers": {
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.instagram.com/",
                    "Cookie": "should_not_forward=true",
                },
                "thumbnails": [
                    {"url": "https://cdn/x_small.jpg", "width": 100, "height": 100},
                    {"url": "https://cdn/x_big.jpg", "width": 1000, "height": 1000},
                ],
            }

    monkeypatch.setattr(media_extractor, "YoutubeDL", _FakeYDL)
    out = media_extractor.extract("https://www.youtube.com/watch?v=1")
    assert out.thumbnail_url == "https://cdn/x_big.jpg"
    assert out.thumbnail_request_headers == {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.instagram.com/",
    }


def test_extract_passes_cookiefile_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path):
    cookiefile = tmp_path / "cookies.txt"
    cookiefile.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    captured_opts = {}

    class _FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def extract_info(self, url, download=False):  # noqa: ANN001
            return {"title": "T"}

    monkeypatch.setenv("YTDLP_COOKIE_FILE", str(cookiefile))
    monkeypatch.setattr(media_extractor, "YoutubeDL", _FakeYDL)

    media_extractor.extract("https://www.instagram.com/reel/abc/")
    assert captured_opts.get("cookiefile") == str(cookiefile)


def test_instagram_legacy_media_includes_carousel_index():
    u = "https://www.instagram.com/p/DX6w3_giDDd/?img_index=2&igsh=test"
    pair = media_extractor.instagram_legacy_media_fetch_params(u)
    assert pair is not None
    legacy_url, hdrs = pair
    assert legacy_url == "https://www.instagram.com/p/DX6w3_giDDd/media/?size=l&img_index=2"
    assert hdrs["Referer"] == u


def test_instagram_legacy_media_carousel_index_alias():
    u = "https://www.instagram.com/p/AbCd09/?carousel_index=1"
    pair = media_extractor.instagram_legacy_media_fetch_params(u)
    assert pair is not None
    assert "img_index=1" in pair[0]


def test_instagram_legacy_media_none_for_reel():
    assert (
        media_extractor.instagram_legacy_media_fetch_params("https://www.instagram.com/reel/abc123/")
        is None
    )


def test_extract_instagram_overrides_thumbnail_when_img_index_present(monkeypatch: pytest.MonkeyPatch):
    class _FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def extract_info(self, url, download=False):  # noqa: ANN001
            return {"title": "T", "thumbnail": "https://cdn.example/first_slide.jpg"}

    monkeypatch.setattr(media_extractor, "YoutubeDL", _FakeYDL)
    u = "https://www.instagram.com/p/SHORT/?img_index=3"
    out = media_extractor.extract(u)
    assert out.thumbnail_url == "https://www.instagram.com/p/SHORT/media/?size=l&img_index=3"
    assert out.thumbnail_request_headers is not None


def test_extract_instagram_keeps_ytdlp_thumb_when_no_slide_query(monkeypatch: pytest.MonkeyPatch):
    class _FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def extract_info(self, url, download=False):  # noqa: ANN001
            return {"title": "T", "thumbnail": "https://cdn.example/hero.jpg"}

    monkeypatch.setattr(media_extractor, "YoutubeDL", _FakeYDL)
    u = "https://www.instagram.com/p/SHORT/"
    out = media_extractor.extract(u)
    assert out.thumbnail_url == "https://cdn.example/hero.jpg"


def test_extract_instagram_legacy_when_ytdlp_missing_thumbnail(monkeypatch: pytest.MonkeyPatch):
    class _FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def extract_info(self, url, download=False):  # noqa: ANN001
            return {"title": "Photo carousel"}

    monkeypatch.setattr(media_extractor, "YoutubeDL", _FakeYDL)
    u = "https://www.instagram.com/p/ONLYPHOTOS/"
    out = media_extractor.extract(u)
    assert out.thumbnail_url == "https://www.instagram.com/p/ONLYPHOTOS/media/?size=l"

