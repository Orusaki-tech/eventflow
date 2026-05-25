from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import redis


@dataclass(frozen=True)
class CachedParsedDraft:
    title: str
    start_time_iso: str
    venue: str
    confidence_score: float
    price: str | None = None


def normalize_shared_url(url: str) -> str:
    """
    Best-effort canonicalization so equivalent shared URLs map to the same cache key.

    - lowercases scheme/host
    - strips fragment
    - removes common tracking params (utm_*, fbclid, gclid, igshid, si)
    - removes trailing slash (except root)
    """
    p = urlparse(url.strip())
    scheme = (p.scheme or "").lower()
    netloc = (p.netloc or "").lower()
    path = p.path or ""
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    drop_keys = {"fbclid", "gclid", "igshid", "si"}
    q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        lk = (k or "").lower()
        if lk.startswith("utm_"):
            continue
        if lk in drop_keys:
            continue
        q.append((k, v))
    query = urlencode(q, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


class ShareParseCache:
    def __init__(
        self,
        redis_url: str,
        *,
        prefix: str = "eventflow:cache:share_url_parse:v1:",
        ttl_seconds: int = 30 * 24 * 3600,
        lock_prefix: str = "eventflow:lock:share_url_parse:v1:",
        lock_ttl_seconds: int = 60,
    ) -> None:
        self._r = redis.Redis.from_url(redis_url)
        self._prefix = prefix
        self._ttl = int(ttl_seconds)
        self._lock_prefix = lock_prefix
        self._lock_ttl = int(lock_ttl_seconds)

    def _key(self, normalized_url: str) -> str:
        h = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        return f"{self._prefix}{h}"

    def _lock_key(self, normalized_url: str) -> str:
        h = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        return f"{self._lock_prefix}{h}"

    def get(self, *, url: str) -> CachedParsedDraft | None:
        normalized = normalize_shared_url(url)
        raw = self._r.get(self._key(normalized))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            title = data.get("title")
            start_time_iso = data.get("start_time_iso")
            venue = data.get("venue")
            confidence_score = data.get("confidence_score")
            if not isinstance(title, str) or not isinstance(start_time_iso, str) or not isinstance(venue, str):
                return None
            if not isinstance(confidence_score, (int, float)):
                return None
            raw_price = data.get("price")
            price: str | None
            if raw_price is None:
                price = None
            elif isinstance(raw_price, str):
                p = raw_price.strip()
                price = p if p else None
            else:
                price = str(raw_price).strip() or None
            return CachedParsedDraft(
                title=title,
                start_time_iso=start_time_iso,
                venue=venue,
                confidence_score=float(confidence_score),
                price=price,
            )
        except Exception:
            return None

    def put(self, *, url: str, parsed: CachedParsedDraft) -> None:
        normalized = normalize_shared_url(url)
        payload = {
            "title": parsed.title,
            "start_time_iso": parsed.start_time_iso,
            "venue": parsed.venue,
            "confidence_score": parsed.confidence_score,
            "price": parsed.price,
        }
        self._r.set(self._key(normalized), json.dumps(payload).encode("utf-8"), ex=self._ttl)

    def try_acquire_lock(self, *, url: str, owner: str) -> bool:
        normalized = normalize_shared_url(url)
        # NX + EX: lock key exists only while work is in progress.
        return bool(self._r.set(self._lock_key(normalized), owner.encode("utf-8"), nx=True, ex=self._lock_ttl))

    def release_lock(self, *, url: str, owner: str) -> None:
        normalized = normalize_shared_url(url)
        lock_key = self._lock_key(normalized)
        current = self._r.get(lock_key)
        if current and current.decode("utf-8") == owner:
            self._r.delete(lock_key)


class NoOpShareParseCache:
    def get(self, *, url: str) -> CachedParsedDraft | None:  # pragma: no cover
        return None

    def put(self, *, url: str, parsed: CachedParsedDraft) -> None:  # pragma: no cover
        return None

    def try_acquire_lock(self, *, url: str, owner: str) -> bool:  # pragma: no cover
        return True

    def release_lock(self, *, url: str, owner: str) -> None:  # pragma: no cover
        pass

