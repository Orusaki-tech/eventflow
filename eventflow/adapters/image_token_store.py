from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional
from uuid import uuid4

import redis


@dataclass(frozen=True)
class StoredImage:
    content_type: str
    image_bytes: bytes


class InMemoryImageTokenStore:
    """
    Process-local token store for ENV=local when REDIS_URL is unset.

    Not suitable for multi-worker production (each worker has its own map).
    """

    def __init__(self, *, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._m: dict[str, tuple[float, StoredImage]] = {}

    def _purge_unlocked(self) -> None:
        now = time.monotonic()
        dead = [k for k, (deadline, _) in self._m.items() if deadline <= now]
        for k in dead:
            del self._m[k]

    def put(self, *, content_type: str, image_bytes: bytes) -> str:
        token = uuid4().hex
        deadline = time.monotonic() + self._ttl
        with self._lock:
            self._purge_unlocked()
            self._m[token] = (deadline, StoredImage(content_type=content_type, image_bytes=image_bytes))
        return token

    def get(self, *, token: str) -> Optional[StoredImage]:
        with self._lock:
            self._purge_unlocked()
            row = self._m.get(token)
            if row is None:
                return None
            _deadline, img = row
            return img


class ImageTokenStore:
    """
    Short-lived image byte storage keyed by an opaque token.

    Intended use:
    - server fetches an image once (the preview image)
    - client renders it from /media/image?token=...
    - after onLoadEnd, client asks server to run Gemini on the same token
    """

    def __init__(self, redis_url: str, *, prefix: str = "eventflow:img:", ttl_seconds: int = 600) -> None:
        self._r = redis.Redis.from_url(redis_url)
        self._prefix = prefix
        self._ttl = ttl_seconds

    def _k(self, token: str) -> str:
        return f"{self._prefix}{token}"

    def put(self, *, content_type: str, image_bytes: bytes) -> str:
        token = uuid4().hex
        key = self._k(token)
        # Store as hash: {ct, b}. Atomic enough for our use; both fields TTL together.
        pipe = self._r.pipeline()
        pipe.hset(key, mapping={"ct": content_type, "b": image_bytes})
        pipe.expire(key, self._ttl)
        pipe.execute()
        return token

    def get(self, *, token: str) -> Optional[StoredImage]:
        key = self._k(token)
        data = self._r.hgetall(key)
        if not data:
            return None
        ct = data.get(b"ct") or b""
        bts = data.get(b"b") or b""
        if not ct or not bts:
            return None
        try:
            content_type = ct.decode("utf-8", errors="replace")
        except Exception:
            content_type = "application/octet-stream"
        return StoredImage(content_type=content_type, image_bytes=bytes(bts))

