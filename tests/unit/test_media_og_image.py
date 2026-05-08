from __future__ import annotations

from eventflow.entrypoints.api.routes import media


def test_extract_og_image_url_prefers_og_image():
    html = """
    <html><head>
      <meta property="og:title" content="X">
      <meta property="og:image" content="https://cdn.example.com/img.jpg">
      <meta name="twitter:image" content="https://cdn.example.com/twitter.jpg">
    </head></html>
    """
    assert media._extract_og_image_url(html) == "https://cdn.example.com/img.jpg"  # type: ignore[attr-defined]


def test_extract_og_image_url_falls_back_to_twitter_image():
    html = """
    <html><head>
      <meta name="twitter:image" content="https://cdn.example.com/twitter.jpg">
    </head></html>
    """
    assert media._extract_og_image_url(html) == "https://cdn.example.com/twitter.jpg"  # type: ignore[attr-defined]


def test_extract_og_image_url_none_when_missing():
    html = "<html><head><title>No image</title></head></html>"
    assert media._extract_og_image_url(html) is None  # type: ignore[attr-defined]


def test_resolve_preview_image_bytes_linkedin_uses_og_image(monkeypatch):
    url = "https://www.linkedin.com/posts/someone_some-post-123/"
    og_image_url = "https://cdn.example.com/linkedin-preview.jpg"

    def _fake_extract(_url: str, **_kwargs):
        raise RuntimeError("yt-dlp blocked")

    def _fake_fetch_html_text(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 1_000_000) -> str:
        assert "linkedin.com" in url
        return f"""
        <html><head>
          <meta property="og:image" content="{og_image_url}">
        </head></html>
        """

    fetched: dict[str, str] = {}

    def _fake_fetch_image_bytes(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 5_000_000, extra_headers=None):
        fetched["url"] = url
        return b"img-bytes", "image/jpeg"

    monkeypatch.setattr(media.media_extractor, "extract", _fake_extract)
    # Ensure we don't hit real network via LinkedIn oEmbed attempt.
    monkeypatch.setattr(media, "_fetch_json", lambda **_kwargs: {})
    monkeypatch.setattr(media, "_fetch_html_text", _fake_fetch_html_text)
    monkeypatch.setattr(media, "_fetch_image_bytes", _fake_fetch_image_bytes)

    out_bytes, out_type = media._resolve_preview_image_bytes(url)  # type: ignore[attr-defined]
    assert out_bytes == b"img-bytes"
    assert out_type == "image/jpeg"
    assert fetched["url"] == og_image_url


def test_resolve_preview_image_bytes_linkedin_uses_oembed_thumbnail(monkeypatch):
    url = "https://www.linkedin.com/posts/someone_some-post-123/"
    oembed_thumb = "https://media.example.com/preview.jpg"

    def _fake_extract(_url: str, **_kwargs):
        raise RuntimeError("yt-dlp blocked")

    def _fake_fetch_json(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 1_000_000):
        assert "linkedin.com/oembed" in url
        return {"thumbnail_url": oembed_thumb}

    fetched: dict[str, str] = {}

    def _fake_fetch_image_bytes(*, url: str, timeout_seconds: float = 5.0, max_bytes: int = 5_000_000, extra_headers=None):
        fetched["url"] = url
        return b"img-bytes", "image/jpeg"

    monkeypatch.setattr(media.media_extractor, "extract", _fake_extract)
    monkeypatch.setattr(media, "_fetch_json", _fake_fetch_json)
    monkeypatch.setattr(media, "_fetch_image_bytes", _fake_fetch_image_bytes)

    out_bytes, out_type = media._resolve_preview_image_bytes(url)  # type: ignore[attr-defined]
    assert out_bytes == b"img-bytes"
    assert out_type == "image/jpeg"
    assert fetched["url"] == oembed_thumb

