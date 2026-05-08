from __future__ import annotations

from unittest.mock import patch

from eventflow.adapters import media_extractor
from eventflow.service_layer.handlers import instagram_carousel_preview_slide_bytes


def test_instagram_carousel_preview_fetches_each_sidecar_slide(monkeypatch):
    html = (
        'junk edge_sidecar_to_children":{"edges":['
        '\\"display_url\\":\\"https:\\\\/\\\\/instagram.cdn.fbcdn.net\\\\\\/v\\\\\\/t51\\\\\\/a.webp\\",'
        '\\"display_url\\":\\"https:\\\\/\\\\/instagram.cdn.fbcdn.net\\\\\\/v\\\\\\/t51\\\\\\/b.webp\\"'
        "]}}"
    )

    monkeypatch.setattr(media_extractor, "fetch_instagram_post_embed_html", lambda page_url: html)

    fetched: list[str] = []

    def fake_fetch(*, url: str, extra_headers: dict[str, str] | None = None, timeout_seconds: float = 25.0, max_bytes: int = 15_000_000):
        fetched.append(url)
        return b"\xff\xd8\xff fake", "image/jpeg"

    monkeypatch.setattr("eventflow.service_layer.handlers._fetch_remote_image_bytes", fake_fetch)

    rows = instagram_carousel_preview_slide_bytes(url="https://www.instagram.com/p/AbCd123eFGh/")
    assert len(rows) == 2
    assert rows[0][0] == 1 and rows[1][0] == 2
    assert fetched == [
        "https://instagram.cdn.fbcdn.net/v/t51/a.webp",
        "https://instagram.cdn.fbcdn.net/v/t51/b.webp",
    ]
