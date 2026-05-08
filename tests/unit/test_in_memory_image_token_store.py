from __future__ import annotations

from unittest.mock import patch

from eventflow.adapters.image_token_store import InMemoryImageTokenStore


def test_in_memory_put_get_roundtrip():
    s = InMemoryImageTokenStore(ttl_seconds=3600)
    t = s.put(content_type="image/jpeg", image_bytes=b"\xff\xd8\xff hi")
    got = s.get(token=t)
    assert got is not None
    assert got.content_type == "image/jpeg"
    assert got.image_bytes == b"\xff\xd8\xff hi"


def test_in_memory_expires():
    s = InMemoryImageTokenStore(ttl_seconds=10)
    with patch("eventflow.adapters.image_token_store.time.monotonic", return_value=1.0):
        t = s.put(content_type="image/png", image_bytes=b"x")
        assert s.get(token=t) is not None
    with patch("eventflow.adapters.image_token_store.time.monotonic", return_value=500.0):
        assert s.get(token=t) is None
