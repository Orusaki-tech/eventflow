"""Instagram /p/ preview: embed sidecar CDN URLs preferred over yt-dlp thumbnails."""

import pytest

from eventflow.adapters.share_preview_image import (
    try_instagram_embed_slide_bytes,
    try_preview_image_bytes_for_share_url,
)


def test_try_instagram_embed_slide_bytes_respects_img_index(monkeypatch: pytest.MonkeyPatch) -> None:
    html = "<html>edge_sidecar_to_children</html>"
    urls = [
        "https://scontent.cdninstagram.com/v/t51.2885-15/a_1.jpg",
        "https://scontent.cdninstagram.com/v/t51.2885-15/a_2.jpg",
    ]

    def fake_embed(*, page_url: str) -> str:
        assert "instagram.com" in page_url
        return html

    monkeypatch.setattr(
        "eventflow.adapters.share_preview_image.media_extractor.fetch_instagram_post_embed_html",
        fake_embed,
    )
    monkeypatch.setattr(
        "eventflow.adapters.share_preview_image.media_extractor.instagram_carousel_image_urls_from_embed_html",
        lambda _h: urls,
    )

    fetched: dict[str, str] = {}

    def fake_fetch(*, url: str, extra_headers: dict | None = None) -> tuple[bytes, str]:
        fetched["url"] = url
        return b"jpeg-bytes", "image/jpeg"

    monkeypatch.setattr(
        "eventflow.adapters.share_preview_image._fetch_remote_image_bytes",
        fake_fetch,
    )

    u = "https://www.instagram.com/p/AbCd123eFGh/?img_index=2"
    out = try_instagram_embed_slide_bytes(u)
    assert out is not None
    assert out[0] == b"jpeg-bytes"
    assert fetched["url"] == urls[1]


def test_try_preview_prefers_embed_before_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "eventflow.adapters.share_preview_image.try_instagram_embed_slide_bytes",
        lambda _u: (b"embed", "image/jpeg"),
    )

    def boom_extract(_url: str):
        raise AssertionError("yt-dlp should not run when embed slide succeeds")

    monkeypatch.setattr(
        "eventflow.adapters.share_preview_image.media_extractor.extract",
        boom_extract,
    )

    url = "https://www.instagram.com/p/XYZ/"
    blob, ct = try_preview_image_bytes_for_share_url(url)
    assert blob == b"embed"
    assert ct == "image/jpeg"
