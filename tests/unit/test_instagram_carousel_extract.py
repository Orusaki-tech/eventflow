from __future__ import annotations

from eventflow.adapters import media_extractor


def test_instagram_post_shortcode_strips_query():
    assert (
        media_extractor.instagram_post_shortcode(
            "https://www.instagram.com/p/AbCd123eFGh/?img_index=3&utm_source=x"
        )
        == "AbCd123eFGh"
    )


def test_instagram_post_shortcode_rejects_reel():
    assert media_extractor.instagram_post_shortcode("https://www.instagram.com/reel/xyz/") is None


def test_carousel_urls_from_embed_html_extracts_ordered_unique():
    html = (
        'junk edge_sidecar_to_children":{"edges":['
        '\\"display_url\\":\\"https:\\\\/\\\\/instagram.cdn.fbcdn.net\\\\\\/v\\\\\\/t51\\\\\\/a.webp\\",'
        '\\"display_url\\":\\"https:\\\\/\\\\/instagram.cdn.fbcdn.net\\\\\\/v\\\\\\/t51\\\\\\/b.webp\\",'
        '\\"display_url\\":\\"https:\\\\/\\\\/instagram.cdn.fbcdn.net\\\\\\/v\\\\\\/t51\\\\\\/b.webp\\"'
        "]}}"
    )
    urls = media_extractor.instagram_carousel_image_urls_from_embed_html(html)
    assert urls == [
        "https://instagram.cdn.fbcdn.net/v/t51/a.webp",
        "https://instagram.cdn.fbcdn.net/v/t51/b.webp",
    ]


def test_carousel_urls_empty_without_marker():
    assert media_extractor.instagram_carousel_image_urls_from_embed_html("<html></html>") == []
